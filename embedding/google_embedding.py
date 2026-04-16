from typing import List
import time
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from embedding.base_embedding import BaseEmbedding
from deepfishy.infra.config.model_registry import get_embedding_config
from deepfishy.shared.logging import logger


class GoogleEmbedding(BaseEmbedding):
    """
    Google Gemini embedding provider.

    Note: LangChain's GoogleGenerativeAIEmbeddings handles batching internally
    (Google API max is 100 texts per request). We just add retry logic.
    """

    MAX_RETRIES = 3
    RETRY_DELAY = 2  # seconds

    def __init__(self, model_name: str = "gemini-embedding-001"):
        """
        Initialize the Google embedding model.

        Args:
            model_name: The name of the model in config.yaml.
        """
        self.model_name = model_name
        self.config = get_embedding_config(model_name)

        if not self.config:
            raise ValueError(f"Model '{model_name}' not found in config.yaml")

        # LangChain handles batching internally (max 100 per API call)
        self.client = GoogleGenerativeAIEmbeddings(
            model=self.config.get("model"),
            google_api_key=self.config.get("api_key"),
            output_dimensionality=self.config.get("output_dimensionality"),
        )
        logger.info(
            f"Initialized GoogleEmbedding with model: {self.config.get('model')}"
        )

    def encode(self, text: str) -> List[float]:
        """Encode a single text with retry logic."""
        for attempt in range(self.MAX_RETRIES):
            try:
                return self.client.embed_query(text)
            except Exception as e:
                if attempt < self.MAX_RETRIES - 1:
                    wait_time = self.RETRY_DELAY * (attempt + 1)
                    logger.warning(
                        f"Embed query failed (attempt {attempt + 1}/{self.MAX_RETRIES}): {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(
                        f"Embed query failed after {self.MAX_RETRIES} attempts: {e}"
                    )
                    raise

    def batch_encode(self, texts: List[str]) -> List[List[float]]:
        """
        Encode a list of texts with retry logic.

        Note: LangChain handles internal batching (max 100 texts per API call).

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        logger.info(f"Generating embeddings for {len(texts)} texts...")

        for attempt in range(self.MAX_RETRIES):
            try:
                embeddings = self.client.embed_documents(texts)
                logger.info(f"✓ Generated {len(embeddings)} embeddings")
                return embeddings
            except Exception as e:
                if attempt < self.MAX_RETRIES - 1:
                    wait_time = self.RETRY_DELAY * (attempt + 1)
                    logger.warning(
                        f"Batch embed failed (attempt {attempt + 1}/{self.MAX_RETRIES}): {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(
                        f"Batch embed failed after {self.MAX_RETRIES} attempts: {e}"
                    )
                    raise


if __name__ == "__main__":
    google_emb = GoogleEmbedding(model_name="gemini-embedding-001")
    vec = google_emb.encode("Hello world")
    logger.info(f"Encode success. Vector length: {len(vec)}")
    batch_vec = google_emb.batch_encode(["Hello", "World"])
    logger.info(f"Batch encode success. Number of vectors: {len(batch_vec)}")
