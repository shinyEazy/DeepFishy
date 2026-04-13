"""Placeholder repository module for the chat feature boundary."""

from sqlalchemy.orm import Session


class ChatRepository:
    """Minimal repository placeholder for future chat persistence extraction."""

    def __init__(self, db: Session):
        self.db = db
