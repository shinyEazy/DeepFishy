import logging
import sys

# Create logger
logger = logging.getLogger("deepfishy")

# Set logging level
logger.setLevel(logging.INFO)

# Prevent propagation to parent loggers (avoids Celery duplication)
logger.propagate = False

# Create console handler
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)

# Create formatter
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)

# Add handler to logger
if not logger.handlers:
    logger.addHandler(handler)

__all__ = ["logger"]
