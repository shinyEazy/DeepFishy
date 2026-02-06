from abc import ABC, abstractmethod
from typing import List


class BaseEmbedding(ABC):
    """Abstract base class for embedding models."""

    @abstractmethod
    def encode(self, text: str) -> List[float]:
        """
        Encode a single string into an embedding vector.

        Args:
            text: The text to encode.

        Returns:
            A list of floats representing the embedding.
        """
        pass

    @abstractmethod
    def batch_encode(self, texts: List[str]) -> List[List[float]]:
        """
        Encode a list of strings into embedding vectors.

        Args:
            texts: A list of texts to encode.

        Returns:
            A list of lists of floats, where each inner list is an embedding.
        """
        pass
