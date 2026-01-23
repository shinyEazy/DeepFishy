from typing import List
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from embedding.base_embedding import BaseEmbedding
from utils.load_config import get_embedding_config
from core.logging import logger

class GoogleEmbedding(BaseEmbedding):
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
            
        self.client = GoogleGenerativeAIEmbeddings(
            model=self.config.get("model"),
            google_api_key=self.config.get("api_key")
        )
        logger.info(f"Initialized GoogleEmbedding with model: {self.config.get('model')}")

    def encode(self, text: str) -> List[float]:
        return self.client.embed_query(text)

    def batch_encode(self, texts: List[str]) -> List[List[float]]:
        return self.client.embed_documents(texts)
