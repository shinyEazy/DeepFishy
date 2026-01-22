"""Tool for querying the Neo4j knowledge graph."""

from typing import Dict, Any, Optional, List, Literal
from langchain_core.tools import tool

from app.core.logging import logger


def _get_query_service():
    """Lazy import to avoid circular imports and side effects on module load."""
    from app.engine.graph_rag.neo4j_ingestion import get_graph_query_service

    return get_graph_query_service()


@tool
def query_knowledge_graph(
    query_type: Literal["time_period", "causal_chain", "search", "related"],
    query_value: str,
    limit: int = 10,
    direction: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Query the Neo4j knowledge graph for entities, events, and relationships.

    Supports four query types:

    1. "time_period": Find events and entities in a specific time period
       - query_value: Time period string (e.g., "Q3/2025", "10/2025", "2025")
       - Example: query_knowledge_graph("time_period", "Q4/2025")
       - Returns: Events and entities with matching time_period

    2. "causal_chain": Find cause-effect chain for an entity or event
       - query_value: Entity or event name
       - direction: "downstream" (effects) or "upstream" (causes)
       - Example: query_knowledge_graph("causal_chain", "FED interest rate", direction="downstream")
       - Returns: Chain of related events showing cause-effect relationships

    3. "search": Full-text search across all entities
       - query_value: Search term
       - Example: query_knowledge_graph("search", "VNINDEX")
       - Returns: Entities matching the search term

    4. "related": Find entities directly related to a given entity
       - query_value: Entity name
       - Example: query_knowledge_graph("related", "VCB")
       - Returns: All entities with direct relationships

    Args:
        query_type: One of "time_period", "causal_chain", "search", "related"
        query_value: The search value or entity name
        limit: Maximum number of results (default: 10)
        direction: For causal_chain only - "downstream" or "upstream"

    Returns:
        Dictionary containing:
        - status: "success" or "error"
        - nodes: List of matched nodes
        - relationships: List of matched relationships
        - paths: List of causal paths (for causal_chain queries)
        - query_time_ms: Query execution time
        - context: Formatted text for LLM consumption

    Example Queries:

    1. Find events in Q4/2025:
       >>> query_knowledge_graph("time_period", "Q4/2025")

    2. Find what FED policy caused:
       >>> query_knowledge_graph("causal_chain", "FED", direction="downstream")

    3. Find causes of VND depreciation:
       >>> query_knowledge_graph("causal_chain", "VND depreciation", direction="upstream")

    4. Search for banking sector entities:
       >>> query_knowledge_graph("search", "ngân hàng")

    5. Find entities related to VNINDEX:
       >>> query_knowledge_graph("related", "VNINDEX")
    """
    try:
        service = _get_query_service()

        if query_type == "time_period":
            result = service.query_by_time_period(query_value, limit=limit)

        elif query_type == "causal_chain":
            # Default to downstream if not specified
            chain_direction = direction or "downstream"
            if chain_direction not in ["downstream", "upstream"]:
                return {
                    "status": "error",
                    "error": f"Invalid direction: {chain_direction}. Use 'downstream' or 'upstream'",
                    "context": "Invalid direction parameter",
                }
            result = service.query_causal_chain(query_value, direction=chain_direction)

        elif query_type == "search":
            result = service.search_entities(query_value, limit=limit)

        elif query_type == "related":
            result = service.get_related_entities(query_value, limit=limit)

        else:
            return {
                "status": "error",
                "error": f"Unknown query_type: {query_type}",
                "valid_types": ["time_period", "causal_chain", "search", "related"],
                "context": f"Error: Unknown query type '{query_type}'",
            }

        logger.info(
            f"Graph query complete: {result.total_results} results, "
            f"{result.query_time_ms:.1f}ms"
        )

        return {
            "status": "success",
            "nodes": result.nodes[:limit],
            "relationships": result.relationships[:limit],
            "paths": result.paths if hasattr(result, "paths") else [],
            "query_time_ms": result.query_time_ms,
            "total_results": result.total_results,
            "context": result.context_text,
        }

    except Exception as e:
        logger.error(f"Graph query failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "nodes": [],
            "relationships": [],
            "context": f"Error querying knowledge graph: {str(e)}",
        }


@tool
def query_graph_natural(
    question: str,
    time_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Query the knowledge graph using natural language.

    This is a higher-level interface that interprets natural language
    questions and routes them to appropriate graph queries.

    Args:
        question: Natural language question about the knowledge graph
        time_filter: Optional time period filter (e.g., "Q4/2025")

    Returns:
        Dictionary with query results and formatted context

    Example:
        >>> query_graph_natural("What caused the USD exchange rate increase?")
        >>> query_graph_natural("What events happened in Q3/2025?", time_filter="Q3/2025")
    """
    try:
        service = _get_query_service()
        question_lower = question.lower()

        # Detect query intent from question
        if time_filter or any(
            kw in question_lower
            for kw in ["khi nào", "thời gian", "q1", "q2", "q3", "q4", "tháng", "năm"]
        ):
            # Time-based query
            time_value = time_filter or _extract_time_from_question(question)
            if time_value:
                result = service.query_by_time_period(time_value)
            else:
                result = service.search_entities(question)

        elif any(
            kw in question_lower
            for kw in [
                "nguyên nhân",
                "gây ra",
                "dẫn đến",
                "tác động",
                "ảnh hưởng",
                "caused",
                "effect",
            ]
        ):
            # Causal chain query
            # Extract entity from question
            entity = _extract_entity_from_question(question)
            if "nguyên nhân" in question_lower or "caused" in question_lower:
                result = service.query_causal_chain(entity, direction="upstream")
            else:
                result = service.query_causal_chain(entity, direction="downstream")

        elif any(kw in question_lower for kw in ["liên quan", "related", "connection"]):
            # Related entities query
            entity = _extract_entity_from_question(question)
            result = service.get_related_entities(entity)

        else:
            # Default to search
            result = service.search_entities(question)

        return {
            "status": "success",
            "nodes": result.nodes,
            "relationships": result.relationships,
            "context": result.context_text,
            "query_time_ms": result.query_time_ms,
        }

    except Exception as e:
        logger.error(f"Natural language graph query failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "context": f"Error: {str(e)}",
        }


def _extract_time_from_question(question: str) -> Optional[str]:
    """Extract time period from question text."""
    import re

    # Match Q1-Q4/year patterns
    match = re.search(r"Q[1-4]/?\d{4}", question, re.IGNORECASE)
    if match:
        return match.group()

    # Match month/year patterns
    match = re.search(r"(\d{1,2})/(\d{4})", question)
    if match:
        return match.group()

    # Match year only
    match = re.search(r"\b(20\d{2})\b", question)
    if match:
        return match.group()

    return None


def _extract_entity_from_question(question: str) -> str:
    """Extract main entity from question text."""
    # Simple extraction - could be enhanced with NER
    # Remove common question words
    stopwords = [
        "what",
        "how",
        "why",
        "when",
        "where",
        "which",
        "nguyên nhân",
        "là gì",
        "như thế nào",
        "tại sao",
        "gây ra",
        "dẫn đến",
        "ảnh hưởng",
        "tác động",
        "liên quan",
        "của",
        "về",
        "đến",
        "cho",
    ]

    result = question
    for word in stopwords:
        result = result.replace(word, " ")

    # Clean up and return
    result = " ".join(result.split())
    return result.strip() or question
