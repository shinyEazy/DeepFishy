"""Configuration loading utilities."""

import os
import yaml
from functools import lru_cache
from typing import Dict, Any, Optional


def _get_config_path() -> str:
    """Get the absolute path to config.yaml."""
    # Navigate from utils/ to project root, then to configs/
    module_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(module_dir)
    return os.path.join(project_root, "configs", "config.yaml")


@lru_cache(maxsize=1)
def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load configuration from YAML file (cached).

    Args:
        config_path: Optional path to config file. Defaults to configs/config.yaml.

    Returns:
        Parsed configuration dictionary.
    """
    if config_path is None:
        config_path = _get_config_path()

    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_llm_config(model_name: str) -> Optional[Dict[str, Any]]:
    """Get model configuration by name from config.yaml.

    Args:
        model_name: The name of the model as defined in config.yaml under 'llm'.

    Returns:
        Model configuration dict or None if not found.
    """
    config = load_config()
    return config.get("llm", {}).get(model_name)


def get_vlm_config() -> Optional[Dict[str, Any]]:
    """Get VLM (Vision Language Model) configuration from config.yaml.

    Returns:
        VLM configuration dict or None if not found.
    """
    config = load_config()
    return config.get("vlm")


def get_embedding_config(model_name: str) -> Optional[Dict[str, Any]]:
    """Get model configuration by name from config.yaml.

    Args:
        model_name: The name of the model as defined in config.yaml under 'embedding'.

    Returns:
        Model configuration dict or None if not found.
    """
    config = load_config()
    return config.get("embedding", {}).get(model_name)


# ============================================================
# DeepFishy Default Model Helpers
# ============================================================

def get_deepfishy_defaults() -> Dict[str, Any]:
    """Get the deepfishy defaults section from config.yaml.

    Returns:
        Dictionary with default model names for llm, vlm, embedding.
    """
    config = load_config()
    return config.get("deepfishy", {})


def get_default_llm_name() -> Optional[str]:
    """Get the default LLM model name from deepfishy config.

    Returns:
        The default LLM model name, or None if not set.
    """
    return get_deepfishy_defaults().get("llm")


def get_default_vlm_name() -> Optional[str]:
    """Get the default VLM model name from deepfishy config.

    Returns:
        The default VLM model name, or None if not set.
    """
    return get_deepfishy_defaults().get("vlm")


def get_default_embedding_name() -> Optional[str]:
    """Get the default embedding model name from deepfishy config.

    Returns:
        The default embedding model name, or None if not set.
    """
    return get_deepfishy_defaults().get("embedding")
