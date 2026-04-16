"""Model registry and config loading helpers."""

from functools import lru_cache
from typing import Any

import yaml

from deepfishy.infra.config.paths import CONFIGS_DIR, resolve_project_path


@lru_cache(maxsize=1)
def load_model_registry(config_path: str | None = None) -> dict[str, Any]:
    """Load the model registry from YAML."""
    path = (
        resolve_project_path(config_path)
        if config_path
        else CONFIGS_DIR / "config.yaml"
    )
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def get_llm_config(model_name: str) -> dict[str, Any] | None:
    return load_model_registry().get("llm", {}).get(model_name)


def get_vlm_config(model_name: str) -> dict[str, Any] | None:
    return load_model_registry().get("vlm", {}).get(model_name)


def get_embedding_config(model_name: str) -> dict[str, Any] | None:
    return load_model_registry().get("embedding", {}).get(model_name)


def get_deepfishy_defaults() -> dict[str, Any]:
    return load_model_registry().get("deepfishy", {})


def get_default_llm_name() -> str | None:
    return get_deepfishy_defaults().get("llm")


def get_default_vlm_name() -> str | None:
    return get_deepfishy_defaults().get("vlm")


def get_default_embedding_name() -> str | None:
    return get_deepfishy_defaults().get("embedding")
