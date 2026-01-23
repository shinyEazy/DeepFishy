"""Model factory for creating LangChain chat models from configuration."""

from typing import Optional
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI

from utils.load_config import get_llm_config, get_embedding_config
from core.logging import logger


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

        elif api_provider == "google":
            model_kwargs = {
                "model": config.get("model"),
                "api_key": config.get("api_key"),
            }

            logger.info(f"Creating Google Generative AI model: {config.get('model')}")
            return ChatGoogleGenerativeAI(**model_kwargs)

        elif api_provider == "openai_compatible":
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

            logger.info(f"Creating OpenAI-compatible model: {config.get('model')}")
            return ChatOpenAI(**model_kwargs)

        else:
            logger.warning(
                f"Unknown api_provider '{api_provider}' for model '{model_name}'"
            )
            return None

    except Exception as e:
        logger.error(f"Failed to create model '{model_name}': {e}")
        return None


def create_embedding_client(model_name: str) -> Optional[BaseChatModel]:
    """Create a LangChain embedding model from config.yaml settings.

    Args:
        model_name: The name of the model as defined in config.yaml under 'embedding'.
                   Examples: 'text-embedding-3-small'

    Returns:
        A configured BaseChatModel instance, or None if model not found or creation fails.
    """
    config = get_embedding_config(model_name)
    if not config:
        logger.warning(f"Model '{model_name}' not found in config.yaml")
        return None

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

        elif api_provider == "google":
            model_kwargs = {
                "model": config.get("model"),
                "api_key": config.get("api_key"),
            }

            logger.info(f"Creating Google Generative AI model: {config.get('model')}")
            return ChatGoogleGenerativeAI(**model_kwargs)

        elif api_provider == "openai_compatible":
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

            logger.info(f"Creating OpenAI-compatible model: {config.get('model')}")
            return ChatOpenAI(**model_kwargs)

        else:
            logger.warning(
                f"Unknown api_provider '{api_provider}' for model '{model_name}'"
            )
            return None

    except Exception as e:
        logger.error(f"Failed to create model '{model_name}': {e}")
        return None
