"""Celery tasks package."""

# Import all tasks to register them
from . import crawler_task  # noqa: F401

__all__ = [
    "crawler_task",
]
