"""SQLAlchemy models for articles."""

from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, Index, Boolean
from sqlalchemy.orm import Mapped

from app.db.base import Base


class Article(Base):
    """Article metadata stored in PostgreSQL.

    This table stores metadata about articles, while embeddings/vectors
    are stored separately in Milvus.
    """

    __tablename__ = "articles"

    # Primary key
    id: Mapped[str] = Column(String(255), primary_key=True, index=True)

    # Article identification
    url: Mapped[str] = Column(String(500), unique=True, index=True, nullable=False)
    title: Mapped[str] = Column(String(500), nullable=False)
    sapo: Mapped[str] = Column(Text, nullable=False)
    content: Mapped[str] = Column(Text, nullable=True)

    # Classification
    category: Mapped[str] = Column(String(100), index=True, nullable=False)
    tags: Mapped[list] = Column(JSON, default=list, nullable=True)

    # Metadata
    date_published: Mapped[int] = Column(
        Integer, index=True, nullable=True
    )  # Unix timestamp
    crawled_at: Mapped[datetime] = Column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Processing status
    is_processed: Mapped[bool] = Column(Boolean, default=False, index=True)
    chunks_count: Mapped[int] = Column(Integer, default=0)
    milvus_ids: Mapped[list] = Column(
        JSON, default=list, nullable=True
    )  # MD5 hashes from Milvus

    # Metadata for tracking
    source_spider: Mapped[str] = Column(String(100), nullable=True)
    processing_error: Mapped[str] = Column(Text, nullable=True)

    # Indexes for common queries
    __table_args__ = (
        Index("idx_articles_category_date", "category", "date_published"),
        Index("idx_articles_is_processed", "is_processed"),
        Index("idx_articles_crawled_at", "crawled_at"),
    )

    def __repr__(self) -> str:
        return f"<Article(id={self.id}, title={self.title[:50]}..., url={self.url})>"
