"""Chat API endpoints."""

from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from api.deps import get_db
from api.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationDetail,
    ConversationListResponse,
    DeleteConversationResponse,
)
from services.chat import ChatService
from core.logging import logger

router = APIRouter(prefix="/responses", tags=["Responses"])

@router.get("/")



@router.get("/health")
async def response_health_check() -> Dict[str, str]:
    """
    Check if the chat service is healthy.

    Verifies that the agent is loaded and ready.
    """
    try:
        from engine.main import agent

        if agent is None:
            return {"status": "unhealthy", "message": "Agent not initialized"}

        return {"status": "healthy", "message": "Chat service is operational"}

    except Exception as e:
        return {"status": "unhealthy", "message": str(e)}
