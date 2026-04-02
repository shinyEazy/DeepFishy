"""LLM-backed response API endpoints."""

import json
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from api.deps import get_db
from core.logging import logger
from services.chat import ChatService
from services.response import ResponseService

router = APIRouter(prefix="/responses", tags=["Responses"])


class ContentPart(BaseModel):
    """A single content part."""

    text: str = Field(..., min_length=1, description="Text content")


class ResponseRequest(BaseModel):
    """Request schema for a session-aware response."""

    message: str = Field(..., min_length=1, description="Latest user message")
    conversation_id: Optional[str] = Field(
        default=None,
        description="Optional persisted conversation ID. A new session is created when omitted.",
    )
    stream: bool = Field(
        default=False, description="Whether to stream the response using SSE"
    )


class ResponsePayload(BaseModel):
    """Response schema for conversational responses."""

    conversation_id: str = Field(..., description="Conversation that owns the response")
    message_id: str = Field(..., description="Persisted assistant message ID")
    role: str = Field(default="model", description="Responder role")
    parts: List[ContentPart] = Field(..., description="Response content parts")
    created_at: str = Field(..., description="Assistant message creation timestamp")


def _build_contents(messages: List[Any]) -> List[Dict[str, Any]]:
    """Build Gemini-compatible contents from persisted messages."""
    return [
        {
            "role": "model" if message.role == "assistant" else "user",
            "parts": [{"text": message.content}],
        }
        for message in messages
        if str(message.content).strip()
    ]


@router.post("/", response_model=ResponsePayload)
async def create_response(
    request: ResponseRequest, db: Session = Depends(get_db)
) -> Any:
    """Generate a response and persist it inside a conversation."""
    try:
        response_service = ResponseService()
        chat_service = ChatService(db)
        conversation = chat_service.get_or_create_conversation(request.conversation_id)
        chat_service.ensure_conversation_title(conversation, request.message)
        chat_service.save_message(
            conversation_id=conversation.id,
            role="user",
            content=request.message,
            metadata={"source": "responses_api"},
        )
        contents = _build_contents(chat_service.get_messages(conversation.id, limit=10))

        if request.stream:

            def event_stream():
                chunks: List[str] = []
                assistant_message = None

                try:
                    yield f"data: {json.dumps({'type': 'conversation_id', 'conversation_id': conversation.id})}\n\n"
                    for chunk in response_service.stream_response(contents):
                        if not chunk:
                            continue
                        chunks.append(chunk)
                        yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"

                    response_text = "".join(chunks).strip()
                    if not response_text:
                        response_text = "I couldn't generate a response right now."

                    assistant_message = chat_service.save_message(
                        conversation_id=conversation.id,
                        role="assistant",
                        content=response_text,
                        metadata={
                            "source": "responses_api",
                            "streamed": True,
                        },
                    )

                    yield (
                        "data: "
                        + json.dumps(
                            {
                                "type": "done",
                                "conversation_id": conversation.id,
                                "message_id": assistant_message.id,
                            }
                        )
                        + "\n\n"
                    )
                except Exception as exc:
                    logger.error(
                        f"Streaming response generation error: {exc}", exc_info=True
                    )
                    yield f"data: {json.dumps({'type': 'error', 'error': str(exc)})}\n\n"
                finally:
                    if assistant_message is not None or not chunks:
                        return

                    response_text = "".join(chunks).strip()
                    if not response_text:
                        return

                    chat_service.save_message(
                        conversation_id=conversation.id,
                        role="assistant",
                        content=response_text,
                        metadata={
                            "source": "responses_api",
                            "streamed": True,
                            "interrupted": True,
                        },
                    )

            return StreamingResponse(
                event_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        response_text = response_service.generate_response(contents)
        assistant_message = chat_service.save_message(
            conversation_id=conversation.id,
            role="assistant",
            content=response_text,
            metadata={"source": "responses_api", "streamed": False},
        )
        return ResponsePayload(
            conversation_id=conversation.id,
            message_id=assistant_message.id,
            role="model",
            parts=[ContentPart(text=response_text)],
            created_at=assistant_message.created_at.isoformat(),
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(f"Response generation error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/health")
async def response_health_check() -> Dict[str, str]:
    """Basic health check for the responses router."""
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    model_name = os.getenv("RESPONSE_MODEL", "gemini-3.1-flash-lite-preview")
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    return {
        "status": "healthy",
        "message": (
            f"Responses service is operational with model '{model_name}' in '{location}'"
            + (f" for project '{project}'" if project else "")
        ),
    }
