"""Tool for querying the Neo4j knowledge graph."""

from typing import Dict, Any, Optional, List, Literal
from langchain_core.tools import tool

from core.logging import logger


def _get_graphiti():
    """Lazy import to avoid circular imports."""
    from engine.graph_rag.graphiti_client import get_graphiti_service

    return get_graphiti_service()


@tool
async def query_knowledge_graph(
    query_type: Literal["time_period", "causal_chain", "search", "related"],
    query_value: str,
    limit: int = 10,
    direction: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Query the Neo4j knowledge graph using Graphiti.

    Args:
        query_type:
            - "search": Semantic/hybrid search
            - "time_period": Search with time context (currently mapped to broad search)
            - "causal_chain": (Mapped to search for now)
            - "related": (Mapped to search for now)
        query_value: The search value or entity name
        limit: Maximum number of results
        direction: Unused in Graphiti version currently

    Returns:
        Dictionary containing search results
    """
    try:
        graphiti = _get_graphiti()

        # Graphiti primarily exposes a unified search.
        # We can optimize specific query types later if Graphiti adds specific APIs.

        search_query = query_value
        if query_type == "time_period":
            search_query = f"Events in {query_value}"
        elif query_type == "causal_chain":
            search_query = f"Causes and effects of {query_value}"

        # Perform search
        results = await graphiti.search(search_query, top_k=limit)

        # Format for consistency
        formatted_nodes = []
        context_lines = []

        if "results" in results:
            for r in results["results"]:
                formatted_nodes.append(
                    {"name": r["name"], "summary": r["summary"], "score": r["score"]}
                )
                context_lines.append(f"- {r['name']}: {r['summary']}")

        return {
            "status": "success",
            "nodes": formatted_nodes,
            "context": "\n".join(context_lines),
            "search_results": results,
        }

    except Exception as e:
        logger.error(f"Graph query failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "context": f"Error querying graph: {str(e)}",
        }


@tool
async def query_graph_natural(
    question: str,
    time_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Query the knowledge graph using natural language.
    """
    try:
        graphiti = _get_graphiti()

        full_query = question
        if time_filter:
            full_query = f"{question} (Time context: {time_filter})"

        results = await graphiti.search(full_query, top_k=10)

        context_lines = []
        if "results" in results:
            for r in results["results"]:
                context_lines.append(f"- {r['name']}: {r['summary']}")

        return {
            "status": "success",
            "context": (
                "\n".join(context_lines) if context_lines else "No results found."
            ),
            "raw_results": results,
        }

    except Exception as e:
        logger.error(f"Natural language graph query failed: {e}")
        return {"status": "error", "error": str(e), "context": f"Error: {str(e)}"}
