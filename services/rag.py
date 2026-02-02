"""RAG (Retrieval-Augmented Generation) service for local knowledge search."""

import threading
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from core.logging import logger
from core.config import settings
from services.milvus import MilvusService
from services.embedding_factory import get_embedding_provider, get_embedding_dim
from embedding.base_embedding import BaseEmbedding


@dataclass
class SearchResult:
    """Represents a single search result from the RAG system."""

    content: str
    url: str
    category: str
    date_ts: int
    tags: List[str]
    score: float
    chunk_index: int


class RAGService:
    """
    Service for Retrieval-Augmented Generation using local knowledge base.

    Combines embedding service for query vectorization and Milvus for
    semantic search over financial articles.
    """

    def __init__(
        self,
        embedding_provider: Optional[BaseEmbedding] = None,
        milvus_service: Optional[MilvusService] = None,
        model_name: str = None,
    ):
        """
        Initialize RAG service.

        Args:
            embedding_provider: Optional embedding provider instance (created if not provided)
            milvus_service: Optional MilvusService instance (created if not provided)
            model_name: Name of embedding model. If None, uses deepfishy.embedding from config.
        """
        self._embedding_provider = embedding_provider
        self._milvus_service = milvus_service
        self._model_name = model_name
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Lazy initialization of services."""
        if self._initialized:
            return

        try:
            if self._embedding_provider is None:
                self._embedding_provider = get_embedding_provider(self._model_name)

            if self._milvus_service is None:
                self._milvus_service = MilvusService(
                    embedding_dim=get_embedding_dim(self._model_name)
                )

            self._initialized = True
            logger.info("RAGService initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize RAGService: {e}")
            raise

    def search(
        self,
        query: str,
        top_k: int = 5,
        category: Optional[str] = None,
        date_range: Optional[tuple] = None,
    ) -> List[SearchResult]:
        """
        Search the local knowledge base using semantic similarity.

        Args:
            query: Natural language query string
            top_k: Number of results to return (default: 5)
            category: Optional category filter
            date_range: Optional tuple (start_timestamp, end_timestamp)

        Returns:
            List of SearchResult objects sorted by relevance
        """
        self._ensure_initialized()

        try:
            query_embedding = self._embedding_provider.encode(query)

            if not query_embedding:
                logger.error("Failed to generate query embedding")
                return []

            logger.debug(
                f"Query embedding generated. Dimension: {len(query_embedding)}"
            )

            # Search Milvus
            logger.info(
                f"Searching Milvus for top {top_k} results with category_filter={repr(category)}"
            )
            results = self._milvus_service.search(
                query_embedding=query_embedding,
                top_k=top_k,
                category_filter=category,
                date_range=date_range,
            )

            # Convert to SearchResult objects
            search_results = []
            for result in results:
                search_results.append(
                    SearchResult(
                        content=result.get("content", ""),
                        url=result.get("url", ""),
                        category=result.get("category", ""),
                        date_ts=result.get("date_ts", 0),
                        tags=result.get("tags", []),
                        score=result.get("score", 0.0),
                        chunk_index=result.get("chunk_index", 0),
                    )
                )

            logger.info(f"RAG search returned {len(search_results)} results")
            if len(search_results) == 0:
                logger.warning(f"RAG search returned 0 results for query: '{query}'")
            return search_results

        except Exception as e:
            logger.error(f"RAG search failed: {e}", exc_info=True)
            return []

    def search_with_context(
        self,
        query: str,
        top_k: int = 5,
        category: Optional[str] = None,
        date_range: Optional[tuple] = None,
        include_metadata: bool = True,
    ) -> Dict[str, Any]:
        """
        Search and return results formatted for LLM context injection.

        Args:
            query: Natural language query string
            top_k: Number of results to return
            category: Optional category filter
            date_range: Optional tuple (start_timestamp, end_timestamp)
            include_metadata: Whether to include metadata in context

        Returns:
            Dictionary with 'context' string and 'sources' list
        """
        results = self.search(
            query=query,
            top_k=top_k,
            category=category,
            date_range=date_range,
        )

        if not results:
            return {
                "context": "No relevant documents found in the knowledge base.",
                "sources": [],
                "query": query,
            }

        # Build context string for LLM
        context_parts = []
        sources = []

        for i, result in enumerate(results, 1):
            # Format each result
            if include_metadata:
                context_parts.append(
                    f"[Document {i}]\n"
                    f"Source: {result.url}\n"
                    f"Category: {result.category if result.category else 'N/A'}\n"
                    f"Tags: {', '.join(result.tags) if result.tags else 'N/A'}\n"
                    f"Content: {result.content}\n"
                )
            else:
                context_parts.append(f"[Document {i}]\n{result.content}\n")

            sources.append(
                {
                    "url": result.url,
                    "category": result.category,
                    "tags": result.tags,
                    "relevance_score": result.score,
                }
            )

        context = "\n".join(context_parts)

        return {
            "context": context,
            "sources": sources,
            "query": query,
            "num_results": len(results),
        }

    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the knowledge base collection."""
        self._ensure_initialized()

        try:
            count = self._milvus_service.count()
            return {
                "total_documents": count,
                "collection_name": self._milvus_service.collection_name,
                "status": "connected",
            }
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {
                "total_documents": 0,
                "collection_name": "unknown",
                "status": "error",
                "error": str(e),
            }

    def close(self) -> None:
        """Clean up resources."""
        try:
            if self._milvus_service:
                self._milvus_service.disconnect()
            logger.info("RAGService closed")
        except Exception as e:
            logger.warning(f"Error closing RAGService: {e}")


# Singleton instance for reuse across the application
_rag_service_instance: Optional[RAGService] = None
_rag_service_lock = threading.Lock()


def get_rag_service() -> RAGService:
    """Get or create the singleton RAGService instance (thread-safe)."""
    global _rag_service_instance
    if _rag_service_instance is None:
        with _rag_service_lock:
            # Double-check pattern for thread safety
            if _rag_service_instance is None:
                _rag_service_instance = RAGService()
    return _rag_service_instance


if __name__ == "__main__":
    rag_service = get_rag_service()
    search_results = rag_service.search("VNINDEX")
    print(search_results)
    rag_service.close()
