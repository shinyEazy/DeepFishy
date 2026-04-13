"""Database session management for PostgreSQL."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from core.config import settings
from core.logging import logger

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
    """
    Dependency function to get database session.

    Yields:
        Database session that automatically closes after use.

    Example:
        @get("/items")
        def get_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal(bind=_get_engine())
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Initialize database - create all tables.
    This should be called on application startup.
    """
    try:
        from db.base import Base
        import db.models  # noqa: F401

        Base.metadata.create_all(bind=_get_engine())
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
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
    except Exception as e:
        logger.warning(f"Error closing database connections: {e}")
