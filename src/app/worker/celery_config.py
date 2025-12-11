"""Celery configuration with scheduled tasks."""

import os
from datetime import timedelta

# Broker and backend settings - use environment variables
broker_url = os.getenv("CELERY_BROKER_URL")
result_backend = os.getenv("CELERY_RESULT_BACKEND")

# Task serialization
task_serializer = "json"
accept_content = ["json"]
result_serializer = "json"
timezone = "UTC"
enable_utc = True

# Task configuration
task_track_started = True
task_time_limit = 60 * 60  # 60 minutes hard limit
task_soft_time_limit = 60 * 60  # 60 minutes soft limit

# Queue configuration
task_queues = {
    "crawler": {"exchange": "crawler", "routing_key": "crawler"},
    "ingestion": {"exchange": "ingestion", "routing_key": "ingestion"},
    "celery": {"exchange": "celery", "routing_key": "celery"},
}

# Default queue
task_default_queue = "celery"
task_default_exchange = "celery"
task_default_routing_key = "celery"

# Logging configuration - disable hijacking of root logger
worker_hijack_root_logger = False

# Celery Beat schedule - periodic tasks
# beat_schedule = {
#     "crawl-article-urls-every-1-min": {
#         "task": "crawler.crawl_article_urls",
#         "schedule": timedelta(minutes=1),
#         "options": {"queue": "crawler"},
#     },
# }

beat_schedule = {
    "crawl-article-urls-every-day": {
        "task": "crawler.crawl_article_urls",
        "schedule": timedelta(days=1),
        "options": {"queue": "crawler"},
    },
}
