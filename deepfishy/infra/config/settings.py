"""Centralized runtime settings for DeepFishy."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="allow",
    )

    CELERY_BROKER_URL: str | None = None
    CELERY_RESULT_BACKEND: str | None = None

    MILVUS_HOST: str | None = None
    MILVUS_PORT: int | None = None
    MILVUS_COLLECTION_NAME: str | None = None
    MILVUS_EMBEDDING_DIM: int | None = None

    EMBEDDING_API_URL: str | None = None
    EMBEDDING_API_TIMEOUT: int | None = None
    EMBEDDING_API_MAX_RETRIES: int | None = None

    CHUNK_SIZE: int | None = None
    CHUNK_OVERLAP: int | None = None
    BATCH_INSERT_SIZE: int | None = None

    MINIO_URL: str | None = None
    MINIO_ACCESS_KEY: str | None = None
    MINIO_SECRET_KEY: str | None = None
    MINIO_SECURE: bool = False

    POSTGRES_CONN_URL: str | None = None
    POSTGRES_USER: str | None = None
    POSTGRES_PASSWORD: str | None = None

    NEO4J_URI: str | None = None
    NEO4J_USER: str | None = None
    NEO4J_PASSWORD: str | None = None
    NEO4J_DATABASE: str | None = None

    MINERU_API_KEY: str | None = None
    TAVILY_API_KEY: str | None = None
    GOOGLE_CLOUD_API_KEY: str | None = None
    GOOGLE_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None
    GOOGLE_CLOUD_PROJECT: str | None = None
    GOOGLE_CLOUD_LOCATION: str = "us-central1"
    RESPONSE_MODEL: str = "xiaomi-mimo-v2.5"


settings = Settings()
