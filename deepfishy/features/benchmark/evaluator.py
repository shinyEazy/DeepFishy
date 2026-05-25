"""Benchmark evaluation application logic."""

import argparse
import csv
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

from deepfishy.features.benchmark.prompt import (
    GOLDEN_REPORT_IRRELEVANT_METRICS_SYSTEM_PROMPT,
    GOLDEN_REPORT_RELEVANT_METRICS_SYSTEM_PROMPT,
    RESEARCH_QUESTION,
    format_evaluation_prompt,
)
from deepfishy.features.benchmark.results import (
    compute_averages,
    parse_json_response,
    print_results_table,
    save_results,
)
from deepfishy.infra.config.paths import PROJECT_ROOT, resolve_project_path
from deepfishy.shared.logging import logger
from deepfishy.shared.pdf.helpers import load_report_as_pdf
from deepfishy.infra.config.model_registry import get_deepfishy_defaults
from deepfishy.infra.llm.chat_factory import create_llm_client

load_dotenv()

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


def format_research_question(topic: str) -> str:
    """Format the benchmark research question robustly across placeholder styles."""
    return RESEARCH_QUESTION.format(topic=topic, TOPIC=topic)


def normalize_dataset_row(row: dict[str, str]) -> dict[str, str]:
    """Normalize CSV headers so casing differences do not break dataset parsing."""
    return {
        str(key).strip().lower(): (value or "").strip()
        for key, value in row.items()
        if key is not None
    }


def load_config(config_path: str | None = None) -> dict:
    """Load benchmark configuration from YAML file."""
    resolved_path = (
        PROJECT_ROOT / "benchmark" / "benchmark_config.yaml"
        if config_path is None
        else Path(config_path)
    )

    if not resolved_path.exists():
        logger.error(f"Config file not found: {resolved_path}")
        sys.exit(1)

    with open(resolved_path, "r", encoding="utf-8") as file_handle:
        return yaml.safe_load(file_handle)


def load_dataset(csv_path: str) -> list[dict]:
    """Load dataset CSV and return list of row dicts."""
    resolved_path = resolve_project_path(csv_path)
    if not resolved_path.exists():
        logger.error(f"Dataset file not found: {resolved_path}")
        sys.exit(1)

    with open(resolved_path, "r", encoding="utf-8") as file_handle:
        reader = csv.DictReader(file_handle)
        rows = [normalize_dataset_row(row) for row in reader]

    logger.info(f"Loaded {len(rows)} row(s) from {resolved_path.name}")
    return rows


def extract_text(response) -> str:
    """Extract text content from an LLM response."""
    response_text = getattr(response, "text", None) or getattr(response, "content", "")
    if isinstance(response_text, list):
        response_text = "\n".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in response_text
        )
    return response_text


def extract_usage(response) -> tuple[int, int]:
    """Extract input and output token usage from an LLM response."""
    usage = getattr(response, "usage_metadata", None) or {}

    if isinstance(usage, dict):
        return usage.get("input_tokens", 0), usage.get("output_tokens", 0)

    return (
        getattr(usage, "input_tokens", 0)
        or getattr(usage, "prompt_token_count", 0)
        or 0,
        getattr(usage, "output_tokens", 0)
        or getattr(usage, "candidates_token_count", 0)
        or 0,
    )


def invoke_llm_judge(model_name: str, messages: list, label: str, row_id: str):
    """Create an LLM client and invoke one benchmark judge prompt."""
    llm = create_llm_client(model_name)
    if llm is None:
        raise RuntimeError(f"Failed to create LLM client: {model_name}")

    logger.info(f"Row {row_id}: Calling LLM judge for {label} metrics...")
    return llm.invoke(messages)


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
    """Evaluate a single generated report against a golden standard."""
    generated_pdf = load_report_as_pdf(Path(report_path))
    if generated_pdf is None:
        logger.error(f"Row {row_id}: Failed to convert generated report to PDF.")
        return None

    if not golden_path.exists():
        logger.error(f"Row {row_id}: Golden report not found: {golden_path}")
        return None

    golden_pdf = load_report_as_pdf(golden_path)
    if golden_pdf is None:
        logger.error(f"Row {row_id}: Failed to load golden report as PDF.")
        return None

    report_pdfs = [{"filename": report_path, "pdf_bytes": generated_pdf}]
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

    llm_start = time.time()
    judge_tasks = {
        "irrelevant": ("6 irrelevant", messages_irrelevant),
        "relevant": ("3 relevant", messages_relevant),
    }
    responses = {}
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(
                invoke_llm_judge,
                model_name,
                messages,
                label,
                row_id,
            ): task_name
            for task_name, (label, messages) in judge_tasks.items()
        }
        for future in as_completed(futures):
            task_name = futures[future]
            try:
                responses[task_name] = future.result()
            except Exception as error:
                logger.error(
                    f"Row {row_id}: LLM {task_name} invocation failed: {error}"
                )
                return None

    llm_duration = time.time() - llm_start
    response_irrelevant = responses["irrelevant"]
    response_relevant = responses["relevant"]
    text_irrelevant = extract_text(response_irrelevant)
    text_relevant = extract_text(response_relevant)

    input_tok_irr, output_tok_irr = extract_usage(response_irrelevant)
    input_tok_rel, output_tok_rel = extract_usage(response_relevant)
    total_tokens = input_tok_irr + output_tok_irr + input_tok_rel + output_tok_rel
    logger.info(f"  Time: {llm_duration:.2f}s | Total tokens: {total_tokens:,}")

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

    merged_evals = []
    for irrelevant_eval, relevant_eval in zip(
        results_irrelevant.get("evaluations", []),
        results_relevant.get("evaluations", []),
    ):
        merged_scores = irrelevant_eval.get("scores", {}).copy()
        merged_scores.update(relevant_eval.get("scores", {}))
        irrelevant_eval["scores"] = merged_scores
        merged_evals.append(irrelevant_eval)

    results_irrelevant["evaluations"] = merged_evals
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


