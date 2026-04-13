"""Model factory for creating LangChain chat models from configuration."""

import base64
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Optional
from google import genai
from google.genai import types

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI

from utils.load_config import get_llm_config, get_vlm_config
from core.logging import logger


@dataclass
class _GoogleGenAIResponse:
    """Minimal response shim matching what benchmark/evaluate.py expects."""

    content: str
    usage_metadata: dict[str, int]


class GoogleVertexAIExpressClient:
    """Native google.genai adapter for Vertex AI Express.

    This intentionally bypasses LangChain's Gemini wrapper so this mode behaves
    like the direct SDK usage proven in test.py.
    """

    def __init__(self, config: dict) -> None:
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

        self.model = config.get("model")
        self.temperature = config.get("temperature")
        self.top_p = config.get("top_p")
        self.top_k = config.get("top_k")
        self.max_tokens = config.get("max_tokens")

        self.client = genai.Client(vertexai=True, api_key=api_key)

    @staticmethod
    def _data_url_to_part(url: str) -> types.Part:
        if not url.startswith("data:") or ";base64," not in url:
            raise ValueError("Expected a base64 data URL for multimodal content.")

        header, b64 = url.split(",", 1)
        mime_type = header[5:].split(";", 1)[0]
        return types.Part.from_bytes(data=base64.b64decode(b64), mime_type=mime_type)

    def _to_generate_config(
        self, system_instruction: str | None
    ) -> types.GenerateContentConfig | None:
        config_kwargs: dict[str, Any] = {}
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction
        if self.temperature is not None:
            config_kwargs["temperature"] = self.temperature
        if self.top_p is not None:
            config_kwargs["top_p"] = self.top_p
        if self.top_k is not None:
            config_kwargs["top_k"] = self.top_k
        if self.max_tokens is not None:
            config_kwargs["max_output_tokens"] = self.max_tokens
        return types.GenerateContentConfig(**config_kwargs) if config_kwargs else None

    def _to_contents(
        self, messages: list[Any]
    ) -> tuple[str | None, list[types.Content]]:
        system_instruction: str | None = None
        contents: list[types.Content] = []

        for message in messages:
            if isinstance(message, SystemMessage):
                if isinstance(message.content, str):
                    system_instruction = message.content
                else:
                    system_instruction = (
                        "\n".join(
                            block.get("text", "")
                            for block in message.content
                            if isinstance(block, dict) and block.get("type") == "text"
                        ).strip()
                        or None
                    )
                continue

            if isinstance(message, HumanMessage):
                raw_content = message.content
                parts: list[types.Part] = []

                if isinstance(raw_content, str):
                    parts.append(types.Part.from_text(text=raw_content))
                else:
                    for block in raw_content:
                        if not isinstance(block, dict):
                            continue
                        if block.get("type") == "text":
                            text = block.get("text", "")
                            if text:
                                parts.append(types.Part.from_text(text=text))
                        elif block.get("type") == "image_url":
                            image_url = block.get("image_url", {}).get("url")
                            if image_url:
                                parts.append(self._data_url_to_part(image_url))

                if parts:
                    contents.append(types.Content(role="user", parts=parts))

        return system_instruction, contents

    def invoke(self, messages: list[Any]) -> _GoogleGenAIResponse:
        system_instruction, contents = self._to_contents(messages)
        config = self._to_generate_config(system_instruction)

        text_chunks: list[str] = []
        usage_metadata = {"input_tokens": 0, "output_tokens": 0}

        for chunk in self.client.models.generate_content_stream(
            model=self.model,
            contents=contents,
            config=config,
        ):
            chunk_text = getattr(chunk, "text", None) or ""
            if chunk_text:
                text_chunks.append(chunk_text)

            usage = getattr(chunk, "usage_metadata", None)
            if usage is not None:
                usage_metadata = {
                    "input_tokens": getattr(usage, "prompt_token_count", 0) or 0,
                    "output_tokens": getattr(usage, "candidates_token_count", 0) or 0,
                }

        return _GoogleGenAIResponse(
            content="".join(text_chunks),
            usage_metadata=usage_metadata,
        )


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
            model_kwargs = _build_google_ai_studio_kwargs(config)
            logger.info(
                f"Creating Google AI Studio Gemini model: {config.get('model')}"
            )
            return ChatGoogleGenerativeAI(**model_kwargs)

        if api_provider == "google_vertex_ai":
            model_kwargs = _build_google_vertex_ai_kwargs(config)
            logger.info(f"Creating Vertex AI Gemini model: {config.get('model')}")
            return ChatGoogleGenerativeAI(**model_kwargs)

        if api_provider == "google_vertex_ai_express":
            logger.info(
                f"Creating Vertex AI Express Gemini model: {config.get('model')}"
            )
            return GoogleVertexAIExpressClient(config)

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
