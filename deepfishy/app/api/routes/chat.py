"""Chat API endpoints."""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from deepfishy.app.api.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationDetail,
    ConversationListResponse,
    DeleteConversationResponse,
)
from deepfishy.app.api.deps import get_db
from deepfishy.features.chat.runtime import is_chat_agent_ready
from deepfishy.features.chat.service import ChatService
from deepfishy.shared.logging import logger

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("/completions", response_model=ChatResponse)
async def chat_completion(request: ChatRequest, db: Session = Depends(get_db)) -> Any:
    """Send a chat message and get AI response."""
    try:
        chat_service = ChatService(db)

        if request.stream:
            return StreamingResponse(
                chat_service.chat_completion_stream(
                    message=request.message, conversation_id=request.conversation_id
                ),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        return await chat_service.chat_completion(
            message=request.message,
            conversation_id=request.conversation_id,
            stream=False,
        )
    except Exception as error:
        logger.error(f"Chat completion error: {error}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(error))


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: str, db: Session = Depends(get_db)
) -> ConversationDetail:
    """Get a conversation by ID with all its messages."""
    try:
        chat_service = ChatService(db)
        conversation = chat_service.get_conversation(conversation_id)
        if not conversation:
            raise HTTPException(
                status_code=404, detail=f"Conversation {conversation_id} not found"
            )
        return conversation
    except HTTPException:
        raise
    except Exception as error:
        logger.error(f"Get conversation error: {error}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(error))


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    limit: int = 50, offset: int = 0, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """List all conversations ordered by most recent."""
    try:
        chat_service = ChatService(db)
        results, total_count = chat_service.list_conversations_with_counts(
            limit=limit, offset=offset
        )
        return {
            "conversations": [
                {
                    "id": conv.id,
                    "title": conv.title,
                    "created_at": conv.created_at,
                    "updated_at": conv.updated_at,
                    "message_count": message_count,
                }
                for conv, message_count in results
            ],
            "total": total_count,
            "limit": limit,
            "offset": offset,
        }
    except Exception as error:
        logger.error(f"List conversations error: {error}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(error))


@router.delete(
    "/conversations/{conversation_id}", response_model=DeleteConversationResponse
)
async def delete_conversation(
    conversation_id: str, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Delete a conversation and all its messages."""
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
    except Exception as error:
        logger.error(f"Delete conversation error: {error}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(error))


@router.get("/health")
async def chat_health_check() -> Dict[str, str]:
    """Check if the chat service is healthy."""
    try:
        if not is_chat_agent_ready():
            return {"status": "unhealthy", "message": "Agent not initialized"}
        return {"status": "healthy", "message": "Chat service is operational"}
    except Exception as error:
        return {"status": "unhealthy", "message": str(error)}


__all__ = ["router"]
