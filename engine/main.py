import os
import re
import time
import glob
import asyncio
import argparse
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage

from core.logging import logger
from engine.prompts.refiner_prompt import REFINER_SYSTEM_PROMPT
from engine.orchestrators.writer import create_writer_orchestrator
from engine.orchestrators.builder import create_builder_orchestrator
from engine.tools.validate_drafts import validate_drafts
from engine.orchestrators.classifier import classify_topic
from engine.tools.normalizer import finalize_staged_facts_to_graph

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
        except (IOError, FileNotFoundError) as e:
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


def _materialize_outline_to_drafts(workspace_path: str, outline_text: str) -> int:
    """Create section_N/draft.md files from outline markdown as a fallback.

    Splits by level-2 headers (`## `). If none exist, writes a single section_1/draft.md.
    Returns the number of draft files created.
    """
    text = (outline_text or "").strip()
    if not text:
        return 0

    lines = text.splitlines()
    section_starts = [i for i, ln in enumerate(lines) if ln.startswith("## ")]

    sections: list[str] = []
    if section_starts:
        for idx, start in enumerate(section_starts):
            end = (
                section_starts[idx + 1] if idx + 1 < len(section_starts) else len(lines)
            )
            chunk = "\n".join(lines[start:end]).strip()
            if chunk:
                sections.append(chunk)
    else:
        sections = [text]

    created = 0
    for i, content in enumerate(sections, start=1):
        section_dir = os.path.join(workspace_path, f"section_{i}")
        os.makedirs(section_dir, exist_ok=True)
        draft_path = os.path.join(section_dir, "draft.md")
        with open(draft_path, "w", encoding="utf-8") as f:
            f.write(content + "\n")
        created += 1

    logger.warning(
        f"Fallback activated: materialized {created} draft(s) directly from outline at {workspace_path}"
    )
    return created


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


def _refine_final_markdown_for_pdf(
    final_md_path: str, model: Optional[BaseChatModel]
) -> str:
    """Refine final markdown for Vietnamese quality and PDF/LaTeX compatibility.

    Preserves the original `final.md` and writes refined content to
    `<workspace>/final_refined.md`.
    Returns the path to the refined output file (`final_refined.md`).
    """
    if not model:
        logger.warning("Skipping final refinement: model is unavailable.")
        return final_md_path

    if not final_md_path or not os.path.exists(final_md_path):
        logger.warning(f"Skipping final refinement: file not found: {final_md_path}")
        return final_md_path

    try:
        with open(final_md_path, "r", encoding="utf-8") as f:
            original = f.read()
    except (IOError, OSError) as e:
        logger.warning(f"Skipping final refinement: cannot read file: {e}")
        return final_md_path

    if not original.strip():
        logger.warning("Skipping final refinement: final.md is empty.")
        return final_md_path

    try:
        response = model.invoke(
            [
                SystemMessage(content=REFINER_SYSTEM_PROMPT),
                HumanMessage(content=original),
            ]
        )
        refined = _extract_text_from_content(response.content).strip()
    except Exception as e:
        logger.warning(f"Final refinement failed during model invocation: {e}")
        return final_md_path

    if not refined:
        logger.warning(
            "Final refinement produced empty output. Keeping original final.md"
        )
        return final_md_path

    workspace_path = os.path.dirname(final_md_path)
    backup_path = os.path.join(workspace_path, "final.raw.md")
    refined_copy_path = os.path.join(workspace_path, "final_refined.md")

    try:
        with open(backup_path, "w", encoding="utf-8") as f:
            f.write(original)
        with open(refined_copy_path, "w", encoding="utf-8") as f:
            f.write(refined + "\n")
        logger.info(
            f"Final refinement complete. Original preserved at {final_md_path}; backup: {backup_path}; refined copy: {refined_copy_path}"
        )
    except (IOError, OSError) as e:
        logger.warning(f"Failed to persist refined final markdown: {e}")
        return final_md_path

    return refined_copy_path


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


