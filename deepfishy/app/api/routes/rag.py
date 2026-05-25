"""RAG (Knowledge Search) API endpoints."""

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from deepfishy.app.api.schemas.rag import (
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    KnowledgeStatsResponse,
)
from deepfishy.features.knowledge_graph.rag import get_rag_service
from deepfishy.shared.logging import logger

router = APIRouter(prefix="/rag", tags=["RAG"])


@router.post("/search", response_model=KnowledgeSearchResponse)
async def search_knowledge(request: KnowledgeSearchRequest) -> Dict[str, Any]:
    """Search the local knowledge base for relevant financial articles."""
    try:
        rag_service = get_rag_service()
        return rag_service.search_with_context(
            query=request.query,
            top_k=request.top_k,
            category=request.category,
            include_metadata=True,
        )
    except Exception as error:
        logger.error(f"RAG search API error: {error}")
        raise HTTPException(status_code=500, detail=str(error))


@router.get("/stats", response_model=KnowledgeStatsResponse)
async def get_knowledge_stats() -> Dict[str, Any]:
    """Get statistics about the local knowledge base."""
    try:
        rag_service = get_rag_service()
        return rag_service.get_collection_stats()
    except Exception as error:
        logger.error(f"RAG stats API error: {error}")
        raise HTTPException(status_code=500, detail=str(error))


@router.get("/health")
async def rag_health_check() -> Dict[str, str]:
    """Check if the RAG service is healthy and connected."""
    try:
        rag_service = get_rag_service()
        stats = rag_service.get_collection_stats()
        if stats.get("status") == "connected":
            return {"status": "healthy", "message": "RAG service is operational"}
        return {
            "status": "degraded",
            "message": stats.get("error", "Unknown error"),
        }
    except Exception as error:
        return {"status": "unhealthy", "message": str(error)}


__all__ = ["router"]
