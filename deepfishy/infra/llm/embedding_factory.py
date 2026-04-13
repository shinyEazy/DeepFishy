"""Factory for creating embedding providers from config.yaml."""

from embedding.base_embedding import BaseEmbedding
from embedding.google_embedding import GoogleEmbedding
from embedding.openai_embedding import OpenAIEmbedding
from deepfishy.infra.config.model_registry import (
    get_default_embedding_name,
    get_embedding_config,
)
from deepfishy.shared.logging import logger


def get_embedding_provider(model_name: str = None) -> BaseEmbedding:
    """Create an embedding provider based on model config."""
    if model_name is None:
        model_name = get_default_embedding_name()
        if not model_name:
            raise ValueError(
                "No embedding model specified and deepfishy.embedding not set in config.yaml"
            )
    config = get_embedding_config(model_name)

    if not config:
        raise ValueError(f"Embedding model '{model_name}' not found in config.yaml")

    api_provider = config.get("api_provider", "").lower()

    if api_provider == "google":
        return GoogleEmbedding(model_name=model_name)
    if api_provider == "openai":
        return OpenAIEmbedding(model_name=model_name)

    raise ValueError(f"Unsupported embedding provider: {api_provider}")


def get_embedding_dim(model_name: str = None) -> int:
    """Get the output dimensionality for an embedding model."""
    if model_name is None:
        model_name = get_default_embedding_name()
        if not model_name:
            logger.warning("No embedding model specified, using default dim 1536")
            return 1536

    config = get_embedding_config(model_name)
    if not config:
        logger.warning(f"Model '{model_name}' not found, using default dim 1536")
        return 1536

    return config.get("output_dimensionality", 1536)