def _create_agent(
    session_id: Optional[str] = None,
    phase: str = "write",
):
    """Factory function to create the agent with lazy initialization.

    Args:
        session_id: Session ID for workspace path (may contain '/').
        phase: 'build' or 'write'.
    """
    custom_model = _create_model()

    if phase == "build":
        logger.info("Creating Builder Orchestrator")
        orchestrator = create_builder_orchestrator(
            model=custom_model,
            session_id=session_id,
            output_base_path=OUTPUT_BASE_PATH,
        )
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


def run_engine(
    user_input: str,
    session_id: Optional[str] = None,
    phases: list[str] = None,
) -> str:
    """Run the engine pipeline (build + write) and return path to final.md.

    Args:
        user_input: Research question / user query for the agent.
        session_id: Session ID that determines output directory
                    (outputs/{session_id}/). Auto-generated if None.
        phases: List of phases to run. Defaults to ["build", "write"].

    Returns:
        Path to the generated final.md file, or empty string on failure.
    """
    if phases is None:
        phases = ["build", "write"]
    if phases == ["write"] and not session_id:
        raise ValueError(
            "Write-only mode requires --session so the engine can reuse outputs/{session_id}."
        )
    if session_id is None:
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    logger.info("Classifying topic...")
    custom_model = _create_model()
    topic_type = classify_topic(custom_model, user_input)

    if topic_type == "1":
        template_path = "templates/company_outline.md"
        logger.info("Topic classified as COMPANY. Using company outline template.")
    elif topic_type == "2":
        template_path = "templates/industry_outline.md"
        logger.info("Topic classified as INDUSTRY. Using industry outline template.")
    else:
        template_path = "templates/company_outline.md"
        logger.info(f"Topic unknown. Falling back to default outline: {template_path}")

    template_outline = ""
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            template_outline = f.read()
    except FileNotFoundError:
        logger.error(
            f"Template file not found: {template_path}. Proceeding with an empty outline."
        )

    build_outline = None
    final_path = ""
    outline_for_write = ""

    for current_phase in phases:
        if current_phase not in ["build", "write"]:
            logger.error(f"Invalid phase: {current_phase}. Must be 'build' or 'write'.")
            continue

        phase_start_time = time.time()

        logger.info("=" * 60)
        if current_phase == "build":
            logger.info(f"PHASE 1: Build Knowledge Graph (session_id={session_id})")
            clear_start = time.time()

            async def clear_graph_before_build():
                service = await get_graphiti_service()
                await service.clear_graph()

            reset_graphiti_service()
            asyncio.run(clear_graph_before_build())
            logger.info(
                f"Cleared existing graph data in {time.time() - clear_start:.2f}s"
            )
            user_input_for_phase = f"{user_input}\n\nVui lòng sử dụng template outline sau đây làm cơ sở cấu trúc khi xây dựng report outline cuối cùng:\n\n{template_outline}"
        else:
            logger.info("PHASE 2: Write Report")
            if build_outline:
                outline = build_outline
                logger.info("Using outline generated from build phase")
            else:
                workspace_path = os.path.join(OUTPUT_BASE_PATH, session_id)
                existing_outline_path = os.path.join(workspace_path, "outline.md")
                if os.path.exists(existing_outline_path):
                    with open(existing_outline_path, "r", encoding="utf-8") as f:
                        outline = f.read()
                    logger.info(
                        f"Using existing outline from prior build run: {existing_outline_path}"
                    )
                else:
                    logger.warning(
                        f"No build outline available, and no existing outline at {existing_outline_path}. Falling back to {template_path}"
                    )
                    outline = template_outline
            outline_for_write = outline

            # Write outline to file so writer reads it via tool (avoids large inline context)
            workspace_path = os.path.join(OUTPUT_BASE_PATH, session_id)
            os.makedirs(workspace_path, exist_ok=True)
            outline_path = os.path.join(workspace_path, "outline.md")
            with open(outline_path, "w", encoding="utf-8") as f:
                f.write(outline)
            logger.info(f"Wrote outline ({len(outline)} chars) to {outline_path}")

            user_input_for_phase = (
                "Viết báo cáo tài chính theo outline được lưu tại `/outline.md`.\n"
                "Đọc file đó trước khi bắt đầu. "
                "Số lượng section trong outline xác định số lượng section_N/draft.md cần tạo."
            )
        logger.info("=" * 60)

        agent, orchestrator = _create_agent(
            session_id=session_id if ENABLE_DISK_BACKEND else None,
            phase=current_phase,
        )

        if ENABLE_DISK_BACKEND and hasattr(agent, "_workspace_path"):
            os.environ["OUTPUT_DIR"] = agent._workspace_path

        logger.info(f"Starting agent invocation for phase {current_phase}.")
        agent_start_time = time.time()

        try:
            result = agent.invoke(
                {"messages": [{"role": "user", "content": user_input_for_phase}]}
            )
            agent_duration = time.time() - agent_start_time
            logger.info(f"⏱️ Agent invocation completed in {agent_duration:.2f}s")

            # After write phase, validate and concatenate section drafts into final.md
            if current_phase == "write" and hasattr(agent, "_workspace_path"):
                try:
                    # Validate drafts before concatenation
                    validation = validate_drafts(agent._workspace_path)
                    if validation["warnings"]:
                        for w in validation["warnings"]:
                            logger.warning(f"Draft validation: {w}")
                    if validation["errors"]:
                        for e in validation["errors"]:
                            logger.error(f"Draft validation: {e}")
                        if "No draft files found" in validation["errors"]:
                            _materialize_outline_to_drafts(
                                agent._workspace_path, outline_for_write
                            )
                            validation = validate_drafts(agent._workspace_path)
                            if validation["errors"]:
                                for e in validation["errors"]:
                                    logger.error(
                                        f"Draft validation after fallback: {e}"
                                    )

                    final_path = _concatenate_drafts_to_final(agent._workspace_path)
                    if final_path:
                        final_path = _refine_final_markdown_for_pdf(
                            final_path, custom_model
                        )
                        logger.info(f"✅ Created final report: {final_path}")
                except IOError as e:
                    logger.warning(f"Failed to concatenate drafts: {e}")

            if orchestrator is not None:
                try:
                    # Build graph once from all staged section facts after outline is finalized
                    finalize_result = finalize_staged_facts_to_graph()
                    logger.info(f"Final staged graph ingest result: {finalize_result}")

                    finalize_start = time.time()

                    async def get_final_stats():
                        service = await get_graphiti_service()
                        return await service.get_graph_stats()

                    reset_graphiti_service()
                    graph_stats = asyncio.run(get_final_stats())
                    finalize_duration = time.time() - finalize_start

                    logger.info(f"Build phase complete - Graph stats: {graph_stats}")

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

            if current_phase == "build":
                build_outline = final_response
                logger.info(
                    f"Captured build phase outline ({len(final_response)} chars)"
                )

            print("\n" + "=" * 80)
            print(f"AGENT RESPONSE ({current_phase.upper()} PHASE):")
            print("=" * 80)
            print(final_response)
            print("=" * 80)

        except Exception as e:
            logger.error(f"Error during execution of phase {current_phase}: {e}")
            import traceback

            traceback.print_exc()

    return final_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--phase",
        type=str,
        default=None,
        help="Phase to run: 'build' for Graph RAG building with Graphiti, 'write' for Report writing. If not specified, runs both in sequence.",
    )
    parser.add_argument(
        "--topic", type=str, default=None, help="User input/query for the agent"
    )
    parser.add_argument(
        "--session",
        type=str,
        default=None,
        help="Session ID to reuse output workspace (e.g., 20260323_205711). Required for --phase write.",
    )
    args = parser.parse_args()

    input_template = "Hãy giúp tôi viết một báo cáo nghiên cứu chi tiết về tài chính doanh nghiệp của {topic}. Báo cáo cần phong phú cả về nội dung văn bản lẫn các biểu đồ minh họa. Đồng thời, hãy cung cấp danh mục trích dẫn tài liệu tham khảo theo chuẩn ở cuối báo cáo (bao gồm số thứ tự và các nguồn tài liệu tương ứng). Bắt đầu viết báo cáo ngay và trả về toàn bộ nội dung."

    phases = [args.phase] if args.phase else None
    topic = (
        args.topic or "Ngân hàng TMCP Quân đội (MBBank – MBB) trong giai đoạn 2025–2026"
    )
    user_input = input_template.format(topic=topic)

    run_engine(user_input=user_input, session_id=args.session, phases=phases)
