"""Single-report generation workflow for DeepFishy reports."""

import argparse
import asyncio
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from langchain_core.language_models.chat_models import BaseChatModel

from deepfishy.features.reports.application.finalize_report import (
    concatenate_drafts_to_final,
)
from deepfishy.infra.config.paths import OUTPUTS_DIR, PROJECT_ROOT
from deepfishy.shared.logging import logger
from deepfishy.shared.pdf.converter import convert_md_to_pdf
from deepfishy.shared.tracing import traceable_chain
from engine.orchestrators.builder import create_builder_orchestrator
from engine.orchestrators.classifier import classify_topic
from engine.orchestrators.writer import create_writer_orchestrator
from engine.tools.normalizer import finalize_staged_facts_to_graph
from engine.tools.validate_drafts import validate_drafts
from graph_rag.graphiti_service import get_graphiti_service, reset_graphiti_service
from deepfishy.infra.config.model_registry import get_default_llm_name
from deepfishy.infra.llm.chat_factory import create_llm_client

load_dotenv()

ENABLE_DISK_BACKEND = "true"
OUTPUT_BASE_PATH = str(OUTPUTS_DIR.relative_to(PROJECT_ROOT))
DEFAULT_TOPIC = "Ngân hàng TMCP Quân đội (MBBank – MBB) trong giai đoạn 2025–2026"


def materialize_outline_to_drafts(workspace_path: str, outline_text: str) -> int:
    """Create section_N/draft.md files from outline markdown as a fallback."""
    text = (outline_text or "").strip()
    if not text:
        return 0

    lines = text.splitlines()
    section_starts = [index for index, line in enumerate(lines) if line.startswith("## ")]

    sections: list[str] = []
    if section_starts:
        for index, start in enumerate(section_starts):
            end = section_starts[index + 1] if index + 1 < len(section_starts) else len(lines)
            chunk = "\n".join(lines[start:end]).strip()
            if chunk:
                sections.append(chunk)
    else:
        sections = [text]

    created = 0
    for index, content in enumerate(sections, start=1):
        section_dir = os.path.join(workspace_path, f"section_{index}")
        os.makedirs(section_dir, exist_ok=True)
        draft_path = os.path.join(section_dir, "draft.md")
        with open(draft_path, "w", encoding="utf-8") as file_handle:
            file_handle.write(content + "\n")
        created += 1

    logger.warning(
        f"Fallback activated: materialized {created} draft(s) directly from outline at {workspace_path}"
    )
    return created


def extract_text_from_content(content) -> str:
    """Extract text from modern LLM message content blocks."""
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text" and "text" in block:
                    text_parts.append(block["text"])
            elif isinstance(block, str):
                text_parts.append(block)

        return "\n".join(text_parts) if text_parts else str(content)

    return str(content)


def create_model() -> Optional[BaseChatModel]:
    """Initialize the default chat model from the shared model registry."""
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


def create_agent(session_id: Optional[str] = None, phase: str = "write"):
    """Create the phase-specific orchestrator and agent."""
    custom_model = create_model()

    if phase == "build":
        logger.info("Creating Builder Orchestrator")
        orchestrator = create_builder_orchestrator(
            model=custom_model,
            session_id=session_id,
            output_base_path=OUTPUT_BASE_PATH,
        )
        return orchestrator.create(), orchestrator

    logger.info("Creating Report Writer agent (Write Phase)")
    return (
        create_writer_orchestrator(
            model=custom_model,
            session_id=session_id,
            output_base_path=OUTPUT_BASE_PATH,
        ),
        None,
    )


