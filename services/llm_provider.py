"""LLM Provider service for creating chat models."""

import os
from typing import Optional

from langchain_core.language_models.chat_models import BaseChatModel
from dotenv import load_dotenv

from core.logging import logger

load_dotenv()

MODEL_PROVIDER = os.getenv("MODEL_PROVIDER")


from utils.model_factory import create_llm_client


def get_llm() -> Optional[BaseChatModel]:
    """
    Get the configured LLM based on MODEL_PROVIDER environment variable.

    Returns:
        BaseChatModel instance or None if not configured

    Raises:
        ValueError: If MODEL_PROVIDER is not recognized
    """
    if MODEL_PROVIDER == "google":
        return create_llm_client("gemini-2.5-flash")

    elif MODEL_PROVIDER == "openai":
        return create_llm_client("gpt-4o-mini")

    else:
        logger.warning(
            f"Unknown MODEL_PROVIDER: {MODEL_PROVIDER}. "
            "Please set to 'google' or 'openai'"
        )
        raise ValueError(f"Unknown MODEL_PROVIDER: {MODEL_PROVIDER}")


def get_extraction_llm() -> BaseChatModel:
    """
    Get an LLM optimized for graph extraction tasks.

    Returns:
        BaseChatModel instance
    """
    llm = get_llm()
    if llm:
        # Set temperature to 0 for deterministic extraction if supported
        if hasattr(llm, "temperature"):
            llm.temperature = 0.0
    return llm
