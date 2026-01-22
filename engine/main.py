import os
import re
import json
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend

from core.logging import logger
from engine.prompts.orchestrator_prompt import ORCHESTRATOR_PROMPT
from engine.tools.get_current_date import get_current_date
from utils.load_agents import load_agents
from utils.model_factory import create_model_client


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
    Model initialization using factory and config.yaml.
    """
    model = None
    if MODEL_PROVIDER == "google":
        model = create_model_client("gemini-2.5-flash")
    elif MODEL_PROVIDER == "openai":
        model = create_model_client("gpt-4o-mini")

    if not model:
        logger.warning(
            f"Could not create model for provider '{MODEL_PROVIDER}'. "
            "Please check config.yaml or MODEL_PROVIDER env var."
        )

    return model


def _create_agent(session_id: Optional[str] = None, phase: str = "write"):
    """Factory function to create the agent with lazy initialization.

    Args:
        session_id: Optional session ID for workspace persistence
        phase: 'build' for Graph RAG building, 'write' for Report writing
    """
    custom_model = _create_model()

    # Select subagents and prompt based on phase
    if phase == "build":
        from engine.prompts.graph_builder_prompt import GRAPH_BUILDER_PROMPT

        system_prompt = GRAPH_BUILDER_PROMPT
        subagent_names = [
            "knowledge_search",
            "financial_research",
            "graph_extractor",
        ]
        logger.info("Creating Graph Builder agent (Phase 1)")
    else:
        from engine.prompts.write_phase_prompt import WRITE_PHASE_PROMPT

        system_prompt = WRITE_PHASE_PROMPT
        subagent_names = [
            "graph_query",  # Query existing GraphRAG
            "gap_analyzer",  # Analyze knowledge gaps
            "knowledge_search",  # Search for missing info
            "financial_research",  # Deep research when needed
            "graph_extractor",  # Add new knowledge to graph
            "report_outline",  # Generate outline with sections
            "section_writer",  # Write each section individually
            "critique",  # Self-critic optimization
            "chart_generator",  # Generate charts from data
            "financial_report_writer",  # Final formatting
        ]
        # Note: Sections are concatenated programmatically, no synthesizer needed
        logger.info("Creating Report Writer agent (Phase 2 - Write Phase)")

    subagents = load_agents(names=subagent_names)

    logger.info(f"Loaded {len(subagents)} subagent(s)")

    # Configure agent with optional disk backend
    config = {"recursion_limit": 1000}
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
        system_prompt=system_prompt,
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

    parser = argparse.ArgumentParser(
        description="DeepFishy Agent - Two-phase workflow for financial analysis"
    )
    parser.add_argument(
        "--phase",
        type=str,
        default=None,
        help="Phase to run: 'build' for Graph RAG building, 'write' for Report writing. If not specified, runs both in sequence.",
    )
    parser.add_argument(
        "--input", type=str, default=None, help="User input/query for the agent"
    )
    args = parser.parse_args()

    # Determine which phases to run
    if args.phase:
        phases_to_run = [args.phase]
    else:
        phases_to_run = ["build", "write"]

    # Generate session ID once for this run (shared across phases)
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    for current_phase in phases_to_run:
        # Validate phase
        if current_phase not in ["build", "write"]:
            logger.error(f"Invalid phase: {current_phase}. Must be 'build' or 'write'.")
            continue

        # Set default input based on phase if not provided by user
        if args.input:
            user_input = args.input
        elif current_phase == "build":
            user_input = "Xây dựng knowledge graph về tình hình của VNINDEX"
        else:
            user_input = "Tạo báo cáo tài chính toàn diện về VNINDEX với phân tích xu hướng và biểu đồ 1 tuần gần đây"

        # Log phase info
        logger.info("=" * 60)
        if current_phase == "build":
            logger.info("PHASE 1: Graph RAG Builder")
        else:
            logger.info(f"PHASE 2: Report Writer")
        logger.info("=" * 60)

        # Create agent with phase parameter (uses the same proven creation pattern)
        # Session ID is passed to ensure workspaces are shared/persisted
        agent = _create_agent(
            session_id=session_id if ENABLE_DISK_BACKEND else None, phase=current_phase
        )

        # Set OUTPUT_DIR environment variable for chart tools
        # This ensures charts are saved to outputs/{session_id}/images
        if ENABLE_DISK_BACKEND and hasattr(agent, "_workspace_path"):
            os.environ["OUTPUT_DIR"] = agent._workspace_path
            logger.info(f"Set OUTPUT_DIR to: {agent._workspace_path}")

        logger.info(f"Phase: {current_phase.upper()}")
        logger.info(f"Starting agent invocation with input: {user_input[:100]}...")

        try:
            result = agent.invoke(
                {"messages": [{"role": "user", "content": user_input}]}
            )
            logger.info(
                f"Agent invocation completed. Result keys: {list(result.keys())}"
            )

            # Extract text from response (handles both string and list content formats)
            logger.info(
                f"Number of messages in result: {len(result.get('messages', []))}"
            )

            if not result.get("messages"):
                logger.error("No messages found in result!")
                logger.error(f"Result structure: {result}")
                print("ERROR: No response from agent")
                continue

            final_response_raw = result["messages"][-1].content
            logger.info(f"Final response type: {type(final_response_raw)}")
            final_response = _extract_text_from_content(final_response_raw)

            # Extract todos from agent state if available
            todos = result.get("todos", [])
            logger.info(
                f"Todos extracted: {len(todos) if isinstance(todos, list) else 'N/A'}"
            )

            print("\n" + "=" * 80)
            print(f"AGENT RESPONSE ({current_phase.upper()} PHASE):")
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
                    phase_path = os.path.join(workspace_path, "phase.txt")

                    os.makedirs(workspace_path, exist_ok=True)

                    # Normalize paths in the markdown content
                    # Replace absolute paths like "outputs/20260113_071152/images/" with relative "images/"
                    session_id_from_path = os.path.basename(workspace_path)

                    # Pattern to match: outputs/{session_id}/images/
                    pattern = rf"{re.escape(OUTPUT_BASE_PATH)}/{re.escape(session_id_from_path)}/images/"

                    # Replace with relative path: images/
                    normalized_response = re.sub(pattern, "images/", final_response)

                    # Append mode if it's the second phase, or just write?
                    # The user likely wants to see the final report in full.md.
                    # Usually 'write' phase produces the final report. 'build' phase might produce some status.
                    # We will overwrite full.md for each phase so the latest is there,
                    # but for 'build' -> 'write', 'write' is the final output.

                    with open(full_md_path, "w", encoding="utf-8") as f:
                        f.write(normalized_response)

                    with open(user_query_path, "w", encoding="utf-8") as f:
                        f.write(user_input)

                    with open(phase_path, "w", encoding="utf-8") as f:
                        f.write(current_phase)

                    # Save todos if any exist
                    if todos:
                        with open(todos_path, "w", encoding="utf-8") as f:
                            json.dump(
                                todos,
                                f,
                                indent=2,
                                ensure_ascii=False,
                            )

                    logger.info(f"Outputs saved to: {workspace_path}")

                except Exception as e:
                    logger.warning(f"Could not save agent response: {e}")

        except Exception as e:
            logger.error(f"Error during execution of phase {current_phase}: {e}")
            import traceback

            traceback.print_exc()
