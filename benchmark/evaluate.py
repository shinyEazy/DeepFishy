"""
Financial Report Benchmark Evaluator.

Evaluates generated reports against golden standard PDFs using an LLM judge.
Supports batch evaluation for a whole benchmark dataset via --dataset and
--report_dir, or single-report evaluation via --topic, --generated_report,
and --golden_report.

python benchmark/evaluate.py --dataset benchmark/dataset/dataset.csv --report_dir benchmark/generated_reports/deepfishy
python benchmark/evaluate.py --topic "Ngân hàng TMCP Quân đội (MBBank – MBB) trong giai đoạn 2025–2026" --generated_report outputs/test.pdf --golden_report benchmark/golden_reports/mbb.pdf
"""

import csv
import sys
import time
import yaml
import argparse
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
from core.logging import logger
from utils.model_factory import create_llm_client
from utils.load_config import get_deepfishy_defaults
from utils.pdf_helpers import load_report_as_pdf
from utils.response_parser import parse_json_response, compute_averages
from utils.results_io import save_results, print_results_table
from benchmark.prompt import (
    format_evaluation_prompt,
    RESEARCH_QUESTION,
    GOLDEN_REPORT_IRRELEVANT_METRICS_SYSTEM_PROMPT,
    GOLDEN_REPORT_RELEVANT_METRICS_SYSTEM_PROMPT,
)

# Setup path and encoding first
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Force UTF-8 for stdout/stderr to handle Vietnamese characters on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv()

MODEL_PRICING = {
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
    "gemini-2.5-flash-lite": {"input": 0.10, "output": 0.40},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-3-flash-preview": {"input": 0.30, "output": 2.50},
}

