"""Chat API schemas."""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    """Request schema for chat completion."""

    message: str = Field(..., description="User message", min_length=1)
    conversation_id: Optional[str] = Field(
        default=None,
        description="Optional conversation ID (will create new if not provided)",
    )
    stream: bool = Field(
        default=False,
        description="Whether to stream the response using Server-Sent Events",
    )


class ChatMessage(BaseModel):
    """Schema for a chat message."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Message ID")
    role: str = Field(..., description="Message role (user or assistant)")
    content: str = Field(..., description="Message content")
    created_at: datetime = Field(..., description="Message creation timestamp")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional message metadata"
    )


class ChatResponse(BaseModel):
    """Response schema for chat completion (non-streaming)."""

    conversation_id: str = Field(..., description="Conversation ID")
    message: str = Field(..., description="Assistant response message")
    message_id: str = Field(..., description="Message ID")
    created_at: str = Field(..., description="Response creation timestamp")


class ConversationSummary(BaseModel):
    """Summary schema for a conversation."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Conversation ID")
    title: str = Field(..., description="Conversation title")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    message_count: int = Field(
        default=0, description="Number of messages in conversation"
    )


class ConversationDetail(BaseModel):
    """Detailed schema for a conversation with messages."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Conversation ID")
    title: str = Field(..., description="Conversation title")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    messages: list[ChatMessage] = Field(
        default_factory=list, description="List of messages in the conversation"
    )


class ConversationListResponse(BaseModel):
    """Response schema for listing conversations."""

    conversations: list[ConversationSummary] = Field(
        default_factory=list, description="List of conversations"
    )
    total: int = Field(..., description="Total number of conversations")
    limit: int = Field(..., description="Number of conversations returned")
    offset: int = Field(..., description="Offset used for pagination")


class DeleteConversationResponse(BaseModel):
    """Response schema for deleting a conversation."""

    success: bool = Field(..., description="Whether deletion was successful")
    conversation_id: str = Field(..., description="ID of deleted conversation")
    message: str = Field(..., description="Status message")


__all__ = [
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "ConversationDetail",
    "ConversationListResponse",
    "ConversationSummary",
    "DeleteConversationResponse",
]
