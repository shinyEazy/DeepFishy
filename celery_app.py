"""Celery app configuration and initialization."""

from celery import Celery
from app.core.config import settings

# Initialize Celery app
celery_app = Celery(
    "deepfishy",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# Load configuration
celery_app.config_from_object("app.worker.celery_config")

# Auto-discover and import tasks
celery_app.autodiscover_tasks(["app.worker.tasks"])

# Explicitly import tasks to ensure registration
from app.worker.tasks import crawler_task  # noqa: F401
from app.worker.tasks import embedding_task  # noqa: F401
