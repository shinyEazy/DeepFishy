"""Compatibility wrappers for configuration loading utilities."""

from deepfishy.infra.config.model_registry import (
    get_deepfishy_defaults,
    get_default_embedding_name,
    get_default_llm_name,
    get_default_vlm_name,
    get_embedding_config,
    get_llm_config,
    get_vlm_config,
    load_model_registry as load_config,
)

__all__ = [
    "load_config",
    "get_llm_config",
    "get_vlm_config",
    "get_embedding_config",
    "get_deepfishy_defaults",
    "get_default_llm_name",
    "get_default_vlm_name",
    "get_default_embedding_name",
]
