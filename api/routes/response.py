"""LLM-backed response API endpoints."""

import json
import os
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core.logging import logger
from services.response import ResponseService

router = APIRouter(prefix="/responses", tags=["Responses"])


class ContentPart(BaseModel):
    """A single content part."""

    text: str = Field(..., min_length=1, description="Text content")


class ContentItem(BaseModel):
    """A single conversation item."""

    role: str = Field(..., description="Message role, such as user or model")
    parts: List[ContentPart] = Field(
        ..., min_length=1, description="Message parts for this role"
    )


class ResponseRequest(BaseModel):
    """Request schema for conversational responses."""

    contents: List[ContentItem] = Field(
        ..., min_length=1, description="Conversation contents"
    )
    stream: bool = Field(
        default=False, description="Whether to stream the response using SSE"
    )


class ResponsePayload(BaseModel):
    """Response schema for conversational responses."""

    role: str = Field(default="model", description="Responder role")
    parts: List[ContentPart] = Field(..., description="Response content parts")


@router.post("/", response_model=ResponsePayload)
async def create_response(request: ResponseRequest) -> Any:
    """Generate a response from the configured Gemini model."""
    try:
        response_service = ResponseService()
        contents = [item.model_dump() for item in request.contents]

        if request.stream:

            def event_stream():
                try:
                    for chunk in response_service.stream_response(contents):
                        if not chunk:
                            continue
                        yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
                    yield 'data: {"type": "done"}\n\n'
                except Exception as exc:
                    logger.error(
                        f"Streaming response generation error: {exc}", exc_info=True
                    )
                    yield f"data: {json.dumps({'type': 'error', 'error': str(exc)})}\n\n"

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
        return ResponsePayload(role="model", parts=[ContentPart(text=response_text)])
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
