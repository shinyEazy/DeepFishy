"""LangSmith tracing helpers with graceful fallback when tracing is unavailable."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

try:
    from langsmith import traceable
    from langsmith.run_helpers import get_current_run_tree, tracing_context
except ImportError:  # pragma: no cover - tracing is optional at runtime
    traceable = None
    get_current_run_tree = None
    tracing_context = None


def traceable_chain(name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorate a function as a LangSmith chain when the SDK is available."""
    if traceable is None:

        def _decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            return func

        return _decorator

    return traceable(name=name, run_type="chain")


def wrap_with_current_tracing_context(
    func: Callable[..., Any],
) -> Callable[..., Any]:
    """Capture the current LangSmith parent run so threaded work stays nested."""
    if get_current_run_tree is None or tracing_context is None:
        return func

    parent_run = get_current_run_tree()
    if parent_run is None:
        return func

    def _wrapped(*args: Any, **kwargs: Any) -> Any:
        with tracing_context(parent=parent_run):
            return func(*args, **kwargs)

    return _wrapped


__all__ = ["traceable_chain", "wrap_with_current_tracing_context"]
