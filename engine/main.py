import os
import re
import csv
import time
import glob
import asyncio
import argparse
from typing import Any, Optional
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

from langchain_core.language_models.chat_models import BaseChatModel

from deepfishy.infra.config.paths import OUTPUTS_DIR, PROJECT_ROOT, resolve_project_path
from deepfishy.shared.logging import logger
from engine.orchestrators.writer import create_writer_orchestrator
from engine.orchestrators.builder import create_builder_orchestrator
from engine.tools.validate_drafts import validate_drafts
from engine.orchestrators.classifier import classify_topic
from engine.tools.normalizer import finalize_staged_facts_to_graph

from utils.load_config import get_default_llm_name
from utils.convert_md_to_pdf import convert_md_to_pdf
from utils.model_factory import create_llm_client

from graph_rag.graphiti_service import (
    get_graphiti_service,
    reset_graphiti_service,
)

load_dotenv()

ENABLE_DISK_BACKEND = "true"
OUTPUT_BASE_PATH = str(OUTPUTS_DIR.relative_to(PROJECT_ROOT))
DEFAULT_TOPIC = "Ngân hàng TMCP Quân đội (MBBank – MBB) trong giai đoạn 2025–2026"
INPUT_TEMPLATE = "Hãy giúp tôi viết một báo cáo nghiên cứu chi tiết về tài chính doanh nghiệp của {topic}. Báo cáo cần phong phú cả về nội dung văn bản lẫn các biểu đồ minh họa. Đồng thời, hãy cung cấp danh mục trích dẫn tài liệu tham khảo theo chuẩn ở cuối báo cáo (bao gồm số thứ tự và các nguồn tài liệu tương ứng). Bắt đầu viết báo cáo ngay và trả về toàn bộ nội dung."
DATASET_OUTPUT_DIR = PROJECT_ROOT / "benchmark" / "generated_reports" / "deepfishy"


def _format_user_input(topic: str) -> str:
    """Format the standard research prompt for a topic."""
    return INPUT_TEMPLATE.format(topic=topic)


def _resolve_input_path(path_str: str) -> Path:
    """Resolve a user-provided path relative to the project root when needed."""
    return resolve_project_path(path_str)


def _normalize_row_keys(row: dict[str, str]) -> dict[str, str]:
    """Normalize CSV headers so `Topic` and `topic` behave the same."""
    return {str(key).strip().lower(): value for key, value in row.items()}


