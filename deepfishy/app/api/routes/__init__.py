"""API route modules."""

"""API route package for DeepFishy app entrypoints."""

from deepfishy.app.api.routes.chat import router as chat_router
from deepfishy.app.api.routes.rag import router as rag_router
from deepfishy.app.api.routes.response import router as response_router
from deepfishy.app.api.routes.session import router as session_router

__all__ = ["chat_router", "rag_router", "response_router", "session_router"]
