"""Dependency exports for the package-native API layer."""


def get_db():
    """Lazily import the DB dependency to avoid import-time engine setup."""
    from db.session import get_db as _get_db

    yield from _get_db()


__all__ = ["get_db"]
