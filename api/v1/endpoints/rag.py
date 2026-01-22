"""RAG (Knowledge Search) API endpoints."""

from typing import Dict, Any
from fastapi import APIRouter, HTTPException

from api.schemas.rag import (
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    KnowledgeStatsResponse,
)
from services.rag import get_rag_service
from core.logging import logger


router = APIRouter(prefix="/rag", tags=["RAG - Knowledge Search"])


@router.post("/search", response_model=KnowledgeSearchResponse)
async def search_knowledge(request: KnowledgeSearchRequest) -> Dict[str, Any]:
    """
    Search the local knowledge base for relevant financial articles.

    This endpoint performs semantic search over indexed Vietnamese financial
    articles using vector similarity.
    """
    try:
        rag_service = get_rag_service()

        result = rag_service.search_with_context(
            query=request.query,
            top_k=request.top_k,
            category=request.category,
            include_metadata=True,
        )

        return result

    except Exception as e:
        logger.error(f"RAG search API error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=KnowledgeStatsResponse)
async def get_knowledge_stats() -> Dict[str, Any]:
    """
    Get statistics about the local knowledge base.

    Returns information about the number of indexed documents and
    connection status.
    """
    try:
        rag_service = get_rag_service()
        stats = rag_service.get_collection_stats()
        return stats

    except Exception as e:
        logger.error(f"RAG stats API error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def rag_health_check() -> Dict[str, str]:
    """
    Check if the RAG service is healthy and connected.
    """
    try:
        rag_service = get_rag_service()
        stats = rag_service.get_collection_stats()

        if stats.get("status") == "connected":
            return {"status": "healthy", "message": "RAG service is operational"}
        else:
            return {
                "status": "degraded",
                "message": stats.get("error", "Unknown error"),
            }

    except Exception as e:
        return {"status": "unhealthy", "message": str(e)}
