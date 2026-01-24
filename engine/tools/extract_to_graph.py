"""Tool for extracting knowledge graph from text and storing in Neo4j."""

from typing import Dict, Any, Optional, List
from langchain_core.tools import tool
from langchain_core.documents import Document

from core.logging import logger


def _get_graphiti():
    """Lazy import to avoid circular imports."""
    from engine.graph_rag.graphiti_client import get_graphiti_service

    return get_graphiti_service()


@tool
async def extract_to_graph(
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
    try:
        if not texts:
            return {
                "status": "error",
                "error": "No texts provided",
                "episodes_created": 0,
            }

        logger.info(f"Extracting graph from {len(texts)} text(s) using Graphiti")

        graphiti = _get_graphiti()
        episodes_created = 0

        for i, text in enumerate(texts):
            url = source_urls[i] if source_urls and i < len(source_urls) else None

            # Add episode to graph
            await graphiti.add_episode(
                text=text, source_url=url, time_context=time_context
            )
            episodes_created += 1

        logger.info(f"Graph extraction complete. Added {episodes_created} episodes.")

        return {
            "status": "success",
            "episodes_created": episodes_created,
            # Graphiti doesn't strictly return node/rel counts per episode insertion in the same way
            # so we omit detailed stats for now or could query them separately if needed.
        }

    except Exception as e:
        logger.error(f"Graph extraction failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e), "episodes_created": 0}


@tool
def get_graph_stats() -> Dict[str, Any]:
    """
    Get statistics about the Neo4j knowledge graph.

    Warning: Graphiti might store data in a specific structure.
    This currently returns a placeholder or basic count if implemented.
    """
    try:
        # TODO: Implement proper stats for Graphiti schema
        # For now, we return a simple connected status or we can run a direct cypher count query
        # via the driver exposed by Graphiti if available, or just skip detailed stats.
        return {
            "status": "connected (Graphiti)",
            "message": "Detailed stats not yet implemented for Graphiti schema",
        }
    except Exception as e:
        logger.error(f"Failed to get graph stats: {e}")
        return {"status": "error", "error": str(e)}