def find_dataset_report(report_dir: Path, row_index: int, row_id: str) -> Path | None:
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


def flatten_benchmark_row(
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


def save_benchmark_csv(
    rows: list[dict[str, str | int | float]],
    results_dir: str,
    run_timestamp: str,
) -> str:
    """Save flattened benchmark rows to a CSV file."""
    output_dir = resolve_project_path(results_dir)
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

    with open(output_path, "w", encoding="utf-8", newline="") as file_handle:
        writer = csv.DictWriter(file_handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return str(output_path)


def run_dataset_benchmark(
    config: dict, dataset_path: str, report_dir: str, judge_model: str | None = None
) -> None:
    """Evaluate a full benchmark dataset against reports in a directory."""
    defaults = get_deepfishy_defaults()
    model_name = judge_model or defaults.get("judge", "gemini-2.5-flash")
    golden_reports_dir = config.get("golden_reports_dir", "benchmark/golden_reports")
    results_dir = config.get("results_dir", "benchmark/results")
    report_dir_path = resolve_project_path(report_dir)

    if not report_dir_path.exists():
        logger.error(f"Report directory not found: {report_dir_path}")
        sys.exit(1)

    rows = load_dataset(dataset_path)
    if not rows:
        logger.error("Dataset is empty.")
        sys.exit(1)

    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    all_results = []
    flattened_rows = []

    for row_index, row in enumerate(rows, start=1):
        row_id = row.get("id") or str(row_index)
        topic = row.get("topic", "")
        golden_filename = row.get("golden_report_path", "")
        research_question = format_research_question(topic)

        logger.info("=" * 60)
        logger.info(f"BENCHMARK ROW {row_id}: {topic}")
        logger.info("=" * 60)

        if not topic:
            error = "Missing topic in dataset row."
            logger.error(f"Row {row_id}: {error}")
            flattened_rows.append(
                flatten_benchmark_row(
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
                flatten_benchmark_row(
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

        report_path = find_dataset_report(report_dir_path, row_index, row_id)
        if report_path is None:
            error = (
                "Generated report not found. Expected topic_{n}.pdf or topic_{n}.md "
                f"under {report_dir_path}."
            )
            logger.error(f"Row {row_id}: {error}")
            flattened_rows.append(
                flatten_benchmark_row(
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
                flatten_benchmark_row(
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
                flatten_benchmark_row(
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
        "dataset": str(resolve_project_path(dataset_path)),
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
    csv_output_path = save_benchmark_csv(flattened_rows, results_dir, run_timestamp)
    logger.info(f"Benchmark JSON saved to: {json_output_path}")
    logger.info(f"Benchmark CSV saved to: {csv_output_path}")


def run_direct_benchmark(
    config: dict,
    topic: str,
    report_path: str,
    golden_path: str,
    judge_model: str | None = None,
) -> None:
    """Run benchmark for a single manually specified report."""
    defaults = get_deepfishy_defaults()
    model_name = judge_model or defaults.get("judge", "gemini-2.5-flash")
    results_dir = config.get("results_dir", "benchmark/results")
    research_question = format_research_question(topic)
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


def build_parser() -> argparse.ArgumentParser:
    """Build the benchmark evaluator CLI parser."""
    parser = argparse.ArgumentParser(
        description="Benchmark financial report quality against a golden standard."
    )
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
    parser.add_argument(
        "--judge_model",
        type=str,
        help="Optional judge model override from configs/config.yaml, e.g. gpt-5-nano or gemini-2.5-flash.",
    )
    return parser


def main() -> None:
    """CLI entrypoint for benchmark evaluation."""
    parser = build_parser()
    args = parser.parse_args()
    config = load_config()

    if args.dataset:
        if not args.report_dir:
            parser.error(
                "--dataset requires --report_dir so each dataset row can be matched "
                "to topic_{n}.pdf or topic_{n}.md."
            )
        run_dataset_benchmark(
            config,
            args.dataset,
            args.report_dir,
            judge_model=args.judge_model,
        )
        return

    if args.report_dir:
        parser.error("--report_dir can only be used together with --dataset.")
    run_direct_benchmark(
        config,
        args.topic,
        args.generated_report,
        args.golden_report,
        judge_model=args.judge_model,
    )


__all__ = [
    "BENCHMARK_SCORE_DIMENSIONS",
    "build_parser",
    "evaluate_generated_report",
    "find_dataset_report",
    "format_research_question",
    "load_config",
    "load_dataset",
    "main",
    "run_dataset_benchmark",
    "run_direct_benchmark",
]


if __name__ == "__main__":
    main()
