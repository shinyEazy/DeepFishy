import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Celery
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND")

    # Milvus Vector Database
    MILVUS_HOST: str = os.getenv("MILVUS_HOST")
    MILVUS_PORT: int = int(os.getenv("MILVUS_PORT"))
    MILVUS_COLLECTION_NAME: str = os.getenv("MILVUS_COLLECTION_NAME")
    MILVUS_EMBEDDING_DIM: int = int(os.getenv("MILVUS_EMBEDDING_DIM"))

    # Embeddings
    EMBEDDING_API_URL: str = os.getenv("EMBEDDING_API_URL")
    EMBEDDING_API_TIMEOUT: int = int(os.getenv("EMBEDDING_API_TIMEOUT"))
    EMBEDDING_API_MAX_RETRIES: int = int(os.getenv("EMBEDDING_API_MAX_RETRIES"))

    # Ingestion Pipeline
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP"))
    BATCH_INSERT_SIZE: int = int(os.getenv("BATCH_INSERT_SIZE"))

    # MinIO Storage
    MINIO_URL: str = os.getenv("MINIO_URL")
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY")
    MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY")
    MINIO_SECURE: bool = os.getenv("MINIO_SECURE").lower() == "true"

    # PostgreSQL Database
    POSTGRES_CONN_URL: str = os.getenv("POSTGRES_CONN_URL")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD")

    # Neo4j Graph Database
    NEO4J_URI: str = os.getenv("NEO4J_URI")
    NEO4J_USER: str = os.getenv("NEO4J_USER")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD")
    NEO4J_DATABASE: str = os.getenv("NEO4J_DATABASE")

    MINERU_API_KEY: str = os.getenv("MINERU_API_KEY")
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY")
    GOOGLE_CLOUD_API_KEY: str | None = os.getenv("GOOGLE_CLOUD_API_KEY")
    GOOGLE_API_KEY: str | None = os.getenv("GOOGLE_API_KEY")
    GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")
    GOOGLE_CLOUD_PROJECT: str | None = os.getenv("GOOGLE_CLOUD_PROJECT")
    GOOGLE_CLOUD_LOCATION: str = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    RESPONSE_MODEL: str = os.getenv("RESPONSE_MODEL", "gemini-3.1-flash-lite-preview")

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "allow"  # Allow extra fields from .env


settings = Settings()
