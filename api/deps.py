"""API dependencies."""

from typing import Generator
from sqlalchemy.orm import Session

from app.db.session import get_db

# Export get_db for easy import
__all__ = ["get_db"]
