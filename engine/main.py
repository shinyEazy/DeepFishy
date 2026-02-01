import os
import re
import json
import argparse
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv

from langchain_core.language_models.chat_models import BaseChatModel
from deepagents import create_deep_agent

from core.logging import logger
from engine.prompts.orchestrator_prompt import ORCHESTRATOR_PROMPT
from engine.orchestrators.report_writer import create_report_writer_orchestrator
from engine.orchestrators.research import create_research_orchestrator

from utils.load_agents import load_agents
from utils.load_config import get_default_llm_name
from utils.model_factory import create_llm_client


load_dotenv()

ENABLE_DISK_BACKEND = "true"
OUTPUT_BASE_PATH = "outputs"


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
    # Read the default LLM model name from config.yaml (deepfishy.llm)
    default_model_name = get_default_llm_name()

    if not default_model_name:
        logger.warning(
            "No default LLM model found in config.yaml under 'deepfishy.llm'. "
            "Please check your configs/config.yaml file."
        )
        return None

    model = create_llm_client(default_model_name)

    if not model:
        logger.warning(
            f"Could not create model '{default_model_name}'. "
            "Please check config.yaml has the model definition under 'llm' section."
        )

    return model


def _create_agent(session_id: Optional[str] = None, phase: str = "write"):
    """Factory function to create the agent with lazy initialization.

    Args:
        session_id: Optional session ID for workspace persistence
        phase: 'build' for Graph RAG building (uses ResearchOrchestrator with Graphiti),
               'write' for Report writing

    Returns:
        For 'build' phase: tuple of (agent, orchestrator) for async graph processing
        For 'write' phase: agent only
    """
    custom_model = _create_model()

    if phase == "build":
        # 'build' phase now uses ResearchOrchestrator with iterative Graphiti pipeline
        logger.info("Creating Research Orchestrator (Build Phase with Graphiti)")
        orchestrator = create_research_orchestrator(
            model=custom_model, session_id=session_id, output_base_path=OUTPUT_BASE_PATH
        )
        # Return both agent and orchestrator for async processing
        return orchestrator.create(), orchestrator
    else:
        logger.info("Creating Report Writer agent (Write Phase)")
        return (
            create_report_writer_orchestrator(
                model=custom_model,
                session_id=session_id,
                output_base_path=OUTPUT_BASE_PATH,
            ),
            None,
        )


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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--phase",
        type=str,
        default=None,
        help="Phase to run: 'build' for Graph RAG building with Graphiti, 'write' for Report writing. If not specified, runs both in sequence.",
    )
    parser.add_argument(
        "--input", type=str, default=None, help="User input/query for the agent"
    )
    args = parser.parse_args()

    # Determine which phases to run
    if args.phase:
        phases_to_run = [args.phase]
    else:
        # Default: build (Graphiti) then write
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
            user_input = "Báo cáo tài chính về VNINDEX tháng 12/2025"
        else:
            user_input = "Báo cáo tài chính về VNINDEX tháng 12/2025"

        # Log phase info
        logger.info("=" * 60)
        if current_phase == "build":
            logger.info("PHASE 1: Build Knowledge Graph (Graphiti)")
        else:
            logger.info("PHASE 2: Write Report")
        logger.info("=" * 60)

        # Create agent with phase parameter (uses the same proven creation pattern)
        # Session ID is passed to ensure workspaces are shared/persisted
        agent, orchestrator = _create_agent(
            session_id=session_id if ENABLE_DISK_BACKEND else None, phase=current_phase
        )

        # This ensures charts are saved to outputs/{session_id}/images
        if ENABLE_DISK_BACKEND and hasattr(agent, "_workspace_path"):
            os.environ["OUTPUT_DIR"] = agent._workspace_path

        logger.info(f"Starting agent invocation with input: {user_input}")

        try:
            result = agent.invoke(
                {"messages": [{"role": "user", "content": user_input}]}
            )

            # Process pending graph updates for build phase
            # This handles the async Graphiti operations in the correct event loop
            if orchestrator is not None:
                import asyncio

                try:
                    added = asyncio.run(orchestrator.process_pending_graph_updates())
                    if added > 0:
                        logger.info(f"Added {added} results to knowledge graph")
                except Exception as e:
                    logger.warning(f"Failed to process pending graph updates: {e}")

            if not result.get("messages"):
                logger.error("No messages found in result!")
                logger.error(f"Result structure: {result}")
                print("ERROR: No response from agent")
                continue

            final_response_raw = result["messages"][-1].content
            final_response = _extract_text_from_content(final_response_raw)

            todos = result.get("todos", [])

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
