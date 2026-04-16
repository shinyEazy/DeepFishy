"""CLI entrypoint for report generation workflows."""

import argparse

from deepfishy.features.reports.application.generate_dataset_reports import (
    format_user_input,
    run_dataset_generation,
)
from deepfishy.features.reports.application.generate_report import (
    DEFAULT_TOPIC,
    build_parser as build_report_parser,
    run_engine,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the report CLI parser."""
    parser = build_report_parser()
    parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        help="Path to a dataset CSV. Generates one report per topic and saves them to benchmark/generated_reports/deepfishy/topic_{n}.pdf.",
    )
    return parser


def main() -> None:
    """CLI entrypoint for report generation."""
    parser = build_parser()
    args = parser.parse_args()

    if args.dataset:
        if args.phase or args.session:
            parser.error("--dataset cannot be combined with --phase or --session.")
        run_dataset_generation(args.dataset)
        raise SystemExit(0)

    phases = [args.phase] if args.phase else None
    topic = args.topic or DEFAULT_TOPIC
    user_input = format_user_input(topic)
    run_engine(user_input=user_input, session_id=args.session, phases=phases)



__all__ = ["build_parser", "main"]


if __name__ == "__main__":
    main()
