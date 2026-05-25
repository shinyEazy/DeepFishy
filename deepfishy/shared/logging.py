"""Shared logging setup for DeepFishy."""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Log directory - default to project root/logs/
LOG_DIR = Path(os.getenv("DEEPFISHY_LOG_DIR", "logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOG_DIR / "deepfishy.log"
LOG_LEVEL = os.getenv("DEEPFISHY_LOG_LEVEL", "INFO").upper()

logger = logging.getLogger("deepfishy")
logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
logger.propagate = False

# Console handler (stdout)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
)

# File handler (rotating, max 10MB, keep 5 backups)
file_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=10 * 1024 * 1024,  # 10MB
    backupCount=5,
    encoding="utf-8",
)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(
    logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
    )
)

if not logger.handlers:
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

logger.info(f"Logging initialized. Log file: {LOG_FILE}")

__all__ = ["logger"]
