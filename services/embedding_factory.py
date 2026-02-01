"""Factory for creating embedding providers from config.yaml."""

from typing import Optional

from embedding.base_embedding import BaseEmbedding
from embedding.google_embedding import GoogleEmbedding
from embedding.openai_embedding import OpenAIEmbedding
from utils.load_config import get_embedding_config, get_default_embedding_name
from core.logging import logger


def get_embedding_provider(
    model_name: str = None,
) -> BaseEmbedding:
    """
    Create an embedding provider based on model name from config.yaml.

    Args:
        model_name: The model name as defined in config.yaml under 'embedding'.
                    If None, uses the default from deepfishy.embedding.

    Returns:
        An embedding provider instance.

    Raises:
        ValueError: If the model is not found or provider is not supported.
    """
    # Use default from deepfishy config if not specified
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
        logger.info(f"Creating GoogleEmbedding provider for model: {model_name}")
        return GoogleEmbedding(model_name=model_name)

    elif api_provider == "openai":
        logger.info(f"Creating OpenAIEmbedding provider for model: {model_name}")
        return OpenAIEmbedding(model_name=model_name)

    else:
        raise ValueError(f"Unsupported embedding provider: {api_provider}")


def get_embedding_dim(model_name: str = None) -> int:
    """
    Get the output dimensionality for an embedding model.

    Args:
        model_name: The model name in config.yaml. If None, uses deepfishy.embedding.

    Returns:
        The output dimensionality (default 1536 if not specified).
    """
    # Use default from deepfishy config if not specified
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
