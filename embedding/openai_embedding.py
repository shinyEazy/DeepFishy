from typing import List
import time
from langchain_openai import OpenAIEmbeddings
from embedding.base_embedding import BaseEmbedding
from utils.load_config import get_embedding_config
from core.logging import logger


class OpenAIEmbedding(BaseEmbedding):
    # Default batch size for API calls
    DEFAULT_BATCH_SIZE = 128
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # seconds

    def __init__(self, model_name: str = "text-embedding-3-small"):
        """
        Initialize the OpenAI embedding model.

        Args:
            model_name: The name of the model in config.yaml.
        """
        self.model_name = model_name
        self.config = get_embedding_config(model_name)

        if not self.config:
            raise ValueError(f"Model '{model_name}' not found in config.yaml")

        self.client = OpenAIEmbeddings(
            model=self.config.get("model"),
            api_key=self.config.get("api_key"),
            dimensions=self.config.get("output_dimensionality"),
        )
        self._batch_size = self.config.get("batch_size", self.DEFAULT_BATCH_SIZE)
        logger.info(
            f"Initialized OpenAIEmbedding with model: {self.config.get('model')}, "
            f"batch_size: {self._batch_size}"
        )

    def encode(self, text: str) -> List[float]:
        """Encode a single text with retry logic."""
        for attempt in range(self.MAX_RETRIES):
            try:
                return self.client.embed_query(text)
            except Exception as e:
                if attempt < self.MAX_RETRIES - 1:
                    logger.warning(
                        f"Embed query failed (attempt {attempt + 1}/{self.MAX_RETRIES}): {e}. "
                        f"Retrying in {self.RETRY_DELAY}s..."
                    )
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
                else:
                    logger.error(f"Embed query failed after {self.MAX_RETRIES} attempts: {e}")
                    raise

    def batch_encode(self, texts: List[str], batch_size: int = None) -> List[List[float]]:
        """
        Encode a list of texts with batching and retry logic.
        
        Args:
            texts: List of texts to embed
            batch_size: Override batch size (uses config value if not specified)
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        batch_size = batch_size or self._batch_size
        all_embeddings = []
        total_batches = (len(texts) + batch_size - 1) // batch_size

        logger.info(
            f"Batch encoding {len(texts)} texts in {total_batches} batches "
            f"(batch_size={batch_size})"
        )

        for batch_idx in range(0, len(texts), batch_size):
            batch = texts[batch_idx : batch_idx + batch_size]
            batch_num = batch_idx // batch_size + 1

            for attempt in range(self.MAX_RETRIES):
                try:
                    embeddings = self.client.embed_documents(batch)
                    all_embeddings.extend(embeddings)
                    
                    if batch_num % 10 == 0 or batch_num == total_batches:
                        logger.info(f"Progress: {batch_num}/{total_batches} batches completed")
                    break
                    
                except Exception as e:
                    if attempt < self.MAX_RETRIES - 1:
                        wait_time = self.RETRY_DELAY * (attempt + 1)
                        logger.warning(
                            f"Batch {batch_num}/{total_batches} failed "
                            f"(attempt {attempt + 1}/{self.MAX_RETRIES}): {e}. "
                            f"Retrying in {wait_time}s..."
                        )
                        time.sleep(wait_time)
                    else:
                        logger.error(
                            f"Batch {batch_num}/{total_batches} failed after "
                            f"{self.MAX_RETRIES} attempts: {e}"
                        )
                        raise

        logger.info(f"✓ Generated {len(all_embeddings)} embeddings")
        return all_embeddings


if __name__ == "__main__":
    openai_emb = OpenAIEmbedding(model_name="text-embedding-3-small")
    vec = openai_emb.encode("Hello world")
    logger.info(f"Encode success. Vector length: {len(vec)}")
    batch_vec = openai_emb.batch_encode(["Hello", "World"])
    logger.info(f"Batch encode success. Number of vectors: {len(batch_vec)}")

