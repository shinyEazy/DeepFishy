"""Chunk tracker for deduplication across pipeline iterations.

Prevents the same article chunks from being processed multiple times
during the iterative research pipeline.
"""

from typing import List, Set
from dataclasses import dataclass

from deepfishy.features.knowledge_graph.rag import SearchResult
from deepfishy.shared.logging import logger


@dataclass
class ChunkId:
    """Unique identifier for a chunk."""

    url: str
    chunk_index: int

    def __hash__(self):
        return hash((self.url, self.chunk_index))

    def __eq__(self, other):
        if not isinstance(other, ChunkId):
            return False
        return self.url == other.url and self.chunk_index == other.chunk_index


class ChunkTracker:
    """
    Track processed chunks to prevent duplicates within a session.

    This is used by the iterative research pipeline to ensure that
    the same article chunk is not added to the knowledge graph
    multiple times across different search queries and iterations.

    Example:
        >>> tracker = ChunkTracker()
        >>> results = rag_service.search("query 1")
        >>> new_results = tracker.filter_new(results)  # All pass
        >>> more_results = rag_service.search("query 2")
        >>> new_only = tracker.filter_new(more_results)  # Duplicates removed
        >>> tracker.reset()  # Clear for new session
    """

    def __init__(self):
        """Initialize an empty chunk tracker."""
        self._processed: Set[ChunkId] = set()

    def _make_id(self, result: SearchResult) -> ChunkId:
        """Create a unique identifier for a search result."""
        return ChunkId(url=result.url, chunk_index=result.chunk_index)

    def is_processed(self, result: SearchResult) -> bool:
        """Check if a chunk has already been processed."""
        return self._make_id(result) in self._processed

    def mark_processed(self, result: SearchResult) -> None:
        """Mark a chunk as processed."""
        self._processed.add(self._make_id(result))

    def filter_new(self, results: List[SearchResult]) -> List[SearchResult]:
        """
        Filter out already-processed chunks and mark new ones.

        Args:
            results: List of search results to filter

        Returns:
            List of search results that haven't been processed yet
        """
        new_results = []
        duplicates = 0

        for result in results:
            chunk_id = self._make_id(result)
            if chunk_id not in self._processed:
                self._processed.add(chunk_id)
                new_results.append(result)
            else:
                duplicates += 1

        if duplicates > 0:
            logger.debug(
                f"ChunkTracker: Filtered {duplicates} duplicates, kept {len(new_results)} new"
            )

        return new_results

    def count(self) -> int:
        """Get the number of processed chunks."""
        return len(self._processed)

    def reset(self) -> None:
        """Clear all tracked chunks for a new session."""
        count = len(self._processed)
        self._processed.clear()
        logger.debug(f"ChunkTracker: Reset, cleared {count} entries")

    def get_processed_urls(self) -> Set[str]:
        """Get set of unique URLs that have been processed."""
        return {chunk_id.url for chunk_id in self._processed}

    def __len__(self) -> int:
        """Return the number of processed chunks."""
        return len(self._processed)

    def __repr__(self) -> str:
        return f"ChunkTracker(processed={len(self._processed)})"
