"""Dataset-driven report generation helpers."""

import csv
from datetime import datetime
from pathlib import Path

from deepfishy.infra.config.paths import PROJECT_ROOT, resolve_project_path
from deepfishy.shared.logging import logger
from utils.convert_md_to_pdf import convert_md_to_pdf

INPUT_TEMPLATE = "Hãy giúp tôi viết một báo cáo nghiên cứu chi tiết về tài chính doanh nghiệp của {topic}. Báo cáo cần phong phú cả về nội dung văn bản lẫn các biểu đồ minh họa. Đồng thời, hãy cung cấp danh mục trích dẫn tài liệu tham khảo theo chuẩn ở cuối báo cáo (bao gồm số thứ tự và các nguồn tài liệu tương ứng). Bắt đầu viết báo cáo ngay và trả về toàn bộ nội dung."
DATASET_OUTPUT_DIR = PROJECT_ROOT / "benchmark" / "generated_reports" / "deepfishy"


def format_user_input(topic: str) -> str:
    """Format the standard research prompt for a topic."""
    return INPUT_TEMPLATE.format(topic=topic)


def resolve_input_path(path_str: str) -> Path:
    """Resolve a user-provided path relative to the project root when needed."""
    return resolve_project_path(path_str)


def normalize_row_keys(row: dict[str, str]) -> dict[str, str]:
    """Normalize CSV headers so `Topic` and `topic` behave the same."""
    return {str(key).strip().lower(): value for key, value in row.items()}


def load_dataset_rows(dataset_path: str) -> list[dict[str, str]]:
    """Load dataset rows from CSV with case-insensitive headers."""
    resolved_path = resolve_input_path(dataset_path)
    if not resolved_path.exists():
        raise FileNotFoundError(f"Dataset file not found: {resolved_path}")

    with open(resolved_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [normalize_row_keys(row) for row in reader]

    logger.info(f"Loaded {len(rows)} row(s) from dataset: {resolved_path}")
    return rows


def run_dataset_generation(dataset_path: str) -> None:
    """Generate reports for each dataset topic and export them as PDFs."""
    rows = load_dataset_rows(dataset_path)
    if not rows:
        raise ValueError("Dataset is empty.")

    DATASET_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Delay this import to avoid a circular dependency while engine.main still
    # owns the single-report workflow implementation.
    from engine.main import run_engine

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
            user_input=format_user_input(topic),
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


__all__ = [
    "DATASET_OUTPUT_DIR",
    "format_user_input",
    "load_dataset_rows",
    "normalize_row_keys",
    "resolve_input_path",
    "run_dataset_generation",
]
