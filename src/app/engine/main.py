import os
import re
from typing import Optional
from datetime import datetime
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel

from app.core.logging import logger
from app.engine.prompts.orchestrator_prompt import ORCHESTRATOR_PROMPT
from app.engine.tools.get_current_date import get_current_date
from app.utils.load_agents import load_agents


load_dotenv()

MODEL_PROVIDER = os.getenv("MODEL_PROVIDER")
ENABLE_DISK_BACKEND = os.getenv("ENABLE_DISK_BACKEND", "true").lower() == "true"
OUTPUT_BASE_PATH = os.getenv("OUTPUT_BASE_PATH", "outputs")


def _extract_text_from_content(content) -> str:
    """
    Extract text from message content (handles both string and list formats).

    Modern LLM APIs return content as a list of content blocks for multimodal support.
    This function handles both formats:
    - String: returns as-is
    - List: extracts text from content blocks

    Args:
        content: Either a string or list of content blocks

    Returns:
        Extracted text content as string
    """
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        # Extract text from content blocks
        text_parts = []
        for block in content:
            if isinstance(block, dict):
                # Handle dict format: {'type': 'text', 'text': '...'}
                if block.get("type") == "text" and "text" in block:
                    text_parts.append(block["text"])
            elif isinstance(block, str):
                # Handle plain string in list
                text_parts.append(block)

        return "\n".join(text_parts) if text_parts else str(content)

    # Fallback: convert to string
    return str(content)


def _create_model() -> Optional[BaseChatModel]:
    """
    Lazy model initialization to avoid credential errors during import.
    Checks for model provider before attempting to initialize models.
    """

    if MODEL_PROVIDER == "google":
        google_api_key = os.getenv("GOOGLE_API_KEY")
        try:
            logger.info("Initializing Gemini model")
            return ChatGoogleGenerativeAI(
                model="gemini-2.5-flash", google_api_key=google_api_key
            )
        except Exception as e:
            logger.warning(f"Failed to initialize Gemini model: {e}")

    elif MODEL_PROVIDER == "openai":
        openai_api_key = os.getenv("OPENAI_API_KEY")
        try:
            logger.info("Initializing OpenAI model")
            return ChatOpenAI(model="gpt-4o-mini", api_key=openai_api_key)
        except Exception as e:
            logger.warning(f"Failed to initialize OpenAI model: {e}")

    else:
        logger.warning(
            "No valid model provider found. Agent will be created without a model."
        )
        logger.warning(
            "Please set MODEL_PROVIDER in your .env file to 'google' or 'openai'"
        )
        return None


def _create_agent(session_id: Optional[str] = None):
    """Factory function to create the agent with lazy initialization."""
    custom_model = _create_model()

    subagents = load_agents(
        names=[
            "market_data",
            "knowledge_search",
            "financial_research",
            "report_outline",
            "financial_report_writer",
        ]
    )

    logger.info(f"Loaded {len(subagents)} subagent(s)")

    # Configure agent with optional disk backend
    config = {"recursion_limit": 100}
    backend = None
    workspace_path = None

    if ENABLE_DISK_BACKEND and session_id:
        workspace_path = os.path.join(OUTPUT_BASE_PATH, session_id)

        # Create standard directory structure
        os.makedirs(os.path.join(workspace_path, "images"), exist_ok=True)

        # Use DeepAgents' built-in FilesystemBackend
        # This backend writes files directly to disk and is used by FilesystemMiddleware
        backend = FilesystemBackend(root_dir=workspace_path, virtual_mode=True)

        logger.info(f"Agent workspace: {workspace_path}")
        logger.info(
            "Agent todos and files will be saved to disk using FilesystemBackend"
        )

        # Add configurable_fields for the agent to use custom backend
        config["configurable"] = {"thread_id": session_id}

    # Create the agent with FilesystemMiddleware (built-in to create_deep_agent)
    # The middleware will use the backend we provide for file operations
    agent = create_deep_agent(
        model=custom_model,
        tools=[],
        system_prompt=ORCHESTRATOR_PROMPT,
        subagents=subagents,
        backend=backend,  # Pass backend to enable disk persistence
    ).with_config(config)

    # Store workspace path for later use
    if workspace_path:
        agent._workspace_path = workspace_path
        agent._session_id = session_id

    return agent


