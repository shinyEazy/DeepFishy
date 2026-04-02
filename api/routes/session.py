"""Session API endpoints backed by persisted conversations."""

from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.deps import get_db
from api.schemas.session import (
    CreateSessionRequest,
    DeleteSessionResponse,
    SessionDetail,
    SessionListResponse,
    SessionMessage,
)
from services.chat import ChatService, DEFAULT_CONVERSATION_TITLE
from core.logging import logger

router = APIRouter(prefix="/sessions", tags=["Sessions"])


def _serialize_session_message(message) -> SessionMessage:
    """Convert a message model into the session API shape."""
    return SessionMessage(
        id=message.id,
        role=message.role,
        content=message.content,
        created_at=message.created_at,
        metadata=message.meta,
    )


def _serialize_session_detail(conversation) -> SessionDetail:
    """Convert a conversation model into the session detail shape."""
    return SessionDetail(
        id=conversation.id,
        title=conversation.title or DEFAULT_CONVERSATION_TITLE,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=[
            _serialize_session_message(message)
            for message in sorted(
                conversation.messages,
                key=lambda item: item.created_at or conversation.created_at,
            )
        ],
    )


@router.get("/", response_model=SessionListResponse)
async def list_sessions(
    limit: int = 100, offset: int = 0, db: Session = Depends(get_db)
) -> Dict[str, object]:
    """List persisted sessions ordered by most recent activity."""
    try:
        chat_service = ChatService(db)
        results, total_count = chat_service.list_conversations_with_counts(
            limit=limit, offset=offset
        )

        return {
            "sessions": [
                {
                    "id": conversation.id,
                    "title": conversation.title or DEFAULT_CONVERSATION_TITLE,
                    "created_at": conversation.created_at,
                    "updated_at": conversation.updated_at,
                    "message_count": message_count,
                }
                for conversation, message_count in results
            ],
            "total": total_count,
            "limit": limit,
            "offset": offset,
        }
    except Exception as exc:
        logger.error(f"List sessions error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/", response_model=SessionDetail, status_code=status.HTTP_201_CREATED)
async def create_session(
    request: CreateSessionRequest, db: Session = Depends(get_db)
) -> SessionDetail:
    """Create a blank persisted session."""
    try:
        chat_service = ChatService(db)
        conversation = chat_service.create_conversation(
            title=request.title or DEFAULT_CONVERSATION_TITLE
        )
        return _serialize_session_detail(conversation)
    except Exception as exc:
        logger.error(f"Create session error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str, db: Session = Depends(get_db)) -> SessionDetail:
    """Get a persisted session with its full message transcript."""
    try:
        chat_service = ChatService(db)
        conversation = chat_service.get_conversation(session_id)
        if not conversation:
            raise HTTPException(
                status_code=404, detail=f"Session {session_id} not found"
            )

        return _serialize_session_detail(conversation)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Get session error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/{session_id}", response_model=DeleteSessionResponse)
async def delete_session(
    session_id: str, db: Session = Depends(get_db)
) -> DeleteSessionResponse:
    """Delete a persisted session and all of its messages."""
    try:
        chat_service = ChatService(db)
        success = chat_service.delete_conversation(session_id)
        if not success:
            raise HTTPException(
                status_code=404, detail=f"Session {session_id} not found"
            )

        return DeleteSessionResponse(
            success=True,
            session_id=session_id,
            message="Session deleted successfully",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Delete session error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
