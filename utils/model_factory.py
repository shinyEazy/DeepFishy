"""Model factory for creating LangChain chat models from configuration."""

import os
from functools import lru_cache
from typing import Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from utils.load_config import get_llm_config, get_vlm_config
from core.logging import logger

def _import_langchain_google_generative_ai():
    """Import LangChain's Google wrapper lazily for optional provider support."""
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError as exc:
        raise ImportError(
            "langchain-google-genai is not installed. Install it to use "
            "google_ai_studio or google_vertex_ai providers."
        ) from exc
    return ChatGoogleGenerativeAI


def _apply_optional_google_params(config: dict, model_kwargs: dict) -> dict:
    """Apply shared Gemini tuning params from config."""
    optional_params = [
        "temperature",
        "top_p",
        "top_k",
        "max_tokens",
        "timeout",
        "max_retries",
    ]
    for param in optional_params:
        if param in config:
            model_kwargs[param] = config[param]
    return model_kwargs


def _build_google_ai_studio_kwargs(config: dict) -> dict:
    """Build kwargs for Google AI Studio / Generative Language API."""
    model_kwargs = {"model": config.get("model")}

    api_key = (
        config.get("api_key")
        or os.getenv("GOOGLE_API_KEY")
        or os.getenv("GEMINI_API_KEY")
    )
    if not api_key:
        raise ValueError(
            "Google AI Studio requires an API key in config['api_key'] or "
            "the GOOGLE_API_KEY / GEMINI_API_KEY environment variable."
        )

    model_kwargs["api_key"] = api_key
    return _apply_optional_google_params(config, model_kwargs)


def _build_google_vertex_ai_express_kwargs(config: dict) -> dict:
    """Build kwargs for Vertex AI Express via LangChain's Gemini wrapper."""
    model_kwargs = {
        "model": config.get("model"),
        "vertexai": True,
        "location": config.get("location")
        or os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
    }

    api_key = (
        config.get("api_key")
        or os.getenv("GOOGLE_CLOUD_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
        or os.getenv("GEMINI_API_KEY")
    )
    if not api_key:
        raise ValueError(
            "Vertex AI Express requires an API key in config['api_key'] or "
            "the GOOGLE_CLOUD_API_KEY / GOOGLE_API_KEY / GEMINI_API_KEY "
            "environment variable."
        )

    model_kwargs["api_key"] = api_key

    project = config.get("project") or os.getenv("GOOGLE_CLOUD_PROJECT")
    if project:
        model_kwargs["project"] = project

    return _apply_optional_google_params(config, model_kwargs)


def _build_google_vertex_ai_kwargs(config: dict) -> dict:
    """Build kwargs for Vertex AI Gemini."""
    model_kwargs = {
        "model": config.get("model"),
        "vertexai": True,
        "location": config.get("location")
        or os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
    }

    project = config.get("project") or os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project:
        raise ValueError(
            "Vertex AI requires a project in config['project'] or the "
            "GOOGLE_CLOUD_PROJECT environment variable."
        )
    model_kwargs["project"] = project

    # Deliberately do not fall back to AI Studio keys here.
    vertex_api_key = config.get("api_key") or os.getenv("GOOGLE_CLOUD_API_KEY")
    if vertex_api_key:
        model_kwargs["api_key"] = vertex_api_key

    return _apply_optional_google_params(config, model_kwargs)


def _create_model_client(config: dict, model_name: str) -> Optional[BaseChatModel]:
    """Instantiate a chat model client from config."""
    api_provider = config.get("api_provider")

    try:
        if api_provider == "openai":
            model_kwargs = {
                "model": config.get("model"),
                "api_key": config.get("api_key"),
            }

            if config.get("reasoning_effort"):
                model_kwargs["reasoning_effort"] = config.get("reasoning_effort")

            logger.info(f"Creating OpenAI model: {config.get('model')}")
            return ChatOpenAI(**model_kwargs)

        if api_provider == "google_ai_studio":
            ChatGoogleGenerativeAI = _import_langchain_google_generative_ai()
            model_kwargs = _build_google_ai_studio_kwargs(config)
            logger.info(
                f"Creating Google AI Studio Gemini model: {config.get('model')}"
            )
            return ChatGoogleGenerativeAI(**model_kwargs)

        if api_provider == "google_vertex_ai":
            ChatGoogleGenerativeAI = _import_langchain_google_generative_ai()
            model_kwargs = _build_google_vertex_ai_kwargs(config)
            logger.info(f"Creating Vertex AI Gemini model: {config.get('model')}")
            return ChatGoogleGenerativeAI(**model_kwargs)

        if api_provider == "google_vertex_ai_express":
            ChatGoogleGenerativeAI = _import_langchain_google_generative_ai()
            model_kwargs = _build_google_vertex_ai_express_kwargs(config)
            logger.info(
                f"Creating Vertex AI Express Gemini model: {config.get('model')}"
            )
            return ChatGoogleGenerativeAI(**model_kwargs)

        if api_provider == "openai_compatible":
            model_kwargs = {
                "model": config.get("model"),
                "api_key": config.get("api_key"),
            }

            optional_params = [
                "base_url",
                "temperature",
                "top_p",
                "max_tokens",
                "timeout",
                "reasoning_effort",
            ]
            for param in optional_params:
                if param in config:
                    model_kwargs[param] = config[param]

            # Backward compatibility for older config entries that used `max_token`.
            if "max_tokens" not in model_kwargs and "max_token" in config:
                model_kwargs["max_tokens"] = config["max_token"]

            logger.info(f"Creating OpenAI-compatible model: {config.get('model')}")
            return ChatOpenAI(**model_kwargs)

        logger.warning(
            f"Unknown api_provider '{api_provider}' for model '{model_name}'"
        )
        return None

    except Exception as e:
        logger.error(f"Failed to create model '{model_name}': {e}")
        return None


@lru_cache(maxsize=16)
def create_llm_client(model_name: str) -> Optional[BaseChatModel]:
    """Create a LangChain chat model from config.yaml settings.

    Args:
        model_name: The name of the model as defined in config.yaml under 'llm'.
                   Examples: 'qwen3-coder-30b', 'gemini-2.5-flash', 'gpt-4o-mini'

    Returns:
        A configured BaseChatModel instance, or None if model not found or creation fails.
    """
    config = get_llm_config(model_name)
    if not config:
        logger.warning(f"Model '{model_name}' not found in config.yaml")
        return None

    return _create_model_client(config, model_name)


@lru_cache(maxsize=16)
def create_vlm_client(model_name: str) -> Optional[BaseChatModel]:
    """Create a LangChain chat model from config.yaml settings.

    Args:
        model_name: The name of the model as defined in config.yaml under 'llm'.
                   Examples: 'qwen3-coder-30b', 'gemini-2.5-flash', 'gpt-4o-mini'

    Returns:
        A configured BaseChatModel instance, or None if model not found or creation fails.
    """
    config = get_vlm_config(model_name)
    if not config:
        logger.warning(f"Model '{model_name}' not found in config.yaml")
        return None

    return _create_model_client(config, model_name)