# Export a factory function for LangGraph API
# LangGraph expects a parameterless function that returns a compiled graph
def agent():
    """Factory function to create the agent for LangGraph API."""
    custom_model = _create_model()

    subagents = load_agents(
        names=[
            "market_data",
            "knowledge_search",
            "financial_research",
            "report_outline",
            "financial_report_writer",
        ]
    )

    logger.info(f"Loaded {len(subagents)} subagent(s)")

    # Create the agent without disk backend for API use
    # Session-specific configuration will be provided via .with_config() at runtime
    return create_deep_agent(
        model=custom_model,
        tools=[],
        system_prompt=ORCHESTRATOR_PROMPT,
        subagents=subagents,
        backend=None,  # API doesn't use disk backend by default
    )


def get_agent(session_id: Optional[str] = None):
    """Get or create the agent. If session_id provided, creates new agent with that session."""
    if session_id:
        # Create new agent with specific session
        return _create_agent(session_id)
    # Create agent without disk backend for API use
    return _create_agent()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=str,
        default="Tạo báo cáo tài chính toàn diện về VNINDEX với phân tích xu hướng và biểu đồ 1 tuần gần đây",
    )
    args = parser.parse_args()
    user_input = args.input

    # Generate session ID once for this run
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Create agent with this session's workspace
    agent = _create_agent(session_id) if ENABLE_DISK_BACKEND else _create_agent()

    # Set OUTPUT_DIR environment variable for chart tools
    # This ensures charts are saved to outputs/{session_id}/images
    if ENABLE_DISK_BACKEND and hasattr(agent, "_workspace_path"):
        os.environ["OUTPUT_DIR"] = agent._workspace_path
        logger.info(f"Set OUTPUT_DIR to: {agent._workspace_path}")

    logger.info(f"Starting agent invocation with input: {user_input[:100]}...")
    result = agent.invoke({"messages": [{"role": "user", "content": user_input}]})
    logger.info(f"Agent invocation completed. Result keys: {list(result.keys())}")

    # Extract text from response (handles both string and list content formats)
    logger.info(f"Number of messages in result: {len(result.get('messages', []))}")

    if not result.get("messages"):
        logger.error("No messages found in result!")
        logger.error(f"Result structure: {result}")
        print("ERROR: No response from agent")
        exit(1)

    final_response_raw = result["messages"][-1].content
    logger.info(f"Final response type: {type(final_response_raw)}")
    final_response = _extract_text_from_content(final_response_raw)

    # Extract todos from agent state if available
    todos = result.get("todos", [])
    logger.info(f"Todos extracted: {len(todos) if isinstance(todos, list) else 'N/A'}")

    print("\n" + "=" * 80)
    print("AGENT RESPONSE:")
    print("=" * 80)
    print(final_response)

    # Save outputs to the unified session directory
    if ENABLE_DISK_BACKEND and hasattr(agent, "_workspace_path"):
        workspace_path = agent._workspace_path

        # Save final response, query, and todos to the workspace
        try:
            full_md_path = os.path.join(workspace_path, "full.md")
            user_query_path = os.path.join(workspace_path, "user_query.txt")
            todos_path = os.path.join(workspace_path, "todos.json")

            os.makedirs(workspace_path, exist_ok=True)

            # Normalize paths in the markdown content
            # Replace absolute paths like "outputs/20260113_071152/images/" with relative "images/"
            # This ensures markdown links work correctly when full.md is in the same directory

            # Get the session ID from workspace_path (e.g., "outputs/20260113_071152" -> "20260113_071152")
            session_id_from_path = os.path.basename(workspace_path)

            # Pattern to match: outputs/{session_id}/images/
            # or {OUTPUT_BASE_PATH}/{session_id}/images/
            pattern = rf"{re.escape(OUTPUT_BASE_PATH)}/{re.escape(session_id_from_path)}/images/"

            # Replace with relative path: images/
            normalized_response = re.sub(pattern, "images/", final_response)

            with open(full_md_path, "w", encoding="utf-8") as f:
                f.write(normalized_response)

            with open(user_query_path, "w", encoding="utf-8") as f:
                f.write(user_input)

            # Save todos if any exist
            if todos:
                import json

                with open(todos_path, "w", encoding="utf-8") as f:
                    json.dump(
                        todos,
                        f,
                        indent=2,
                        ensure_ascii=False,
                    )

        except Exception as e:
            logger.warning(f"Could not save agent response: {e}")
