import os
import time
import asyncio
import argparse
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv

from langchain_core.language_models.chat_models import BaseChatModel

from core.logging import logger
from engine.orchestrators.writer import create_writer_orchestrator
from engine.orchestrators.builder import create_builder_orchestrator

from utils.load_config import get_default_llm_name
from utils.model_factory import create_llm_client

from graph_rag.graphiti_service import (
    get_graphiti_service,
    reset_graphiti_service,
)


load_dotenv()

ENABLE_DISK_BACKEND = "true"
OUTPUT_BASE_PATH = "outputs"


def _concatenate_drafts_to_final(workspace_path: str) -> str:
    """
    Concatenate all section drafts into a single final.md file.

    Scans for outputs/{timestamp}/section_*/draft.md files, sorts them by section number,
    and concatenates them into outputs/{timestamp}/final.md.

    Args:
        workspace_path: Path to the workspace directory (e.g., outputs/20260206_081222)

    Returns:
        Path to the created final.md file
    """
    import glob
    import re

    # Find all section draft files
    pattern = os.path.join(workspace_path, "section_*", "draft.md")
    draft_files = glob.glob(pattern)

    if not draft_files:
        logger.warning(f"No draft files found matching pattern: {pattern}")
        return ""

    # Sort by section number (extract number from section_N)
    def extract_section_num(path: str) -> int:
        match = re.search(r"section_(\d+)", path)
        return int(match.group(1)) if match else 0

    draft_files.sort(key=extract_section_num)

    # Concatenate all drafts
    combined_content = []
    for draft_path in draft_files:
        section_name = os.path.basename(os.path.dirname(draft_path))
        logger.info(f"Reading draft from {section_name}")
        try:
            with open(draft_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    combined_content.append(content)
        except Exception as e:
            logger.warning(f"Failed to read {draft_path}: {e}")

    # Write final.md
    final_path = os.path.join(workspace_path, "final.md")
    final_content = "\n\n---\n\n".join(combined_content)

    image_path_pattern = re.compile(r"outputs/\d{8}_\d{6}/images/")
    final_content = image_path_pattern.sub("./images/", final_content)

    with open(final_path, "w", encoding="utf-8") as f:
        f.write(final_content)

    logger.info(f"Created final.md with {len(draft_files)} sections at {final_path}")
    return final_path


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
        phase: 'build' for Graph RAG building (uses BuilderOrchestrator with Graphiti),
               'write' for Report writing

    Returns:
        For 'build' phase: tuple of (agent, orchestrator) for async graph processing
        For 'write' phase: agent only
    """
    custom_model = _create_model()

    if phase == "build":
        # 'build' phase now uses BuilderOrchestrator with iterative Graphiti pipeline
        logger.info("Creating Builder Orchestrator")
        orchestrator = create_builder_orchestrator(
            model=custom_model, session_id=session_id, output_base_path=OUTPUT_BASE_PATH
        )
        # Return both agent and orchestrator for async processing
        return orchestrator.create(), orchestrator
    else:
        logger.info("Creating Report Writer agent (Write Phase)")
        return (
            create_writer_orchestrator(
                model=custom_model,
                session_id=session_id,
                output_base_path=OUTPUT_BASE_PATH,
            ),
            None,
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
        else:
            user_input = "Báo cáo tài chính về VNINDEX tháng 12/2025"
            # Note: No longer clearing graph - using group_id namespacing instead

        phase_start_time = time.time()

        logger.info("=" * 60)
        if current_phase == "build":
            logger.info(f"PHASE 1: Build Knowledge Graph (session_id={session_id})")
            # Clear graph before building a new one
            clear_start = time.time()

            async def clear_graph_before_build():
                service = await get_graphiti_service()
                await service.clear_graph()
                # Note: Don't call service.close() here - Graphiti runs background tasks
                # (like build_indices_and_constraints) that need the connection open.
                # The "coroutine was never awaited" warning is benign.

            # Reset singleton before new asyncio.run() to handle event loop change
            reset_graphiti_service()
            asyncio.run(clear_graph_before_build())
            logger.info(
                f"Cleared existing graph data in {time.time() - clear_start:.2f}s"
            )
        else:
            logger.info("PHASE 2: Write Report")
            with open("engine/outline_vnindex.md", "r", encoding="utf-8") as f:
                outline = f.read()
            user_input = f"Viết báo cáo tài chính về VNINDEX tháng 12/2025 theo outline sau:\n\n{outline}"
        logger.info("=" * 60)

        agent, orchestrator = _create_agent(
            session_id=session_id if ENABLE_DISK_BACKEND else None, phase=current_phase
        )

        if ENABLE_DISK_BACKEND and hasattr(agent, "_workspace_path"):
            os.environ["OUTPUT_DIR"] = agent._workspace_path

        logger.info(f"Starting agent invocation with input: {user_input}")
        agent_start_time = time.time()

        try:
            result = agent.invoke(
                {"messages": [{"role": "user", "content": user_input}]}
            )
            agent_duration = time.time() - agent_start_time
            logger.info(f"⏱️ Agent invocation completed in {agent_duration:.2f}s")

            # After write phase, concatenate section drafts into final.md
            if current_phase == "write" and hasattr(agent, "_workspace_path"):
                try:
                    final_path = _concatenate_drafts_to_final(agent._workspace_path)
                    if final_path:
                        logger.info(f"✅ Created final report: {final_path}")
                except Exception as e:
                    logger.warning(f"Failed to concatenate drafts: {e}")

            if orchestrator is not None:
                try:
                    # Graph is now built synchronously in the tool
                    # Just log final stats and communities
                    finalize_start = time.time()

                    async def get_final_stats(group_id: str):
                        service = await get_graphiti_service()
                        stats = await service.get_graph_stats(group_id=group_id)
                        communities = await service.get_communities(group_id=group_id)
                        return stats, communities

                    reset_graphiti_service()
                    graph_stats, communities = asyncio.run(get_final_stats(session_id))
                    finalize_duration = time.time() - finalize_start

                    logger.info(f"Build phase complete - Graph stats: {graph_stats}")
                    logger.info(f"Communities: {len(communities)}")

                    # Log detailed information about each community
                    for i, community in enumerate(communities, 1):
                        logger.info(f"Community {i}: {community.get('name', 'N/A')}")
                        logger.info(f"  - Entities: {community.get('entity_count', 0)}")

                    # Log total phase time
                    total_phase_duration = time.time() - phase_start_time
                    logger.info(f"\n{'='*60}")
                    logger.info(
                        f"⏱️ TOTAL BUILD PHASE: {total_phase_duration:.2f}s ({total_phase_duration/60:.1f} min)"
                    )
                    logger.info(f"   - Agent invocation: {agent_duration:.2f}s")
                    logger.info(f"   - Final stats: {finalize_duration:.2f}s")
                    logger.info(f"{'='*60}")
                except Exception as e:
                    logger.warning(f"Failed to get final graph stats: {e}")

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
            print("=" * 80)

        except Exception as e:
            logger.error(f"Error during execution of phase {current_phase}: {e}")
            import traceback

            traceback.print_exc()
