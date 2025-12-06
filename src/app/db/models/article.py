"""SQLAlchemy models for articles."""

from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, Index
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
    is_processed: Mapped[bool] = Column(default=False, index=True)
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


class ArticleChunk(Base):
    """Chunk metadata (optional - for tracking which chunks exist for an article).

    This table maintains a reference between articles and their chunks in Milvus.
    Useful for managing chunk lifecycles and performing cleanup.
    """

    __tablename__ = "article_chunks"

    # Primary key
    chunk_id: Mapped[str] = Column(String(32), primary_key=True, index=True)

    # Foreign key to article
    article_id: Mapped[str] = Column(String(255), index=True, nullable=False)

    # Chunk metadata
    chunk_index: Mapped[int] = Column(Integer, nullable=False)
    text_preview: Mapped[str] = Column(String(500), nullable=True)  # First 500 chars
    embedding_dim: Mapped[int] = Column(Integer, default=1024, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = Column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        Index("idx_chunks_article_id", "article_id"),
        Index("idx_chunks_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ArticleChunk(chunk_id={self.chunk_id}, article_id={self.article_id})>"
