"""API schema modules."""

from deepfishy.app.api.schemas.chat import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ConversationDetail,
    ConversationListResponse,
    ConversationSummary,
    DeleteConversationResponse,
)
from deepfishy.app.api.schemas.rag import (
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    KnowledgeStatsResponse,
    SearchSource,
)
from deepfishy.app.api.schemas.session import (
    CreateSessionRequest,
    DeleteSessionResponse,
    SessionDetail,
    SessionListResponse,
    SessionMessage,
    SessionSummary,
)

__all__ = [
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "ConversationDetail",
    "ConversationListResponse",
    "ConversationSummary",
    "CreateSessionRequest",
    "DeleteConversationResponse",
    "DeleteSessionResponse",
    "KnowledgeSearchRequest",
    "KnowledgeSearchResponse",
    "KnowledgeStatsResponse",
    "SearchSource",
    "SessionDetail",
    "SessionListResponse",
    "SessionMessage",
    "SessionSummary",
]
