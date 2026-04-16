"""CLI entrypoints for benchmark workflows."""

from deepfishy.features.benchmark.evaluator import (
    build_parser as build_evaluator_parser,
    main as evaluate_main,
)
from deepfishy.features.benchmark.run_dataset_and_evaluate import (
    build_parser as build_generate_and_evaluate_parser,
    main as generate_and_evaluate_main,
)

__all__ = [
    "build_evaluator_parser",
    "build_generate_and_evaluate_parser",
    "evaluate_main",
    "generate_and_evaluate_main",
]
