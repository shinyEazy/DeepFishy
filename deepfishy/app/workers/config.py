"""Celery configuration for DeepFishy workers."""

import os
from datetime import timedelta

from deepfishy.infra.config.settings import settings

broker_url = settings.CELERY_BROKER_URL or os.getenv("CELERY_BROKER_URL")
result_backend = settings.CELERY_RESULT_BACKEND or os.getenv("CELERY_RESULT_BACKEND")

task_serializer = "json"
accept_content = ["json"]
result_serializer = "json"
timezone = "UTC"
enable_utc = True

task_track_started = True
task_time_limit = 150 * 60
task_soft_time_limit = 120 * 60

task_queues = {
    "crawler": {"exchange": "crawler", "routing_key": "crawler"},
    "ingestion": {"exchange": "ingestion", "routing_key": "ingestion"},
    "celery": {"exchange": "celery", "routing_key": "celery"},
}

task_default_queue = "celery"
task_default_exchange = "celery"
task_default_routing_key = "celery"
worker_hijack_root_logger = False

beat_schedule = {
    "crawl-article-urls-every-day": {
        "task": "crawler.crawl_article_urls",
        "schedule": timedelta(days=1),
        "options": {"queue": "crawler"},
    },
}
