"""LLM Provider service for creating chat models."""

import os
from typing import Optional

from langchain_core.language_models.chat_models import BaseChatModel
from dotenv import load_dotenv

from core.logging import logger

load_dotenv()

MODEL_PROVIDER = os.getenv("MODEL_PROVIDER")


def get_llm() -> Optional[BaseChatModel]:
    """
    Get the configured LLM based on MODEL_PROVIDER environment variable.

    Returns:
        BaseChatModel instance or None if not configured

    Raises:
        ValueError: If MODEL_PROVIDER is not recognized
    """
    if MODEL_PROVIDER == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        google_api_key = os.getenv("GOOGLE_API_KEY")
        try:
            logger.info("Initializing Gemini model for LLM provider")
            return ChatGoogleGenerativeAI(
                model="gemini-2.5-flash", google_api_key=google_api_key
            )
        except Exception as e:
            logger.error(f"Failed to initialize Gemini model: {e}")
            raise

    elif MODEL_PROVIDER == "openai":
        from langchain_openai import ChatOpenAI

        openai_api_key = os.getenv("OPENAI_API_KEY")
        try:
            logger.info("Initializing OpenAI model for LLM provider")
            return ChatOpenAI(model="gpt-4o-mini", api_key=openai_api_key)
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI model: {e}")
            raise

    else:
        logger.warning(
            f"Unknown MODEL_PROVIDER: {MODEL_PROVIDER}. "
            "Please set to 'google' or 'openai'"
        )
        raise ValueError(f"Unknown MODEL_PROVIDER: {MODEL_PROVIDER}")


def get_extraction_llm() -> BaseChatModel:
    """
    Get an LLM optimized for graph extraction tasks.

    Uses a slightly different model configuration that may be better
    suited for structured extraction tasks.

    Returns:
        BaseChatModel instance
    """
    if MODEL_PROVIDER == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        google_api_key = os.getenv("GOOGLE_API_KEY")
        return ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=google_api_key,
            temperature=0.0,  # More deterministic for extraction
        )

    elif MODEL_PROVIDER == "openai":
        from langchain_openai import ChatOpenAI

        openai_api_key = os.getenv("OPENAI_API_KEY")
        return ChatOpenAI(
            model="gpt-4o-mini",
            api_key=openai_api_key,
            temperature=0.0,  # More deterministic for extraction
        )

    else:
        raise ValueError(f"Unknown MODEL_PROVIDER: {MODEL_PROVIDER}")
