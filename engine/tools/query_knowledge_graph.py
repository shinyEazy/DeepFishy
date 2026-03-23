"""Tool for querying the Neo4j knowledge graph."""

import asyncio
from typing import Dict, Any, Optional, Literal

from langchain_core.tools import tool

from core.logging import logger


def _get_graphiti():
    """Lazy import to avoid circular imports."""
    from graph_rag.graphiti_service import get_graphiti_service

    return get_graphiti_service()


def _get_group_id() -> Optional[str]:
    """Get the current session's group_id for scoped graph queries."""
    try:
        from engine.tools.search_and_build_graph import get_current_session_id

        return get_current_session_id()
    except Exception:
        return None


async def _query_knowledge_graph_async(
    query_type: str,
    query_value: str,
    limit: int = 10,
) -> Dict[str, Any]:
    """Async implementation of knowledge graph query."""
    group_id = _get_group_id()
    try:
        graphiti = await _get_graphiti()

        search_query = query_value
        if query_type == "time_period":
            search_query = f"Events in {query_value}"
        elif query_type == "causal_chain":
            search_query = f"Causes and effects of {query_value}"

        # Perform search, scoped to current session
        results = await graphiti.search_facts(
            search_query, limit=limit, group_id=group_id
        )

        # Format for consistency
        formatted_nodes = []
        context_lines = []

        for r in results:
            formatted_nodes.append({"name": r.get("fact", "")})
            context_lines.append(f"- {r.get('fact', '')}")

        return {
            "status": "success",
            "nodes": formatted_nodes,
            "context": (
                "\n".join(context_lines) if context_lines else "No results found."
            ),
            "num_results": len(results),
            "group_id": group_id,
        }

    except Exception as e:
        logger.error(f"Graph query failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "context": f"Error querying graph: {str(e)}",
        }


async def _query_graph_natural_async(
    question: str,
    time_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """Async implementation of natural language graph query."""
    group_id = _get_group_id()
    try:
        graphiti = await _get_graphiti()

        full_query = question
        if time_filter:
            full_query = f"{question} (Time context: {time_filter})"

        # Search scoped to current session's group_id
        results = await graphiti.search_nodes(full_query, limit=10, group_id=group_id)

        context_lines = []
        for r in results:
            name = r.get("name", "")
            summary = r.get("summary", "")
            if name:
                context_lines.append(f"- {name}: {summary}")

        return {
            "status": "success",
            "context": (
                "\n".join(context_lines) if context_lines else "No results found."
            ),
            "num_results": len(results),
            "group_id": group_id,
        }

    except Exception as e:
        logger.error(f"Natural language graph query failed: {e}")
        return {"status": "error", "error": str(e), "context": f"Error: {str(e)}"}


@tool
def query_knowledge_graph(
    query_type: Literal["time_period", "causal_chain", "search", "related"],
    query_value: str,
    limit: int = 10,
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

    Returns:
        Dictionary containing search results
    """
    return asyncio.run(_query_knowledge_graph_async(query_type, query_value, limit))


@tool
def query_graph_natural(
    question: str,
    time_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Query the knowledge graph using natural language.

    Args:
        question: Natural language question to search the knowledge graph
        time_filter: Optional time context filter

    Returns:
        Dictionary with search results and context
    """
    return asyncio.run(_query_graph_natural_async(question, time_filter))
