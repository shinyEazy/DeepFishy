"""SQLAlchemy models for chat conversations and messages."""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, JSON, ForeignKey, Index
from sqlalchemy.orm import Mapped, relationship
import uuid

from app.db.base import Base


def generate_uuid():
    """Generate a UUID string."""
    return str(uuid.uuid4())


class Conversation(Base):
    """Chat conversation model.

    Represents a conversation thread containing multiple messages.
    """

    __tablename__ = "conversations"

    # Primary key
    id: Mapped[str] = Column(
        String(36), primary_key=True, default=generate_uuid, index=True
    )

    # Conversation metadata
    title: Mapped[str] = Column(String(500), nullable=True)
    meta: Mapped[dict] = Column("metadata", JSON, default=dict, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at: Mapped[datetime] = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationship to messages
    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )

    # Indexes for common queries
    __table_args__ = (
        Index("idx_conversations_created_at", "created_at"),
        Index("idx_conversations_updated_at", "updated_at"),
    )

    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, title={self.title}, created_at={self.created_at})>"


class Message(Base):
    """Chat message model.

    Represents a single message in a conversation (user or assistant).
    """

    __tablename__ = "messages"

    # Primary key
    id: Mapped[str] = Column(
        String(36), primary_key=True, default=generate_uuid, index=True
    )

    # Foreign key to conversation
    conversation_id: Mapped[str] = Column(
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Message content
    role: Mapped[str] = Column(
        String(20), nullable=False, index=True
    )  # 'user' or 'assistant'
    content: Mapped[str] = Column(Text, nullable=False)

    # Optional metadata (sources, agent steps, etc.)
    meta: Mapped[dict] = Column("metadata", JSON, default=dict, nullable=True)

    # Timestamp
    created_at: Mapped[datetime] = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    # Relationship to conversation
    conversation = relationship("Conversation", back_populates="messages")

    # Indexes for common queries
    __table_args__ = (
        Index("idx_messages_conversation_id", "conversation_id"),
        Index("idx_messages_created_at", "created_at"),
        Index("idx_messages_conversation_created", "conversation_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Message(id={self.id}, role={self.role}, conversation_id={self.conversation_id})>"
