"""Shared logging setup for DeepFishy."""

import logging
import sys


logger = logging.getLogger("deepfishy")
logger.setLevel(logging.INFO)
logger.propagate = False

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
handler.setFormatter(
    logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
)

if not logger.handlers:
    logger.addHandler(handler)

__all__ = ["logger"]
