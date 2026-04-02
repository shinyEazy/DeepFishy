"""Session API schemas backed by persisted conversations."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SessionMessage(BaseModel):
    """Persisted message inside a session."""

    id: str = Field(..., description="Message ID")
    role: str = Field(..., description="Message role")
    content: str = Field(..., description="Message content")
    created_at: datetime = Field(..., description="Message creation timestamp")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional message metadata"
    )


class SessionSummary(BaseModel):
    """Sidebar-friendly session summary."""

    id: str = Field(..., description="Session ID")
    title: str = Field(..., description="Session title")
    created_at: datetime = Field(..., description="Session creation timestamp")
    updated_at: datetime = Field(..., description="Session last update timestamp")
    message_count: int = Field(default=0, description="Number of messages in session")


class SessionDetail(BaseModel):
    """Full session detail with messages."""

    id: str = Field(..., description="Session ID")
    title: str = Field(..., description="Session title")
    created_at: datetime = Field(..., description="Session creation timestamp")
    updated_at: datetime = Field(..., description="Session last update timestamp")
    messages: List[SessionMessage] = Field(
        default_factory=list, description="Session messages"
    )


class SessionListResponse(BaseModel):
    """Response for paginated session lists."""

    sessions: List[SessionSummary] = Field(
        default_factory=list, description="Available sessions"
    )
    total: int = Field(..., description="Total number of sessions")
    limit: int = Field(..., description="Pagination limit")
    offset: int = Field(..., description="Pagination offset")


class CreateSessionRequest(BaseModel):
    """Request to create a new session."""

    title: Optional[str] = Field(
        default=None, max_length=500, description="Optional initial session title"
    )


class DeleteSessionResponse(BaseModel):
    """Response for session deletion."""

    success: bool = Field(..., description="Whether deletion was successful")
    session_id: str = Field(..., description="Deleted session ID")
    message: str = Field(..., description="Status message")
