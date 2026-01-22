"""Tool for extracting knowledge graph from text and storing in Neo4j."""

from typing import Dict, Any, Optional, List
from langchain_core.tools import tool
from langchain_core.documents import Document

from app.core.logging import logger


def _get_transformer():
    """Lazy import to avoid circular imports and side effects on module load."""
    from app.engine.graph_rag.transformer import get_graph_transformer

    return get_graph_transformer()


@tool
def extract_to_graph(
    texts: List[str],
    source_urls: Optional[List[str]] = None,
    time_context: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Extract entities, events, and relationships from texts and store in Neo4j.

    Uses LangChain's LLMGraphTransformer to extract structured knowledge:
    - Entities: Organizations, People, Indices, Currencies, Companies
    - Events: Policy changes, market events with timestamps
    - Relationships: CAUSES, AFFECTS, LEADS_TO, PREDICTS, etc.

    The extracted graph is automatically stored in Neo4j for later querying.

    Args:
        texts: List of text contents to process. Each text will be converted
               to a LangChain Document and processed by LLMGraphTransformer.
        source_urls: Optional list of URLs for attribution. Should match
                     the length of texts list for proper source tracking.
        time_context: Optional time context hint (e.g., "Q4/2025", "2025")
                      to help with temporal extraction when not explicit.

    Returns:
        Dictionary containing:
        - status: "success" or "error"
        - nodes_created: Number of nodes created in Neo4j
        - relationships_created: Number of relationships created
        - documents_processed: Number of documents processed
        - node_types: Breakdown by node type
        - relationship_types: Breakdown by relationship type
        - error: Error message if status is "error"

    Example:
        >>> extract_to_graph(
        ...     texts=["FED tăng lãi suất 0.25% vào Q4/2025, gây áp lực lên tỷ giá VND"],
        ...     source_urls=["https://example.com/article1"],
        ...     time_context="Q4/2025"
        ... )
        {
            "status": "success",
            "nodes_created": 3,
            "relationships_created": 1,
            "documents_processed": 1,
            "node_types": {"Organization": 1, "Currency": 1, "Event": 1},
            "relationship_types": {"CAUSES": 1}
        }
    """
    try:
        if not texts:
            return {
                "status": "error",
                "error": "No texts provided",
                "nodes_created": 0,
                "relationships_created": 0,
                "documents_processed": 0,
            }

        logger.info(f"Extracting graph from {len(texts)} text(s)")

        # Convert to LangChain Documents
        documents = []
        for i, text in enumerate(texts):
            metadata = {}

            # Add source URL if available
            if source_urls and i < len(source_urls):
                metadata["source"] = source_urls[i]

            # Add time context if provided
            if time_context:
                metadata["time_context"] = time_context

            documents.append(Document(page_content=text, metadata=metadata))

        # Get transformer and extract
        transformer = _get_transformer()
        result = transformer.extract_and_store(documents)

        logger.info(
            f"Graph extraction complete: {result.nodes_created} nodes, "
            f"{result.relationships_created} relationships"
        )

        return {
            "status": "success",
            "nodes_created": result.nodes_created,
            "relationships_created": result.relationships_created,
            "documents_processed": result.source_documents,
            "node_types": result.node_types,
            "relationship_types": result.relationship_types,
            "errors": result.errors if result.errors else None,
        }

    except Exception as e:
        logger.error(f"Graph extraction failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "nodes_created": 0,
            "relationships_created": 0,
            "documents_processed": 0,
        }


@tool
def get_graph_stats() -> Dict[str, Any]:
    """
    Get statistics about the Neo4j knowledge graph.

    Returns information about the current state of the graph:
    - Total number of nodes
    - Total number of relationships
    - Distribution of node labels
    - Connection status

    Returns:
        Dictionary containing:
        - total_nodes: Number of nodes in the graph
        - total_relationships: Number of relationships
        - node_labels: List of node types and their counts
        - status: "connected" or "error"

    Example:
        >>> get_graph_stats()
        {
            "total_nodes": 150,
            "total_relationships": 230,
            "node_labels": [
                {"labels": ["Organization"], "count": 45},
                {"labels": ["Event"], "count": 60}
            ],
            "status": "connected"
        }
    """
    try:
        transformer = _get_transformer()
        stats = transformer.get_graph_stats()
        return stats
    except Exception as e:
        logger.error(f"Failed to get graph stats: {e}")
        return {
            "status": "error",
            "error": str(e),
            "total_nodes": 0,
            "total_relationships": 0,
        }