def _load_dataset_rows(dataset_path: str) -> list[dict[str, str]]:
    """Load dataset rows from CSV with case-insensitive headers."""
    resolved_path = _resolve_input_path(dataset_path)
    if not resolved_path.exists():
        raise FileNotFoundError(f"Dataset file not found: {resolved_path}")

    with open(resolved_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [_normalize_row_keys(row) for row in reader]

    logger.info(f"Loaded {len(rows)} row(s) from dataset: {resolved_path}")
    return rows


def run_dataset_generation(dataset_path: str) -> None:
    """Generate reports for each dataset topic and export them as PDFs."""
    rows = _load_dataset_rows(dataset_path)
    if not rows:
        raise ValueError("Dataset is empty.")

    DATASET_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for index, row in enumerate(rows, start=1):
        row_id = (row.get("id") or "").strip() or str(index)
        topic = (row.get("topic") or "").strip()
        output_path = DATASET_OUTPUT_DIR / f"topic_{index}.pdf"

        if not topic:
            logger.warning(
                f"Skipping dataset row {row_id}: missing 'topic' value after header normalization."
            )
            continue

        logger.info("=" * 60)
        logger.info(f"DATASET ROW {row_id}: {topic}")
        logger.info("=" * 60)

        session_id = f"dataset_{run_timestamp}/topic_{index}"
        final_md_path = run_engine(
            user_input=_format_user_input(topic),
            session_id=session_id,
        )

        if not final_md_path:
            logger.error(f"Row {row_id}: Engine failed to produce final.md.")
            continue

        with open(final_md_path, "r", encoding="utf-8") as f:
            final_md_content = f.read()

        convert_md_to_pdf(
            final_md_content,
            str(output_path),
            base_path=str(Path(final_md_path).resolve().parent),
        )
        if output_path.exists():
            logger.info(f"Converted final.md to PDF at {output_path}")
        else:
            logger.error(f"Row {row_id}: PDF conversion did not create {output_path}")


def _split_section_references(section_markdown: str) -> tuple[str, str]:
    match = re.search(
        r"(?im)^\s*###\s+references\s*$", section_markdown or "", flags=re.MULTILINE
    )
    if not match:
        return (section_markdown or "").strip(), ""
    body = (section_markdown or "")[: match.start()].rstrip()
    references = (section_markdown or "")[match.end() :].strip()
    return body, references


def _parse_reference_entries(reference_block: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []

    for raw_line in (reference_block or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        local_id: Optional[int] = None
        bracketed_match = re.match(r"^\[(\d+)\]\s*", line)
        ordered_match = re.match(r"^(\d+)\.\s*", line)
        if bracketed_match:
            local_id = int(bracketed_match.group(1))
            line = line[bracketed_match.end() :].strip()
        elif ordered_match:
            local_id = int(ordered_match.group(1))
            line = line[ordered_match.end() :].strip()

        url = ""
        title = line

        markdown_url_match = re.search(r"\[([^\]]+)\]\((https?://[^)]+)\)", line)
        if markdown_url_match:
            url = markdown_url_match.group(2).strip()
            title_prefix = line[: markdown_url_match.start()].strip()
            title = (
                title_prefix.rstrip(":").strip()
                or markdown_url_match.group(1).strip()
                or url
            )
        else:
            plain_url_match = re.search(r"(https?://\S+?)(?=[.,;)]*(?:\s|$))", line)
            if plain_url_match:
                url = plain_url_match.group(1)
                title = line[: plain_url_match.start()].rstrip(": ").strip() or url
            else:
                title = line.rstrip(":").strip()

        if local_id is None and not title and not url:
            continue

        entries.append(
            {
                "local_id": local_id,
                "title": title or url or "Unknown source",
                "url": url,
            }
        )

    return entries


def _reference_key(reference: dict[str, Any]) -> str:
    url = str(reference.get("url", "")).strip().lower()
    if url:
        return f"url::{url}"
    title = re.sub(r"\s+", " ", str(reference.get("title", "")).strip().lower())
    return f"title::{title}"


def _reference_title_score(title: str) -> tuple[int, int]:
    cleaned = str(title or "").strip()
    if not cleaned:
        return (0, 0)
    generic = cleaned.lower() in {"unknown source", "source", "nguon", "nguồn"}
    looks_like_url = cleaned.startswith("http://") or cleaned.startswith("https://")
    return (
        0 if generic or looks_like_url else 1,
        len(cleaned),
    )


def _renumber_inline_citations(
    section_body: str, local_to_global: dict[int, int]
) -> str:
    if not local_to_global:
        return section_body

    def replace_match(match: re.Match[str]) -> str:
        raw_numbers = match.group(1)
        numbers = [part.strip() for part in raw_numbers.split(",") if part.strip()]
        remapped: list[str] = []
        seen = set()
        for number in numbers:
            try:
                mapped = int(local_to_global.get(int(number), int(number)))
            except ValueError:
                return match.group(0)
            if mapped in seen:
                continue
            seen.add(mapped)
            remapped.append(str(mapped))

        if not remapped:
            return match.group(0)
        return f"[{', '.join(remapped)}]"

    return re.sub(r"\[(\d+(?:\s*,\s*\d+)*)\](?!\()", replace_match, section_body)


def _normalize_report_references(
    sections: list[str],
) -> tuple[list[str], list[dict[str, Any]]]:
    normalized_sections: list[str] = []
    global_references: list[dict[str, Any]] = []
    reference_key_to_index: dict[str, int] = {}

    for section in sections:
        body, reference_block = _split_section_references(section)
        local_references = _parse_reference_entries(reference_block)
        local_to_global: dict[int, int] = {}

        for reference in local_references:
            key = _reference_key(reference)
            if key in {"url::", "title::"}:
                continue

            global_index = reference_key_to_index.get(key)
            if global_index is None:
                global_index = len(global_references) + 1
                reference_key_to_index[key] = global_index
                global_references.append(
                    {
                        "index": global_index,
                        "title": str(reference.get("title", "")).strip()
                        or "Unknown source",
                        "url": str(reference.get("url", "")).strip(),
                    }
                )
            else:
                existing = global_references[global_index - 1]
                current_title = str(reference.get("title", "")).strip()
                if _reference_title_score(current_title) > _reference_title_score(
                    str(existing.get("title", "")).strip()
                ):
                    existing["title"] = current_title
                if not str(existing.get("url", "")).strip():
                    existing["url"] = str(reference.get("url", "")).strip()

            local_id = reference.get("local_id")
            if isinstance(local_id, int):
                local_to_global[local_id] = global_index

        normalized_sections.append(
            _renumber_inline_citations(body.strip(), local_to_global).strip()
        )

    return normalized_sections, global_references


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

    # Concatenate all drafts and normalize references into one global list
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

    normalized_sections, global_references = _normalize_report_references(
        combined_content
    )

    reference_lines: list[str] = []
    if global_references:
        reference_lines.extend(["## References", ""])
        for reference in global_references:
            url = str(reference.get("url", "")).strip()
            title = str(reference.get("title", "")).strip() or url or "Unknown source"
            index = int(reference.get("index", 0) or 0)
            if url:
                reference_lines.append(f"[{index}] {title}: [{url}]({url})")
            else:
                reference_lines.append(f"[{index}] {title}")

    final_path = os.path.join(workspace_path, "final.md")
    final_parts = [part for part in normalized_sections if part.strip()]
    if reference_lines:
        final_parts.append("\n".join(reference_lines).strip())
    final_content = "\n\n---\n\n".join(final_parts)

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
        "--dataset",
        type=str,
        default=None,
        help="Path to a dataset CSV. Generates one report per topic and saves them to benchmark/generated_reports/deepfishy/topic_{n}.pdf.",
    )
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

    if args.dataset:
        if args.phase or args.session:
            parser.error("--dataset cannot be combined with --phase or --session.")
        run_dataset_generation(args.dataset)
        raise SystemExit(0)

    phases = [args.phase] if args.phase else None
    topic = args.topic or DEFAULT_TOPIC
    user_input = _format_user_input(topic)

    run_engine(user_input=user_input, session_id=args.session, phases=phases)
