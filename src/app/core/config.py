"""Application configuration from environment variables."""

import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Celery
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = os.getenv(
        "CELERY_RESULT_BACKEND", "redis://localhost:6379/0"
    )

    # API
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))

    # Milvus Vector Database
    MILVUS_HOST: str = os.getenv("MILVUS_HOST", "localhost")
    MILVUS_PORT: int = int(os.getenv("MILVUS_PORT", "19530"))
    MILVUS_COLLECTION_NAME: str = os.getenv("MILVUS_COLLECTION_NAME", "articles")
    MILVUS_EMBEDDING_DIM: int = int(os.getenv("MILVUS_EMBEDDING_DIM", "1024"))

    # Embeddings - Remote API (via Kaggle + ngrok)
    EMBEDDING_API_URL: str = os.getenv("EMBEDDING_API_URL", "http://localhost:8001")
    EMBEDDING_API_TIMEOUT: int = int(os.getenv("EMBEDDING_API_TIMEOUT", "60"))
    EMBEDDING_API_MAX_RETRIES: int = int(os.getenv("EMBEDDING_API_MAX_RETRIES", "3"))

    # Ingestion Pipeline
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "1024"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "128"))
    BATCH_INSERT_SIZE: int = int(os.getenv("BATCH_INSERT_SIZE", "64"))

    # MinIO Storage
    MINIO_URL: str = os.getenv("MINIO_URL", "localhost:9000")
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    MINIO_SECURE: bool = os.getenv("MINIO_SECURE", "false").lower() == "true"

    # PostgreSQL Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "postgresql://user:password@localhost:5432/deepfishy"
    )

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "allow"  # Allow extra fields from .env


settings = Settings()
