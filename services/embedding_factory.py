"""Compatibility shim for the embedding factory."""

from deepfishy.infra.llm.embedding_factory import (
    get_embedding_dim,
    get_embedding_provider,
)

__all__ = ["get_embedding_provider", "get_embedding_dim"]
