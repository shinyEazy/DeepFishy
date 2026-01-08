"""Chat API endpoints."""

from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationDetail,
    ConversationListResponse,
    ConversationSummary,
    DeleteConversationResponse,
    ChatMessage,
)
from app.services.chat import ChatService
from app.core.logging import logger


router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("", response_model=ChatResponse)
async def chat_completion(request: ChatRequest, db: Session = Depends(get_db)) -> Any:
    """
    Send a chat message and get AI response.

    Supports both streaming (SSE) and non-streaming modes:
    - If stream=false: Returns complete response as JSON
    - If stream=true: Returns Server-Sent Events stream

    The agent will use your configured workflow (market data, knowledge search, etc.)
    to generate contextual responses.
    """
    try:
        chat_service = ChatService(db)

        if request.stream:
            # Return streaming response using Server-Sent Events
            return StreamingResponse(
                chat_service.chat_completion_stream(
                    message=request.message, conversation_id=request.conversation_id
                ),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",  # Disable buffering in nginx
                },
            )
        else:
            # Return complete response
            result = await chat_service.chat_completion(
                message=request.message,
                conversation_id=request.conversation_id,
                stream=False,
            )
            return result

    except Exception as e:
        logger.error(f"Chat completion error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: str, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get a conversation by ID with all its messages.

    Returns conversation details including full message history.
    """
    try:
        chat_service = ChatService(db)

        conversation = chat_service.get_conversation(conversation_id)
        if not conversation:
            raise HTTPException(
                status_code=404, detail=f"Conversation {conversation_id} not found"
            )

        messages = chat_service.get_messages(conversation_id)

        return {
            "id": conversation.id,
            "title": conversation.title,
            "created_at": conversation.created_at,
            "updated_at": conversation.updated_at,
            "messages": [
                {
                    "id": msg.id,
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": msg.created_at,
                    "metadata": msg.meta,
                }
                for msg in messages
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get conversation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    limit: int = 50, offset: int = 0, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    List all conversations ordered by most recent.

    Supports pagination with limit and offset parameters.
    """
    try:
        chat_service = ChatService(db)

        conversations = chat_service.list_conversations(limit=limit, offset=offset)

        # Count messages for each conversation
        conversation_summaries = []
        for conv in conversations:
            message_count = len(chat_service.get_messages(conv.id))
            conversation_summaries.append(
                {
                    "id": conv.id,
                    "title": conv.title,
                    "created_at": conv.created_at,
                    "updated_at": conv.updated_at,
                    "message_count": message_count,
                }
            )

        return {
            "conversations": conversation_summaries,
            "total": len(conversations),
            "limit": limit,
            "offset": offset,
        }

    except Exception as e:
        logger.error(f"List conversations error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/conversations/{conversation_id}", response_model=DeleteConversationResponse
)
async def delete_conversation(
    conversation_id: str, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Delete a conversation and all its messages.

    This is a permanent operation and cannot be undone.
    """
    try:
        chat_service = ChatService(db)

        success = chat_service.delete_conversation(conversation_id)

        if not success:
            raise HTTPException(
                status_code=404, detail=f"Conversation {conversation_id} not found"
            )

        return {
            "success": True,
            "conversation_id": conversation_id,
            "message": "Conversation deleted successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete conversation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def chat_health_check() -> Dict[str, str]:
    """
    Check if the chat service is healthy.

    Verifies that the agent is loaded and ready.
    """
    try:
        from app.engine.main import agent

        if agent is None:
            return {"status": "unhealthy", "message": "Agent not initialized"}

        return {"status": "healthy", "message": "Chat service is operational"}

    except Exception as e:
        return {"status": "unhealthy", "message": str(e)}
