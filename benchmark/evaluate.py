"""
Financial Report Benchmark Evaluator.

Loads a dataset CSV, generates reports via the engine for each row,
then evaluates them against golden standard PDFs using an LLM judge.
Can also evaluate a single existing report directly using --topic, --report, --golden.

python benchmark/evaluate.py --dataset benchmark/dataset/dataset_tmp.csv
python benchmark/evaluate.py --topic "Ngân hàng TMCP Quân đội (MBBank - MBB) trong quý 4 năm 2025" --report outputs/20260211_171619/final.md --golden benchmark/golden_reports/mbb_q4_2025.pdf
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
from benchmark.prompt import format_evaluation_prompt, RESEARCH_QUESTION

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
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4.1-nano-2025-04-14": {"input": 0.10, "output": 0.40},
    "gpt-5-nano-2025-08-07": {"input": 0.10, "output": 0.40},
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
    p = Path(csv_path) if Path(csv_path).is_absolute() else PROJECT_ROOT / csv_path
    if not p.exists():
        logger.error(f"Dataset file not found: {p}")
        sys.exit(1)

    with open(p, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    logger.info(f"Loaded {len(rows)} row(s) from {p.name}")
    return rows


def evaluate_generated_report(
    row_id: str,
    topic: str,
    research_question: str,
    report_path: str,
    golden_path: Path,
    model_name: str,
    results_dir: str,
) -> dict | None:
    """Evaluate a single generated report against a golden standard."""
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
        logger.error(f"Failed to create LLM client: {model_name}")
        sys.exit(1)

    # Build prompt & call LLM judge
    report_pdfs = [{"filename": report_path, "pdf_bytes": generated_pdf}]
    messages = format_evaluation_prompt(
        research_question=research_question,
        golden_pdf=golden_pdf,
        report_pdfs=report_pdfs,
    )

    logger.info(f"Row {row_id}: Calling LLM judge...")
    llm_start = time.time()
    try:
        response = llm.invoke(messages)
    except Exception as e:
        logger.error(f"Row {row_id}: LLM invocation failed: {e}")
        return None
    llm_duration = time.time() - llm_start

    # Extract response text
    response_text = response.content
    if isinstance(response_text, list):
        response_text = "\n".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in response_text
        )

    # Token usage & cost
    usage = response.usage_metadata or {}
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    total_tokens = usage.get("total_tokens", input_tokens + output_tokens)

    pricing = MODEL_PRICING.get(model_name, {"input": 0, "output": 0})
    total_cost = (input_tokens / 1_000_000) * pricing["input"] + (
        output_tokens / 1_000_000
    ) * pricing["output"]

    logger.info(
        f"  Time: {llm_duration:.2f}s | Tokens: {total_tokens:,} | Cost: ${total_cost:.4f}"
    )

    # Parse & save
    results = parse_json_response(response_text)
    if results is None:
        save_results(
            {"error": "Failed to parse JSON", "raw_response": response_text},
            results_dir,
        )
        logger.error(f"Row {row_id}: Failed to parse LLM response.")
        return None

    results = compute_averages(results)
    results["metadata"] = {
        "row_id": row_id,
        "topic": topic,
        "model": model_name,
        "research_question": research_question,
        "golden_report": str(golden_path.name),
        "generated_report": report_path,
        "timestamp": datetime.now().isoformat(),
        "llm_time_seconds": round(llm_duration, 2),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cost_usd": round(total_cost, 6),
    }

    print_results_table(results)
    return results


def run_dataset_benchmark(config: dict, dataset_path: str):
    """Run the benchmark pipeline for a full dataset."""
    defaults = get_deepfishy_defaults()
    model_name = defaults.get("judge", "gemini-2.5-flash")
    golden_reports_dir = config.get("golden_reports_dir", "benchmark/golden_reports")
    results_dir = config.get("results_dir", "benchmark/results")

    rows = load_dataset(dataset_path)
    if not rows:
        logger.error("Dataset is empty.")
        sys.exit(1)

    # Shared timestamp for this benchmark run
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    all_results = []

    for row in rows:
        row_id = row["id"]
        topic = row["topic"]
        golden_filename = row["golden_report_path"]
        research_question = RESEARCH_QUESTION.format(TOPIC=topic)

        logger.info("=" * 60)
        logger.info(f"BENCHMARK ROW {row_id}: {topic}")
        logger.info("=" * 60)

        # --- Step A: Generate report via engine ---
        from engine.main import run_engine

        session_id = f"{run_timestamp}/rq{row_id}"
        logger.info(f"Running engine with session_id={session_id}")

        final_md_path = run_engine(
            user_input=research_question,
            session_id=session_id,
        )

        if not final_md_path:
            logger.error(f"Row {row_id}: Engine failed to produce final.md, skipping.")
            continue

        logger.info(f"Row {row_id}: Generated report at {final_md_path}")

        # --- Step B: Evaluate against golden report ---
        golden_path = PROJECT_ROOT / golden_reports_dir / golden_filename

        result = evaluate_generated_report(
            row_id=row_id,
            topic=topic,
            research_question=research_question,
            report_path=final_md_path,
            golden_path=golden_path,
            model_name=model_name,
            results_dir=results_dir,
        )

        if result:
            all_results.append(result)

    # Save combined results
    if all_results:
        combined = {
            "benchmark_run": run_timestamp,
            "dataset": dataset_path,
            "rows": all_results,
        }
        output_path = save_results(combined, results_dir)
        logger.info(f"All results saved to: {output_path}")
    else:
        logger.error("No successful evaluations.")


def run_direct_benchmark(config: dict, topic: str, report_path: str, golden_path: str):
    """Run benchmark for a single manually specified report."""
    defaults = get_deepfishy_defaults()
    model_name = defaults.get("judge", "gemini-2.5-flash")
    results_dir = config.get("results_dir", "benchmark/results")

    research_question = RESEARCH_QUESTION.format(TOPIC=topic)
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
        default="benchmark/dataset/dataset_tmp.csv",
        help="Path to dataset CSV file (for batch evaluation)",
    )

    # Direct mode args
    parser.add_argument("--topic", type=str, help="Topic of the report")
    parser.add_argument("--report", type=str, help="Path to generated report (.md)")
    parser.add_argument("--golden", type=str, help="Path to golden standard (.pdf)")

    args = parser.parse_args()
    config = load_config()

    # Check which mode to run
    if args.topic and args.report and args.golden:
        run_direct_benchmark(config, args.topic, args.report, args.golden)
    else:
        # Fallback to dataset mode
        run_dataset_benchmark(config, args.dataset)


if __name__ == "__main__":
    main()
