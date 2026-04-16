"""ASGI entrypoint for the DeepFishy API."""

from deepfishy.app.api.factory import create_app

app = create_app()

__all__ = ["app"]
