"""Shared filesystem paths for the DeepFishy repository."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
BENCHMARK_DIR = PROJECT_ROOT / "benchmark"
CONFIGS_DIR = PROJECT_ROOT / "configs"


def resolve_project_path(path: str | Path) -> Path:
    """Resolve a path relative to the repository root when needed."""
    candidate = Path(path)
    return candidate if candidate.is_absolute() else PROJECT_ROOT / candidate
