"""Parsing and persistence helpers for benchmark evaluation."""

import json
import re
from datetime import datetime
from pathlib import Path

from deepfishy.infra.config.paths import PROJECT_ROOT, resolve_project_path
from deepfishy.shared.logging import logger
from deepfishy.shared.pdf.helpers import load_report_as_pdf

BENCHMARK_DIMENSIONS = [
    "cons",
    "faith",
    "t_i",
    "rich",
    "cover",
    "ins",
    "logic",
    "lang",
    "vis",
]


def parse_json_response(response_text: str) -> dict | None:
    """Extract and parse JSON from an LLM response."""
    json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", response_text, re.DOTALL)
    json_str = json_match.group(1).strip() if json_match else response_text.strip()

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as error:
        logger.error(f"Failed to parse JSON response: {error}")
        logger.debug(f"Raw response:\n{response_text[:500]}...")
        return None


def compute_averages(evaluation: dict) -> dict:
    """Compute overall average score for each report evaluation."""
    for report_eval in evaluation.get("evaluations", []):
        scores = report_eval.get("scores", {})
        score_values = [
            dimension.get("score", 0)
            for dimension in scores.values()
            if isinstance(dimension, dict)
        ]
        if score_values:
            report_eval["overall_average"] = round(
                sum(score_values) / len(score_values), 2
            )
    return evaluation


def save_results(results: dict, results_dir: str) -> str:
    """Save evaluation results to a timestamped JSON file."""
    output_dir = resolve_project_path(results_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"{timestamp}_results.json"
    with open(output_path, "w", encoding="utf-8") as file_handle:
        json.dump(results, file_handle, ensure_ascii=False, indent=2)

    return str(output_path)


def print_results_table(results: dict) -> None:
    """Print a formatted summary table of evaluation results."""
    evaluations = results.get("evaluations", [])
    if not evaluations:
        print("No evaluations found.")
        return

    dim_short = ["Cons", "Faith", "T-I", "Rich", "Cover", "Ins", "Logic", "Lang", "Vis"]
    header = (
        f"{'Report ID':<30} " + " ".join(f"{dimension:>5}" for dimension in dim_short) + f" {'AVG':>8}"
    )
    print("\n" + "=" * len(header))
    print("BENCHMARK EVALUATION RESULTS")
    print("=" * len(header))
    print(header)
    print("-" * len(header))

    for evaluation in evaluations:
        report_id = evaluation.get("report_id", "unknown")
        if len(report_id) > 28:
            report_id = "..." + report_id[-25:]

        scores_dict = evaluation.get("scores", {})
        scores = [
            f"{scores_dict.get(dimension, {}).get('score', '-'):>5}"
            for dimension in BENCHMARK_DIMENSIONS
        ]

        average = evaluation.get("overall_average", "-")
        average_str = (
            f"{average:>8.2f}" if isinstance(average, (int, float)) else f"{average:>8}"
        )
        print(f"{report_id:<30} " + " ".join(scores) + f" {average_str}")

    print("=" * len(header))


def discover_reports(reports_dir: str) -> list[dict]:
    """Scan timestamped directories for final markdown reports and load them as PDFs."""
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


__all__ = [
    "BENCHMARK_DIMENSIONS",
    "compute_averages",
    "discover_reports",
    "parse_json_response",
    "print_results_table",
    "save_results",
]
