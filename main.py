"""Compatibility entry point for the FastAPI application."""

from deepfishy.app.api.factory import create_app

app = create_app()
