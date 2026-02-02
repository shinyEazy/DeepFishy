"""Knowledge search tool with Graphiti auto-ingestion.

This tool searches the local knowledge base AND automatically adds
the results to the Graphiti knowledge graph.

IMPORTANT: Due to async client limitations, graph building only works
in the async version (search_and_build_graph_async). The sync version
only performs search operations.
"""

import asyncio
from typing import Optional, Dict, Any, List
from langchain_core.tools import tool

from core.logging import logger

# Thread-local storage for pending graph updates
# These will be processed by the async orchestrator
_pending_graph_updates: List[Dict[str, Any]] = []


def _get_rag_service():
    """Lazy import to avoid circular imports."""
    from services.rag import get_rag_service

    return get_rag_service()


def _get_graphiti_service():
    """Lazy import to get GraphitiService."""
    from graph_rag.graphiti_service import get_graphiti_service

    return get_graphiti_service()


async def _add_to_graph_async(results, query):
    """Add search results to Graphiti graph asynchronously.

    This MUST be called from the main event loop where GraphitiService
    was initialized. Async clients (Neo4j, LLM) cannot be shared across
    different event loops.
    """
    try:
        graphiti_service = await _get_graphiti_service()
        added = await graphiti_service.add_search_results(results, query)
        return added
    except Exception as e:
        logger.warning(f"Failed to add results to graph: {e}")
        return 0


def get_pending_graph_updates() -> List[Dict[str, Any]]:
    """Get pending graph updates for batch processing by the orchestrator."""
    global _pending_graph_updates
    updates = _pending_graph_updates.copy()
    _pending_graph_updates.clear()
    return updates


def clear_pending_graph_updates():
    """Clear any pending graph updates."""
    global _pending_graph_updates
    _pending_graph_updates.clear()


@tool
def search_and_build_graph(
    query: str,
    top_k: int = 5,
    category: Optional[str] = None,
) -> Dict[str, Any]:
    """Search local knowledge base for relevant documents.

    This tool searches the Milvus vector database for relevant articles.

    NOTE: Graph building is deferred to the async orchestrator context.
    For immediate graph building, use the async version in an async context.

    Args:
        query: Natural language search query in Vietnamese or English.
               Be specific about what information you're looking for.
        top_k: Number of results to return (default: 5, max: 10).
        category: Optional category filter.

    Returns:
        Dictionary containing:
        - context: Formatted text with relevant document contents
        - sources: List of source URLs and metadata
        - num_results: Number of documents found
        - query: The original query

    Example:
        search_and_build_graph("thuế quan Trump tác động Việt Nam", top_k=5)
    """
    global _pending_graph_updates

    try:
        # Validate top_k
        top_k = max(1, min(top_k, 10))

        logger.info(f"Builder: query='{query}', top_k={top_k}")

        rag_service = _get_rag_service()

        # Get raw search results
        results = rag_service.search(
            query=query,
            top_k=top_k,
            category=category,
        )

        if not results:
            return {
                "context": f"No results found for: {query}",
                "sources": [],
                "query": query,
                "num_results": 0,
                "added_to_graph": 0,
            }

        # Queue results for graph building by the async orchestrator
        # This avoids the "Future attached to different loop" error
        _pending_graph_updates.append(
            {
                "results": results,
                "query": query,
            }
        )
        logger.debug(f"Queued {len(results)} results for deferred graph building")

        # Format results for agent
        context_parts = []
        sources = []

        for i, result in enumerate(results, 1):
            context_parts.append(
                f"[{i}] {result.url}\n"
                f"Category: {result.category or 'N/A'}\n"
                f"Tags: {', '.join(result.tags[:5]) if result.tags else 'N/A'}\n"
                f"Content: {result.content[:500]}...\n"
            )
            sources.append(
                {
                    "url": result.url,
                    "category": result.category,
                    "tags": result.tags,
                    "score": result.score,
                }
            )

        return {
            "context": "\n".join(context_parts),
            "sources": sources,
            "query": query,
            "num_results": len(results),
            "graph_updates_queued": True,
            "message": "Search complete. Graph updates queued for async processing.",
        }

    except Exception as e:
        logger.error(f"Search+Graph failed: {e}", exc_info=True)
        return {
            "context": f"Error: {str(e)}",
            "sources": [],
            "query": query,
            "num_results": 0,
            "added_to_graph": 0,
            "error": str(e),
        }


@tool
async def search_and_build_graph_async(
    query: str,
    top_k: int = 5,
    category: Optional[str] = None,
) -> Dict[str, Any]:
    """Async version of search_and_build_graph.

    Same functionality but designed for async contexts like the
    BuilderOrchestrator's iterative loop.
    """
    try:
        top_k = max(1, min(top_k, 10))

        logger.info(f"Search+Graph (async): query='{query}', top_k={top_k}")

        rag_service = _get_rag_service()

        # Get search results
        results = rag_service.search(
            query=query,
            top_k=top_k,
            category=category,
        )

        if not results:
            return {
                "context": f"No results found for: {query}",
                "sources": [],
                "query": query,
                "num_results": 0,
                "added_to_graph": 0,
            }

        # Add to Graphiti graph
        added = await _add_to_graph_async(results, query)

        # Format results
        context_parts = []
        sources = []

        for i, result in enumerate(results, 1):
            context_parts.append(
                f"[{i}] {result.url}\n" f"Content: {result.content[:400]}...\n"
            )
            sources.append(
                {
                    "url": result.url,
                    "category": result.category,
                }
            )

        return {
            "context": "\n".join(context_parts),
            "sources": sources,
            "query": query,
            "num_results": len(results),
            "added_to_graph": added,
        }

    except Exception as e:
        logger.error(f"Async Search+Graph failed: {e}")
        return {
            "context": f"Error: {str(e)}",
            "sources": [],
            "query": query,
            "num_results": 0,
            "added_to_graph": 0,
            "error": str(e),
        }
