"""Celery application bootstrap for DeepFishy workers."""

from celery import Celery

from core.config import settings
from worker.tasks import crawler_task  # noqa: F401
from worker.tasks import embedding_task  # noqa: F401


celery_app = Celery(
    "deepfishy",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.config_from_object("worker.celery_config")
celery_app.autodiscover_tasks(["worker.tasks"])
