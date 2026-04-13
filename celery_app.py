"""Compatibility entry point for the Celery application."""

from deepfishy.app.workers.celery_app import celery_app

__all__ = ["celery_app"]
