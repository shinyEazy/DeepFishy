"""Runtime helpers for chat-facing agent access."""

from functools import lru_cache

from deepfishy.features.reports.application.generate_report import create_agent


@lru_cache(maxsize=1)
def get_chat_agent():
    """Create and cache the default chat agent."""
    agent, _ = create_agent(phase="write")
    return agent


def is_chat_agent_ready() -> bool:
    """Return whether the chat agent can be created successfully."""
    try:
        return get_chat_agent() is not None
    except Exception:
        return False


__all__ = ["get_chat_agent", "is_chat_agent_ready"]
