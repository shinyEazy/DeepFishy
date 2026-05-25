"""Knowledge search tool for agent to query local financial knowledge base."""

from typing import Optional, List, Dict, Any
from langchain_core.tools import tool

from deepfishy.shared.logging import logger


def _get_rag_service():
    """Lazy import to avoid circular imports and side effects on module load."""
    from deepfishy.features.knowledge_graph.rag import get_rag_service

    return get_rag_service()


@tool
def search_local_knowledge(
    query: str,
    top_k: int = 5,
    category: Optional[str] = None,
) -> Dict[str, Any]:
    """Search the local financial knowledge base for relevant information.

    Use this tool to find information from crawled Vietnamese financial articles
    and news stored in the local vector database. This is useful for:
    - Finding recent financial news and analysis
    - Researching specific companies, stocks, or market trends
    - Getting context about Vietnamese economy and business

    Args:
        query: Natural language search query in Vietnamese or English.
               Be specific about what information you're looking for.
        top_k: Number of results to return (default: 5, max: 20).
               Use fewer results for focused queries, more for broader research.
        category: Optional category filter (e.g., 'tài chính', 'chứng khoán').
                  Leave empty to search all categories.

    Returns:
        Dictionary containing:
        - context: Formatted text with relevant document contents
        - sources: List of source URLs and metadata
        - num_results: Number of documents found
        - query: The original query

    Example queries:
        - "Tình hình thị trường chứng khoán Việt Nam tuần qua"
        - "Cổ phiếu ngành ngân hàng VPBank, ACB"
        - "Dự báo tăng trưởng kinh tế Việt Nam 2025"
        - "AI and technology stocks market impact"
    """
    try:
        # Validate top_k
        top_k = max(1, min(top_k, 20))

        logger.info(
            f"Knowledge search: query='{query}', top_k={top_k}, category={repr(category)}"
        )

        rag_service = _get_rag_service()

        result = rag_service.search_with_context(
            query=query,
            top_k=top_k,
            category=category,
            include_metadata=True,
        )

        logger.debug(
            f"Knowledge search result: num_results={result.get('num_results', 'unknown')}"
        )
        return result

    except Exception as e:
        logger.error(f"Knowledge search failed: {e}", exc_info=True)
        return {
            "context": f"Error searching knowledge base: {str(e)}",
            "sources": [],
            "query": query,
            "num_results": 0,
            "error": str(e),
        }


@tool
def get_knowledge_base_stats() -> Dict[str, Any]:
    """Get statistics about the local knowledge base.

    Use this tool to check the current state of the knowledge base,
    including total number of indexed documents and connection status.

    Returns:
        Dictionary containing:
        - total_documents: Number of indexed documents
        - collection_name: Name of the Milvus collection
        - status: Connection status ('connected' or 'error')
    """
    try:
        rag_service = _get_rag_service()
        stats = rag_service.get_collection_stats()
        return stats

    except Exception as e:
        logger.error(f"Failed to get knowledge base stats: {e}")
        return {
            "total_documents": 0,
            "collection_name": "unknown",
            "status": "error",
            "error": str(e),
        }


@tool
def search_financial_news(
    query: str,
    num_results: int = 5,
) -> str:
    """Search for Vietnamese financial news and articles in the local database.

    This is a simplified version of search_local_knowledge that returns
    a formatted text response suitable for direct use in conversation.

    Args:
        query: Search query about financial topics (Vietnamese or English)
        num_results: Number of articles to retrieve (1-10, default: 5)

    Returns:
        Formatted string with relevant article excerpts and sources
    """
    try:
        num_results = max(1, min(num_results, 10))

        rag_service = _get_rag_service()

        results = rag_service.search(
            query=query,
            top_k=num_results,
        )

        if not results:
            return f"Không tìm thấy thông tin liên quan đến: {query}"

        # Format results as readable text
        output_parts = [f"Kết quả tìm kiếm cho: {query}\n"]

        for i, result in enumerate(results, 1):
            output_parts.append(f"\n📰 [{i}] {result.url}")
            if result.category:
                output_parts.append(f"   Danh mục: {result.category}")
            if result.tags:
                output_parts.append(f"   Tags: {', '.join(result.tags[:5])}")
            output_parts.append(f"   Nội dung: {result.content[:500]}...")
            output_parts.append("")

        return "\n".join(output_parts)

    except Exception as e:
        logger.error(f"Financial news search failed: {e}")
        return f"Lỗi khi tìm kiếm: {str(e)}"
