"""Health check utilities for worker services."""

import requests
from urllib.parse import urljoin

from core.logging import logger
from core.config import settings


def check_embedding_server_health(timeout: int = 5) -> tuple[bool, str]:
    """
    Check if embedding server is healthy by calling /health endpoint.

    Args:
        timeout: Timeout in seconds for health check request

    Returns:
        Tuple of (is_healthy: bool, message: str)
    """
    try:
        health_url = urljoin(settings.EMBEDDING_API_URL, "health")
        logger.info(f"🏥 Checking embedding server health: {health_url}")

        response = requests.get(health_url, timeout=timeout)

        if response.status_code == 200:
            logger.info("✅ Embedding server is healthy")
            return True, "Embedding server is healthy"
        else:
            error_msg = f"Embedding server returned status {response.status_code}"
            logger.error(f"❌ {error_msg}")
            return False, error_msg

    except requests.Timeout:
        error_msg = f"Embedding server health check timed out (>{timeout}s)"
        logger.error(f"❌ {error_msg}")
        return False, error_msg
    except requests.ConnectionError as e:
        error_msg = f"Failed to connect to embedding server at {settings.EMBEDDING_API_URL}: {e}"
        logger.error(f"❌ {error_msg}")
        return False, error_msg
    except Exception as e:
        error_msg = f"Embedding server health check failed: {e}"
        logger.error(f"❌ {error_msg}")
        return False, error_msg
