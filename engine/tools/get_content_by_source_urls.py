"""Tool for retrieving detailed content from Milvus based on source URLs from Neo4j nodes."""

from typing import List, Dict, Any
from langchain_core.tools import tool

from core.logging import logger


def _get_milvus_service():
    """Lazy import to avoid circular imports."""
    from services.milvus import MilvusService

    return MilvusService()


@tool
def get_content_by_source_urls(
    source_urls: List[str],
    max_chunks_per_url: int = 3,
) -> Dict[str, Any]:
    """
    Retrieve detailed content from Milvus for given source URLs.

    Use this after querying the knowledge graph to get full text content
    of documents referenced by graph nodes. This bridges Neo4j entities
    to their original detailed content stored in Milvus.

    Workflow:
    1. Query Neo4j using query_knowledge_graph → get nodes with source_url
    2. Call this tool with those source_urls
    3. Get detailed content to use in report writing

    Args:
        source_urls: List of document URLs from Neo4j nodes (from source_url property)
        max_chunks_per_url: Maximum chunks to return per URL (default: 3)

    Returns:
        Dictionary with:
        - contents: List of {url, chunks: [{content, chunk_index}]}
        - total_chunks: Total number of chunks retrieved
        - context: Formatted context string for LLM consumption
        - status: "success" or "error"

    Example:
        >>> # First query the knowledge graph
        >>> graph_result = query_knowledge_graph("search", "VNINDEX")
        >>> # Extract source_urls from nodes
        >>> urls = [n.get("source_url") for n in graph_result["nodes"] if n.get("source_url")]
        >>> # Get detailed content
        >>> content = get_content_by_source_urls(urls)
        >>> print(content["context"])
    """
    if not source_urls:
        return {
            "status": "error",
            "error": "No source URLs provided",
            "contents": [],
            "total_chunks": 0,
            "context": "No source URLs provided to retrieve content.",
        }

    # Filter out None and empty strings
    valid_urls = [url for url in source_urls if url and isinstance(url, str)]

    if not valid_urls:
        return {
            "status": "error",
            "error": "No valid URLs in provided list",
            "contents": [],
            "total_chunks": 0,
            "context": "No valid URLs provided.",
        }

    try:
        milvus = _get_milvus_service()

        # Query Milvus for each URL
        all_contents = []
        total_chunks = 0

        for url in valid_urls[:10]:  # Limit to 10 URLs to avoid overload
            try:
                # Load collection
                milvus.collection.load()

                # Query by doc_url
                results = milvus.collection.query(
                    expr=f'doc_url == "{url}"',
                    output_fields=["content", "chunk_index", "doc_url"],
                    limit=max_chunks_per_url,
                )

                if results:
                    chunks = [
                        {
                            "content": r.get("content", ""),
                            "chunk_index": r.get("chunk_index", 0),
                        }
                        for r in results
                    ]
                    # Sort by chunk_index
                    chunks.sort(key=lambda x: x["chunk_index"])

                    all_contents.append(
                        {
                            "url": url,
                            "chunks": chunks,
                        }
                    )
                    total_chunks += len(chunks)

            except Exception as e:
                logger.warning(f"Failed to query content for URL {url}: {e}")
                continue

        # Format as context for LLM
        context_parts = [f"📚 Retrieved content from {len(all_contents)} sources:\n"]

        for content in all_contents:
            context_parts.append(f"\n---\n📰 Source: {content['url']}\n")
            for chunk in content["chunks"]:
                context_parts.append(f"{chunk['content']}\n")

        logger.info(f"Retrieved {total_chunks} chunks from {len(all_contents)} URLs")

        return {
            "status": "success",
            "contents": all_contents,
            "total_chunks": total_chunks,
            "context": "".join(context_parts),
        }

    except Exception as e:
        logger.error(f"Failed to retrieve content by source URLs: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "contents": [],
            "total_chunks": 0,
            "context": f"Error retrieving content: {str(e)}",
        }