@traceable_chain("report_generation")
def run_engine(
    user_input: str,
    session_id: Optional[str] = None,
    phases: list[str] | None = None,
) -> str:
    """Run the build/write report pipeline and return the final markdown path."""
    if phases is None:
        phases = ["build", "write"]
    if phases == ["write"] and not session_id:
        raise ValueError(
            "Write-only mode requires --session so the engine can reuse outputs/{session_id}."
        )
    if session_id is None:
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    logger.info("Classifying topic...")
    custom_model = create_model()
    topic_type = classify_topic(custom_model, user_input)

    if topic_type == "1":
        template_path = Path("templates/company_outline.md")
        logger.info("Topic classified as COMPANY. Using company outline template.")
    elif topic_type == "2":
        template_path = Path("templates/industry_outline.md")
        logger.info("Topic classified as INDUSTRY. Using industry outline template.")
    else:
        template_path = Path("templates/company_outline.md")
        logger.info(f"Topic unknown. Falling back to default outline: {template_path}")

    template_outline = ""
    try:
        template_outline = template_path.read_text(encoding="utf-8")
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
            user_input_for_phase = (
                f"{user_input}\n\n"
                "Vui lòng sử dụng template outline sau đây làm cơ sở cấu trúc khi xây dựng report outline cuối cùng:\n\n"
                f"{template_outline}"
            )
        else:
            logger.info("PHASE 2: Write Report")
            if build_outline:
                outline = build_outline
                logger.info("Using outline generated from build phase")
            else:
                workspace_path = os.path.join(OUTPUT_BASE_PATH, session_id)
                existing_outline_path = os.path.join(workspace_path, "outline.md")
                if os.path.exists(existing_outline_path):
                    with open(existing_outline_path, "r", encoding="utf-8") as file_handle:
                        outline = file_handle.read()
                    logger.info(
                        f"Using existing outline from prior build run: {existing_outline_path}"
                    )
                else:
                    logger.warning(
                        f"No build outline available, and no existing outline at {existing_outline_path}. Falling back to {template_path}"
                    )
                    outline = template_outline
            outline_for_write = outline

            workspace_path = os.path.join(OUTPUT_BASE_PATH, session_id)
            os.makedirs(workspace_path, exist_ok=True)
            outline_path = os.path.join(workspace_path, "outline.md")
            with open(outline_path, "w", encoding="utf-8") as file_handle:
                file_handle.write(outline)
            logger.info(f"Wrote outline ({len(outline)} chars) to {outline_path}")

            user_input_for_phase = (
                "Viết báo cáo tài chính theo outline được lưu tại `/outline.md`.\n"
                "Đọc file đó trước khi bắt đầu. "
                "Số lượng section trong outline xác định số lượng section_N/draft.md cần tạo."
            )
        logger.info("=" * 60)

        agent, orchestrator = create_agent(
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
            logger.info(f"Agent invocation completed in {agent_duration:.2f}s")

            if current_phase == "write" and hasattr(agent, "_workspace_path"):
                try:
                    validation = validate_drafts(agent._workspace_path)
                    if validation["warnings"]:
                        for warning in validation["warnings"]:
                            logger.warning(f"Draft validation: {warning}")
                    if validation["errors"]:
                        for error in validation["errors"]:
                            logger.error(f"Draft validation: {error}")
                        if "No draft files found" in validation["errors"]:
                            materialize_outline_to_drafts(
                                agent._workspace_path, outline_for_write
                            )
                            validation = validate_drafts(agent._workspace_path)
                            if validation["errors"]:
                                for error in validation["errors"]:
                                    logger.error(
                                        f"Draft validation after fallback: {error}"
                                    )

                    final_path = concatenate_drafts_to_final(agent._workspace_path)
                    if final_path:
                        logger.info(f"Created final report: {final_path}")
                        pdf_path = str(Path(final_path).with_suffix(".pdf"))
                        with open(final_path, "r", encoding="utf-8") as file_handle:
                            final_md_content = file_handle.read()
                        convert_md_to_pdf(
                            final_md_content,
                            pdf_path,
                            base_path=str(Path(final_path).resolve().parent),
                        )
                        if Path(pdf_path).exists():
                            logger.info(f"Created final PDF: {pdf_path}")
                        else:
                            logger.error(f"PDF conversion did not create {pdf_path}")
                except Exception as error:
                    logger.warning(f"Failed to finalize report outputs: {error}")

            if orchestrator is not None:
                try:
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
                    logger.info(f"\n{'=' * 60}")
                    logger.info(
                        f"TOTAL BUILD PHASE: {total_phase_duration:.2f}s ({total_phase_duration / 60:.1f} min)"
                    )
                    logger.info(f"   - Agent invocation: {agent_duration:.2f}s")
                    logger.info(f"   - Final stats: {finalize_duration:.2f}s")
                    logger.info(f"{'=' * 60}")
                except Exception as error:
                    logger.warning(f"Failed to get final graph stats: {error}")

            if not result.get("messages"):
                logger.error("No messages found in result!")
                logger.error(f"Result structure: {result}")
                print("ERROR: No response from agent")
                continue

            final_response_raw = result["messages"][-1].content
            final_response = extract_text_from_content(final_response_raw)

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

        except Exception as error:
            logger.error(f"Error during execution of phase {current_phase}: {error}")
            import traceback

            traceback.print_exc()

    return final_path


def build_parser() -> argparse.ArgumentParser:
    """Build the legacy engine CLI parser."""
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
    return parser


__all__ = [
    "DEFAULT_TOPIC",
    "build_parser",
    "create_agent",
    "create_model",
    "extract_text_from_content",
    "materialize_outline_to_drafts",
    "run_engine",
]
