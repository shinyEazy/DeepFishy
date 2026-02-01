"""Tool for extracting knowledge graph from text and storing in Neo4j."""

import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from langchain_core.tools import tool
from langchain_core.documents import Document

from core.logging import logger

from services.rag import SearchResult


def _get_graphiti():
    """Lazy import to avoid circular imports."""
    from graph_rag.graphiti_service import get_graphiti_service

    return get_graphiti_service()


async def _extract_to_graph_async(
    texts: List[str],
    source_urls: Optional[List[str]] = None,
    time_context: Optional[str] = None,
) -> Dict[str, Any]:
    """Async implementation of extract_to_graph."""
    try:
        if not texts:
            return {
                "status": "error",
                "error": "No texts provided",
                "episodes_created": 0,
            }

        logger.info(f"Extracting graph from {len(texts)} text(s) using Graphiti")

        graphiti = await _get_graphiti()
        episodes_created = 0

        for i, text in enumerate(texts):
            url = source_urls[i] if source_urls and i < len(source_urls) else None
            result = SearchResult(
                content=text,
                url=url or f"manual_input_{i}",
                chunk_index=0,
                category=None,
                tags=[],
                date_ts=int(datetime.now(timezone.utc).timestamp()),
                score=1.0,
            )

            added = await graphiti.add_search_results(
                [result], time_context or "manual extraction"
            )
            episodes_created += added

        logger.info(f"Graph extraction complete. Added {episodes_created} episodes.")

        return {
            "status": "success",
            "episodes_created": episodes_created,
        }

    except Exception as e:
        logger.error(f"Graph extraction failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e), "episodes_created": 0}


@tool
def extract_to_graph(
    texts: List[str],
    source_urls: Optional[List[str]] = None,
    time_context: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Extract entities, events, and relationships from texts and store in Neo4j using Graphiti.

    Graphiti automatically handles entity extraction, relationship building, and
    temporal indexing using the configured Gemini model.

    Args:
        texts: List of text contents to process.
        source_urls: Optional list of URLs for attribution.
        time_context: Optional time context (e.g., "Q4/2025") to append to text.

    Returns:
        Dictionary containing:
        - status: "success" or "error"
        - episodes_created: Number of episodes added
        - error: Error message if status is "error"
    """
    return asyncio.run(_extract_to_graph_async(texts, source_urls, time_context))


@tool
def get_graph_stats() -> Dict[str, Any]:
    """
    Get statistics about the Neo4j knowledge graph.

    Warning: Graphiti might store data in a specific structure.
    This currently returns a placeholder or basic count if implemented.
    """
    try:

        async def _get_stats():
            graphiti = await _get_graphiti()
            return await graphiti.get_graph_stats()

        stats = asyncio.run(_get_stats())
        return {
            "status": "success",
            **stats,
        }
    except Exception as e:
        logger.error(f"Failed to get graph stats: {e}")
        return {"status": "error", "error": str(e)}
