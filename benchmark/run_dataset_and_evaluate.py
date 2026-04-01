"""Generate benchmark reports for a dataset, then evaluate them."""

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


DEFAULT_REPORT_DIR = "benchmark/generated_reports/deepfishy"
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate reports for a benchmark dataset and then evaluate them."
    )
    parser.add_argument(
        "--dataset",
        required=True,
        help="Path to the dataset CSV file.",
    )
    parser.add_argument(
        "--report_dir",
        default=DEFAULT_REPORT_DIR,
        help=(
            "Directory containing generated reports. "
            "When generation is enabled, this should stay at the default value."
        ),
    )
    parser.add_argument(
        "--benchmark_config",
        default=None,
        help="Optional path to benchmark_config.yaml.",
    )
    parser.add_argument(
        "--skip_generation",
        action="store_true",
        help="Skip dataset generation and only run evaluation on an existing report_dir.",
    )

    args = parser.parse_args()

    if not args.skip_generation and Path(args.report_dir) != Path(DEFAULT_REPORT_DIR):
        parser.error(
            "--report_dir can only be changed together with --skip_generation "
            "because dataset generation currently writes to "
            f"{DEFAULT_REPORT_DIR}."
        )

    try:
        from engine.main import run_dataset_generation
        from benchmark.evaluate import (
            load_config as load_benchmark_config,
            run_dataset_benchmark,
        )
    except Exception as exc:
        raise SystemExit(
            "Failed to import DeepFishy benchmark modules. "
            "Make sure project dependencies are installed and required environment "
            f"variables are set. Original error: {exc}"
        ) from exc

    if args.skip_generation:
        logger.info(f"Skipping generation. Evaluating reports in {args.report_dir}")
    else:
        logger.info(f"Generating reports for dataset: {args.dataset}")
        run_dataset_generation(args.dataset)

    logger.info(
        f"Loading benchmark config: {args.benchmark_config or 'default config'}"
    )
    config = load_benchmark_config(args.benchmark_config)

    logger.info(f"Evaluating dataset reports in: {args.report_dir}")
    run_dataset_benchmark(config, args.dataset, args.report_dir)


if __name__ == "__main__":
    main()
