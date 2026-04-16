"""Database session management for PostgreSQL."""

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from deepfishy.infra.config.settings import settings
from deepfishy.shared.logging import logger


engine = None
SessionLocal = sessionmaker(autocommit=False, autoflush=False)


def _get_engine():
    """Create the SQLAlchemy engine lazily."""
    global engine
    if engine is None:
        if not settings.POSTGRES_CONN_URL:
            raise ValueError("POSTGRES_CONN_URL is not configured")
        engine = create_engine(
            settings.POSTGRES_CONN_URL,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            echo=False,
        )
        SessionLocal.configure(bind=engine)
    return engine


def get_db() -> Generator[Session, None, None]:
    """Dependency function to get database session."""
    db = SessionLocal(bind=_get_engine())
    try:
        yield db
    finally:
        db.close()


def create_session() -> Session:
    """Create a standalone SQLAlchemy session bound to the shared engine."""
    return SessionLocal(bind=_get_engine())


def init_db() -> None:
    """Initialize database by creating all tables."""
    try:
        from db.base import Base
        import db.models  # noqa: F401

        Base.metadata.create_all(bind=_get_engine())
        logger.info("Database tables created successfully")
    except Exception as exc:
        logger.error(f"Failed to initialize database: {exc}")
        raise


def close_db() -> None:
    """Close database connections."""
    try:
        global engine
        if engine is not None:
            engine.dispose()
            engine = None
            SessionLocal.configure(bind=None)
            logger.info("Database connections closed")
    except Exception as exc:
        logger.warning(f"Error closing database connections: {exc}")


__all__ = [
    "engine",
    "SessionLocal",
    "create_session",
    "get_db",
    "init_db",
    "close_db",
]
