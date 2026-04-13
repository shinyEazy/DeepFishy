"""Compatibility shim for database session management."""

from deepfishy.infra.db.session import (
    SessionLocal,
    close_db,
    engine,
    get_db,
    init_db,
)

__all__ = ["engine", "SessionLocal", "get_db", "init_db", "close_db"]
