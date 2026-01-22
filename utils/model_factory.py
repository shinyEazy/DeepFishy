"""Model factory for creating LangChain chat models from configuration."""

from typing import Optional
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI

from utils.load_config import get_model_config
from core.logging import logger


def create_model_client(model_name: str) -> Optional[BaseChatModel]:
    """Create a LangChain chat model from config.yaml settings.

    Args:
        model_name: The name of the model as defined in config.yaml under 'llm'.
                   Examples: 'qwen3-coder-30b', 'gemini-2.5-flash', 'gpt-4o-mini'

    Returns:
        A configured BaseChatModel instance, or None if model not found or creation fails.
    """
    config = get_model_config(model_name)
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

            if config.get("base_url"):
                model_kwargs["base_url"] = config["base_url"]

            if config.get("temperature"):
                model_kwargs["temperature"] = config["temperature"]

            if config.get("top_p"):
                model_kwargs["top_p"] = config["top_p"]

            if config.get("max_tokens"):
                model_kwargs["max_tokens"] = config["max_tokens"]

            if config.get("timeout"):
                model_kwargs["timeout"] = config["timeout"]

            if config.get("reasoning_effort"):
                model_kwargs["reasoning_effort"] = config["reasoning_effort"]

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
