import os
from typing import Optional
from deepagents import create_deep_agent
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel
from prompts.orchestrator_prompt import ORCHESTRATOR_PROMPT
from app.utils.load_agents import load_agents
from tools.get_current_date import get_current_date
from app.core.logging import logger


load_dotenv()


def _create_model() -> Optional[BaseChatModel]:
    """
    Lazy model initialization to avoid credential errors during import.
    Checks for API keys before attempting to initialize models.
    """
    google_api_key = os.getenv("GOOGLE_API_KEY")
    openai_api_key = os.getenv("OPENAI_API_KEY")

    # Try Gemini first if API key is available
    if google_api_key and google_api_key != "your_google_api_key_here":
        try:
            logger.info("Initializing Gemini model")
            return ChatGoogleGenerativeAI(
                model="gemini-2.5-flash", google_api_key=google_api_key
            )
        except Exception as e:
            logger.warning(f"Failed to initialize Gemini model: {e}")

    # Fallback to OpenAI if available
    if openai_api_key and openai_api_key != "your_openai_api_key_here":
        try:
            logger.info("Initializing OpenAI model")
            return ChatOpenAI(model="gpt-4o-mini", api_key=openai_api_key)
        except Exception as e:
            logger.warning(f"Failed to initialize OpenAI model: {e}")

    # No valid API keys found
    logger.warning("No valid API keys found. Agent will be created without a model.")
    logger.warning("Please set GOOGLE_API_KEY or OPENAI_API_KEY in your .env file")
    return None


def _create_agent():
    """Factory function to create the agent with lazy initialization."""
    custom_model = _create_model()

    subagents = load_agents(
        names=[
            "market_data",
            "knowledge_search",
        ]
    )

    logger.info(f"Loaded {len(subagents)} subagent(s)")

    # Create the agent
    return create_deep_agent(
        model=custom_model,
        tools=[],
        system_prompt=ORCHESTRATOR_PROMPT,
        subagents=subagents,
    ).with_config({"recursion_limit": 5})


agent = _create_agent()
