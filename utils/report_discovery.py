"""Auto-discover report files from output directories."""

from pathlib import Path

from core.logging import logger
from utils.pdf_helpers import load_report_as_pdf

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def discover_reports(reports_dir: str) -> list[dict]:
    """Scan timestamped directories for final.md or final_report.md.

    Returns:
        List of dicts with 'filename' (str) and 'pdf_bytes' (bytes).
    """
    base = PROJECT_ROOT / reports_dir
    if not base.exists():
        logger.warning(f"Reports directory not found: {base}")
        return []

    reports = []
    for entry in sorted(base.iterdir()):
        if not entry.is_dir():
            continue

        for name in ["final.md", "final_report.md"]:
            report_file = entry / name
            if report_file.exists():
                report_id = f"{entry.name}/{name}"
                logger.info(f"  Converting report: {report_id}")

                pdf_bytes = load_report_as_pdf(report_file)
                if pdf_bytes:
                    reports.append({"filename": report_id, "pdf_bytes": pdf_bytes})
                    logger.info(f"    -> PDF ready ({len(pdf_bytes):,} bytes)")
                break

    return reports
