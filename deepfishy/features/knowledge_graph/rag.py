"""RAG service for local knowledge search."""

import threading
from dataclasses import dataclass
from typing import Any, Optional

from embedding.base_embedding import BaseEmbedding

from deepfishy.infra.llm.embedding_factory import (
    get_embedding_dim,
    get_embedding_provider,
)
from deepfishy.infra.vector.milvus import MilvusService
from deepfishy.shared.logging import logger


@dataclass
class SearchResult:
    """Represents a single search result from the RAG system."""

    content: str
    url: str
    category: str
    date_ts: int
    tags: list[str]
    score: float
    chunk_index: int


class RAGService:
    """Retrieval-Augmented Generation service backed by Milvus."""

    def __init__(
        self,
        embedding_provider: Optional[BaseEmbedding] = None,
        milvus_service: Optional[MilvusService] = None,
        model_name: str | None = None,
    ):
        self._embedding_provider = embedding_provider
        self._milvus_service = milvus_service
        self._model_name = model_name
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Lazy initialization of dependencies."""
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
        except Exception as error:
            logger.error(f"Failed to initialize RAGService: {error}")
            raise

    def search(
        self,
        query: str,
        top_k: int = 5,
        category: Optional[str] = None,
        date_range: Optional[tuple] = None,
    ) -> list[SearchResult]:
        """Search the local knowledge base using semantic similarity."""
        self._ensure_initialized()

        try:
            query_embedding = self._embedding_provider.encode(query)
            if not query_embedding:
                logger.error("Failed to generate query embedding")
                return []

            logger.debug(f"Query embedding generated. Dimension: {len(query_embedding)}")
            logger.info(
                f"Searching Milvus for top {top_k} results with category_filter={repr(category)}"
            )
            results = self._milvus_service.search(
                query_embedding=query_embedding,
                top_k=top_k,
                category_filter=category,
                date_range=date_range,
            )

            search_results = [
                SearchResult(
                    content=result.get("content", ""),
                    url=result.get("url", ""),
                    category=result.get("category", ""),
                    date_ts=result.get("date_ts", 0),
                    tags=result.get("tags", []),
                    score=result.get("score", 0.0),
                    chunk_index=result.get("chunk_index", 0),
                )
                for result in results
            ]

            logger.info(f"RAG search returned {len(search_results)} results")
            if not search_results:
                logger.warning(f"RAG search returned 0 results for query: '{query}'")
            return search_results
        except Exception as error:
            logger.error(f"RAG search failed: {error}", exc_info=True)
            return []

    def search_with_context(
        self,
        query: str,
        top_k: int = 5,
        category: Optional[str] = None,
        date_range: Optional[tuple] = None,
        include_metadata: bool = True,
    ) -> dict[str, Any]:
        """Search and return results formatted for LLM context injection."""
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

        context_parts = []
        sources = []

        for index, result in enumerate(results, start=1):
            if include_metadata:
                context_parts.append(
                    f"[Document {index}]\n"
                    f"Source: {result.url}\n"
                    f"Category: {result.category if result.category else 'N/A'}\n"
                    f"Tags: {', '.join(result.tags) if result.tags else 'N/A'}\n"
                    f"Content: {result.content}\n"
                )
            else:
                context_parts.append(f"[Document {index}]\n{result.content}\n")

            sources.append(
                {
                    "url": result.url,
                    "category": result.category,
                    "tags": result.tags,
                    "relevance_score": result.score,
                }
            )

        return {
            "context": "\n".join(context_parts),
            "sources": sources,
            "query": query,
            "num_results": len(results),
        }

    def get_collection_stats(self) -> dict[str, Any]:
        """Get statistics about the knowledge base collection."""
        self._ensure_initialized()

        try:
            count = self._milvus_service.count()
            return {
                "total_documents": count,
                "collection_name": self._milvus_service.collection_name,
                "status": "connected",
            }
        except Exception as error:
            logger.error(f"Failed to get collection stats: {error}")
            return {
                "total_documents": 0,
                "collection_name": "unknown",
                "status": "error",
                "error": str(error),
            }

    def close(self) -> None:
        """Clean up resources."""
        try:
            if self._milvus_service:
                self._milvus_service.disconnect()
            logger.info("RAGService closed")
        except Exception as error:
            logger.warning(f"Error closing RAGService: {error}")


_rag_service_instance: Optional[RAGService] = None
_rag_service_lock = threading.Lock()


def get_rag_service() -> RAGService:
    """Get or create the singleton RAGService instance."""
    global _rag_service_instance
    if _rag_service_instance is None:
        with _rag_service_lock:
            if _rag_service_instance is None:
                _rag_service_instance = RAGService()
    return _rag_service_instance


__all__ = ["RAGService", "SearchResult", "get_rag_service"]
