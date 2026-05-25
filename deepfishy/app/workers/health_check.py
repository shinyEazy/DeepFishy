"""Health check utilities for worker services."""

from urllib.parse import urljoin

import requests

from deepfishy.infra.config.settings import settings
from deepfishy.shared.logging import logger


def check_embedding_server_health(timeout: int = 5) -> tuple[bool, str]:
    """Check if the embedding server is healthy by calling /health."""
    try:
        health_url = urljoin(settings.EMBEDDING_API_URL, "health")
        logger.info(f"Checking embedding server health: {health_url}")
        response = requests.get(health_url, timeout=timeout)

        if response.status_code == 200:
            logger.info("Embedding server is healthy")
            return True, "Embedding server is healthy"

        error_msg = f"Embedding server returned status {response.status_code}"
        logger.error(error_msg)
        return False, error_msg
    except requests.Timeout:
        error_msg = f"Embedding server health check timed out (>{timeout}s)"
        logger.error(error_msg)
        return False, error_msg
    except requests.ConnectionError as error:
        error_msg = f"Failed to connect to embedding server at {settings.EMBEDDING_API_URL}: {error}"
        logger.error(error_msg)
        return False, error_msg
    except Exception as error:
        error_msg = f"Embedding server health check failed: {error}"
        logger.error(error_msg)
        return False, error_msg


__all__ = ["check_embedding_server_health"]
