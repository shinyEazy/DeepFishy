"""Celery application bootstrap for DeepFishy workers."""

from celery import Celery

from deepfishy.infra.config.settings import settings
from deepfishy.app.workers.tasks import crawler_task  # noqa: F401
from deepfishy.app.workers.tasks import embedding_task  # noqa: F401


celery_app = Celery(
    "deepfishy",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.config_from_object("deepfishy.app.workers.config")
celery_app.autodiscover_tasks(["deepfishy.app.workers.tasks"])
