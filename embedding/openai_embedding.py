from typing import List, Optional
from langchain_openai import OpenAIEmbeddings
from embedding.base_embedding import BaseEmbedding
from utils.load_config import get_embedding_config
from core.logging import logger

class OpenAIEmbedding(BaseEmbedding):
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
            dimensions=self.config.get("output_dimensionality")
        )
        logger.info(f"Initialized OpenAIEmbedding with model: {self.config.get('model')}")

    def encode(self, text: str) -> List[float]:
        return self.client.embed_query(text)

    def batch_encode(self, texts: List[str]) -> List[List[float]]:
        return self.client.embed_documents(texts)
