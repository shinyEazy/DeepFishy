"""Celery task modules."""

"""Celery task package for DeepFishy worker entrypoints."""

from deepfishy.app.workers.tasks import crawler_task, embedding_task

__all__ = ["crawler_task", "embedding_task"]
