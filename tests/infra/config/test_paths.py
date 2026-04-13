from pathlib import Path

from deepfishy.infra.config.paths import PROJECT_ROOT, resolve_project_path


def test_project_root_points_to_repository() -> None:
    assert (PROJECT_ROOT / "pyproject.toml").exists()


def test_resolve_project_path_handles_relative_and_absolute_paths(
    tmp_path: Path,
) -> None:
    relative = resolve_project_path("README.md")
    absolute = resolve_project_path(tmp_path)

    assert relative == PROJECT_ROOT / "README.md"
    assert absolute == tmp_path