BENCHMARK_SCORE_DIMENSIONS = [
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


def _format_research_question(topic: str) -> str:
    """Format the benchmark research question robustly across placeholder styles."""
    return RESEARCH_QUESTION.format(topic=topic, TOPIC=topic)


def _resolve_project_path(path_str: str | Path) -> Path:
    """Resolve a user-provided path relative to the project root when needed."""
    path = Path(path_str)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _normalize_dataset_row(row: dict[str, str]) -> dict[str, str]:
    """Normalize CSV headers so casing differences do not break dataset parsing."""
    return {
        str(key).strip().lower(): (value or "").strip()
        for key, value in row.items()
        if key is not None
    }


def load_config(config_path: str = None) -> dict:
    """Load benchmark configuration from YAML file."""
    if config_path is None:
        config_path = PROJECT_ROOT / "benchmark" / "benchmark_config.yaml"
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_dataset(csv_path: str) -> list[dict]:
    """Load dataset CSV and return list of row dicts."""
    p = _resolve_project_path(csv_path)
    if not p.exists():
        logger.error(f"Dataset file not found: {p}")
        sys.exit(1)

    with open(p, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [_normalize_dataset_row(row) for row in reader]

    logger.info(f"Loaded {len(rows)} row(s) from {p.name}")
    return rows


def _extract_text(resp) -> str:
    """Extract text content from an LLM response."""
    response_text = resp.content
    if isinstance(response_text, list):
        response_text = "\n".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in response_text
        )
    return response_text


def _extract_usage(resp) -> tuple[int, int]:
    """Extract input and output token usage from an LLM response."""
    usage = resp.usage_metadata or {}
    return usage.get("input_tokens", 0), usage.get("output_tokens", 0)


def evaluate_generated_report(
    row_id: str,
    topic: str,
    research_question: str,
    report_path: str,
    golden_path: Path,
    model_name: str,
    results_dir: str,
    print_table: bool = True,
) -> dict | None:
    """Evaluate a single generated report against a golden standard using 2 LLM prompts and merge the metrics."""
    # Load generated report as PDF
    generated_pdf = load_report_as_pdf(Path(report_path))
    if generated_pdf is None:
        logger.error(f"Row {row_id}: Failed to convert generated report to PDF.")
        return None

    # Load golden report
    if not golden_path.exists():
        logger.error(f"Row {row_id}: Golden report not found: {golden_path}")
        return None

    golden_pdf = load_report_as_pdf(golden_path)
    if golden_pdf is None:
        logger.error(f"Row {row_id}: Failed to load golden report as PDF.")
        return None

    # Create LLM client
    llm = create_llm_client(model_name)
    if llm is None:
        logger.error(f"Row {row_id}: Failed to create LLM client: {model_name}")
        return None

    report_pdfs = [{"filename": report_path, "pdf_bytes": generated_pdf}]

    # Format 2 different prompts
    system_prompt_irrelevant = GOLDEN_REPORT_IRRELEVANT_METRICS_SYSTEM_PROMPT.format(
        RESEARCH_QUESTION=research_question
    )
    messages_irrelevant = format_evaluation_prompt(
        system_prompt=system_prompt_irrelevant,
        golden_pdf=golden_pdf,
        report_pdfs=report_pdfs,
    )

    messages_relevant = format_evaluation_prompt(
        system_prompt=GOLDEN_REPORT_RELEVANT_METRICS_SYSTEM_PROMPT,
        golden_pdf=golden_pdf,
        report_pdfs=report_pdfs,
    )

    logger.info(f"Row {row_id}: Calling LLM judge for 6 irrelevant metrics...")

    llm_start = time.time()
    try:
        response_irrelevant = llm.invoke(messages_irrelevant)
    except Exception as e:
        logger.error(f"Row {row_id}: LLM irrelevant invocation failed: {e}")
        return None

    logger.info(f"Row {row_id}: Calling LLM judge for 3 relevant metrics...")
    try:
        response_relevant = llm.invoke(messages_relevant)
    except Exception as e:
        logger.error(f"Row {row_id}: LLM relevant invocation failed: {e}")
        return None

    llm_duration = time.time() - llm_start

    text_irrelevant = _extract_text(response_irrelevant)
    text_relevant = _extract_text(response_relevant)

    input_tok_irr, output_tok_irr = _extract_usage(response_irrelevant)
    input_tok_rel, output_tok_rel = _extract_usage(response_relevant)

    input_tokens = input_tok_irr + input_tok_rel
    output_tokens = output_tok_irr + output_tok_rel
    total_tokens = input_tokens + output_tokens

    pricing = MODEL_PRICING.get(model_name, {"input": 0, "output": 0})
    total_cost = (input_tokens / 1_000_000) * pricing["input"] + (
        output_tokens / 1_000_000
    ) * pricing["output"]

    logger.info(
        f"  Time: {llm_duration:.2f}s | Tokens: {total_tokens:,} | Cost: ${total_cost:.4f}"
    )

    # Parse JSONs
    results_irrelevant = parse_json_response(text_irrelevant)
    results_relevant = parse_json_response(text_relevant)

    if results_irrelevant is None or results_relevant is None:
        save_results(
            {
                "error": "Failed to parse JSON",
                "raw_response_irr": text_irrelevant,
                "raw_response_rel": text_relevant,
            },
            results_dir,
        )
        logger.error(f"Row {row_id}: Failed to parse LLM response(s).")
        return None

    # Merge results
    merged_evals = []

    # We assume 'evaluations' array length and order match
    for ir_ev, re_ev in zip(
        results_irrelevant.get("evaluations", []),
        results_relevant.get("evaluations", []),
    ):
        merged_scores = ir_ev.get("scores", {}).copy()
        merged_scores.update(re_ev.get("scores", {}))
        ir_ev["scores"] = merged_scores
        merged_evals.append(ir_ev)

    results_irrelevant["evaluations"] = merged_evals

    # Compute averages after merging the scores
    results = compute_averages(results_irrelevant)

    results["metadata"] = {
        "row_id": row_id,
        "topic": topic,
        "model": model_name,
        "research_question": research_question,
        "golden_report": str(golden_path.name),
        "generated_report": report_path,
        "timestamp": datetime.now().isoformat(),
    }

    if print_table:
        print_results_table(results)
    return results


def _find_dataset_report(report_dir: Path, row_index: int, row_id: str) -> Path | None:
    """Locate the generated report for a dataset row by common naming conventions."""
    candidate_names = [f"topic_{row_index}.pdf", f"topic_{row_index}.md"]
    normalized_row_id = row_id.strip()
    if normalized_row_id and normalized_row_id != str(row_index):
        candidate_names.extend(
            [f"topic_{normalized_row_id}.pdf", f"topic_{normalized_row_id}.md"]
        )

    for candidate_name in candidate_names:
        candidate_path = report_dir / candidate_name
        if candidate_path.exists():
            return candidate_path

    return None


def _flatten_benchmark_row(
    run_timestamp: str,
    dataset_path: str,
    report_dir: str,
    row_index: int,
    row: dict[str, str],
    report_path: str,
    result: dict | None,
    status: str,
    error: str = "",
) -> dict[str, str | int | float]:
    """Flatten one benchmark row into a CSV-friendly record."""
    evaluation = (result or {}).get("evaluations", [{}])
    evaluation = evaluation[0] if evaluation else {}
    scores = evaluation.get("scores", {})

    flattened = {
        "benchmark_run": run_timestamp,
        "dataset": dataset_path,
        "report_dir": report_dir,
        "row_index": row_index,
        "row_id": row.get("id") or str(row_index),
        "type": row.get("type", ""),
        "topic": row.get("topic", ""),
        "golden_report": row.get("golden_report_path", ""),
        "generated_report": report_path,
        "status": status,
        "error": error,
        "overall_average": evaluation.get("overall_average", ""),
    }

    for dimension in BENCHMARK_SCORE_DIMENSIONS:
        flattened[dimension] = scores.get(dimension, {}).get("score", "")

    return flattened


def _save_benchmark_csv(
    rows: list[dict[str, str | int | float]],
    results_dir: str,
    run_timestamp: str,
) -> str:
    """Save flattened benchmark rows to a CSV file."""
    output_dir = _resolve_project_path(results_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"{run_timestamp}_benchmark.csv"
    fieldnames = [
        "benchmark_run",
        "dataset",
        "report_dir",
        "row_index",
        "row_id",
        "type",
        "topic",
        "golden_report",
        "generated_report",
        "status",
        "error",
        "overall_average",
        *BENCHMARK_SCORE_DIMENSIONS,
    ]

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return str(output_path)


def run_dataset_benchmark(config: dict, dataset_path: str, report_dir: str):
    """Evaluate a full benchmark dataset against reports in a directory."""
    defaults = get_deepfishy_defaults()
    model_name = defaults.get("judge", "gemini-2.5-flash")
    golden_reports_dir = config.get("golden_reports_dir", "benchmark/golden_reports")
    results_dir = config.get("results_dir", "benchmark/results")
    report_dir_path = _resolve_project_path(report_dir)

    if not report_dir_path.exists():
        logger.error(f"Report directory not found: {report_dir_path}")
        sys.exit(1)

    rows = load_dataset(dataset_path)
    if not rows:
        logger.error("Dataset is empty.")
        sys.exit(1)

    # Shared timestamp for this benchmark run
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    all_results = []
    flattened_rows = []

    for row_index, row in enumerate(rows, start=1):
        row_id = row.get("id") or str(row_index)
        topic = row.get("topic", "")
        golden_filename = row.get("golden_report_path", "")
        research_question = _format_research_question(topic)

        logger.info("=" * 60)
        logger.info(f"BENCHMARK ROW {row_id}: {topic}")
        logger.info("=" * 60)

        if not topic:
            error = "Missing topic in dataset row."
            logger.error(f"Row {row_id}: {error}")
            flattened_rows.append(
                _flatten_benchmark_row(
                    run_timestamp=run_timestamp,
                    dataset_path=dataset_path,
                    report_dir=str(report_dir_path),
                    row_index=row_index,
                    row=row,
                    report_path="",
                    result=None,
                    status="failed",
                    error=error,
                )
            )
            continue

        if not golden_filename:
            error = "Missing golden_report_path in dataset row."
            logger.error(f"Row {row_id}: {error}")
            flattened_rows.append(
                _flatten_benchmark_row(
                    run_timestamp=run_timestamp,
                    dataset_path=dataset_path,
                    report_dir=str(report_dir_path),
                    row_index=row_index,
                    row=row,
                    report_path="",
                    result=None,
                    status="failed",
                    error=error,
                )
            )
            continue

        report_path = _find_dataset_report(report_dir_path, row_index, row_id)
        if report_path is None:
            error = (
                "Generated report not found. Expected topic_{n}.pdf or topic_{n}.md "
                f"under {report_dir_path}."
            )
            logger.error(f"Row {row_id}: {error}")
            flattened_rows.append(
                _flatten_benchmark_row(
                    run_timestamp=run_timestamp,
                    dataset_path=dataset_path,
                    report_dir=str(report_dir_path),
                    row_index=row_index,
                    row=row,
                    report_path="",
                    result=None,
                    status="failed",
                    error=error,
                )
            )
            continue

        logger.info(f"Row {row_id}: Evaluating report at {report_path}")

        golden_path = PROJECT_ROOT / golden_reports_dir / golden_filename

        result = evaluate_generated_report(
            row_id=row_id,
            topic=topic,
            research_question=research_question,
            report_path=str(report_path),
            golden_path=golden_path,
            model_name=model_name,
            results_dir=results_dir,
            print_table=False,
        )

        if result:
            all_results.append(result)
            flattened_rows.append(
                _flatten_benchmark_row(
                    run_timestamp=run_timestamp,
                    dataset_path=dataset_path,
                    report_dir=str(report_dir_path),
                    row_index=row_index,
                    row=row,
                    report_path=str(report_path),
                    result=result,
                    status="success",
                )
            )
        else:
            flattened_rows.append(
                _flatten_benchmark_row(
                    run_timestamp=run_timestamp,
                    dataset_path=dataset_path,
                    report_dir=str(report_dir_path),
                    row_index=row_index,
                    row=row,
                    report_path=str(report_path),
                    result=None,
                    status="failed",
                    error="Evaluation failed. Check logs for details.",
                )
            )

    success_count = sum(1 for row in flattened_rows if row["status"] == "success")
    failed_count = len(flattened_rows) - success_count

    successful_scores = [
        row["overall_average"]
        for row in flattened_rows
        if row["status"] == "success"
        and isinstance(row["overall_average"], (int, float))
    ]
    dataset_average = (
        round(sum(successful_scores) / len(successful_scores), 2)
        if successful_scores
        else ""
    )

    combined = {
        "benchmark_run": run_timestamp,
        "dataset": str(_resolve_project_path(dataset_path)),
        "report_dir": str(report_dir_path),
        "summary": {
            "total_rows": len(flattened_rows),
            "successful_rows": success_count,
            "failed_rows": failed_count,
            "overall_average": dataset_average,
        },
        "rows": flattened_rows,
        "evaluations": all_results,
    }

    json_output_path = save_results(combined, results_dir)
    csv_output_path = _save_benchmark_csv(flattened_rows, results_dir, run_timestamp)
    logger.info(f"Benchmark JSON saved to: {json_output_path}")
    logger.info(f"Benchmark CSV saved to: {csv_output_path}")


def run_direct_benchmark(config: dict, topic: str, report_path: str, golden_path: str):
    """Run benchmark for a single manually specified report."""
    defaults = get_deepfishy_defaults()
    model_name = defaults.get("judge", "gemini-2.5-flash")
    results_dir = config.get("results_dir", "benchmark/results")

    research_question = _format_research_question(topic)
    golden_path_obj = Path(golden_path)

    logger.info("=" * 60)
    logger.info(f"DIRECT BENCHMARK: {topic}")
    logger.info(f"Report: {report_path}")
    logger.info(f"Golden: {golden_path}")
    logger.info("=" * 60)

    result = evaluate_generated_report(
        row_id="manual",
        topic=topic,
        research_question=research_question,
        report_path=report_path,
        golden_path=golden_path_obj,
        model_name=model_name,
        results_dir=results_dir,
    )

    if result:
        output_path = save_results(result, results_dir)
        logger.info(f"Result saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark financial report quality against a golden standard."
    )

    # Dataset mode args
    parser.add_argument(
        "--dataset",
        type=str,
        help="Path to dataset CSV file (for batch evaluation)",
    )
    parser.add_argument(
        "--report_dir",
        type=str,
        help="Directory containing generated reports named topic_{n}.pdf or topic_{n}.md",
    )

    # Direct mode args
    parser.add_argument(
        "--topic",
        type=str,
        default="Ngân hàng TMCP Quân đội (MBBank – MBB) trong giai đoạn 2025–2026",
        help="Topic of the report",
    )
    parser.add_argument(
        "--generated_report",
        type=str,
        default="benchmark/generated_reports/open_deep_research/topic_1.pdf",
        help="Path to generated report (.pdf)",
    )
    parser.add_argument(
        "--golden_report",
        type=str,
        default="benchmark/golden_reports/mbb.pdf",
        help="Path to golden standard (.pdf)",
    )

    args = parser.parse_args()
    config = load_config()

    # Check which mode to run
    if args.dataset:
        if not args.report_dir:
            parser.error(
                "--dataset requires --report_dir so each dataset row can be matched "
                "to topic_{n}.pdf or topic_{n}.md."
            )
        run_dataset_benchmark(config, args.dataset, args.report_dir)
    else:
        if args.report_dir:
            parser.error("--report_dir can only be used together with --dataset.")
        run_direct_benchmark(
            config, args.topic, args.generated_report, args.golden_report
        )


if __name__ == "__main__":
    main()
