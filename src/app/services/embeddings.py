"""Embedding service for text vectorization via remote API (Kaggle + ngrok)."""

import hashlib
import json
from datetime import datetime
from typing import List, Dict, Any
from dataclasses import dataclass

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.logging import logger


@dataclass
class ChunkedArticle:
    """Represents a chunked article for Milvus insertion."""

    id: str  # MD5 hash of url + chunk index
    doc_url: str
    content: str  # Full enriched text (title + sapo + content)
    vector_source: str  # Text to embed
    category: str
    date_ts: int  # Unix timestamp
    tags: List[str]
    chunk_index: int


class EmbeddingService:
    """Service for text embedding via remote API (Kaggle + ngrok)."""

    def __init__(self, api_url: str, timeout: int = 60, max_retries: int = 3):
        """
        Initialize remote embedding service.

        Args:
            api_url: URL of the remote embedding API endpoint (required)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.api_url = api_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.embedding_dim = 1024

        self.session = self._create_session()
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=1024,
            chunk_overlap=102,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )

        logger.info(f"Initialized EmbeddingService with API URL {api_url}")

    def _create_session(self) -> requests.Session:
        """Create HTTP session with retry strategy."""
        session = requests.Session()
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _parse_date(self, date_str: str) -> int:
        """
        Parse date string to Unix timestamp.

        Args:
            date_str: Date string in format "DD/MM/YYYY, HH:MM", or None

        Returns:
            Unix timestamp, or current timestamp if parsing fails or date_str is None
        """
        if not date_str:
            return int(datetime.now().timestamp())

        try:
            dt_obj = datetime.strptime(date_str, "%d/%m/%Y, %H:%M")
            return int(dt_obj.timestamp())
        except (ValueError, TypeError) as e:
            logger.warning(
                f"Failed to parse date '{date_str}': {e}, using current timestamp"
            )
            return int(datetime.now().timestamp())

    def embed_texts(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """
        Generate embeddings for a list of texts via remote API.

        Args:
            texts: List of texts to embed
            batch_size: Batch size for API calls (API may have limits)

        Returns:
            List of embedding vectors

        Raises:
            Exception: If API call fails after retries
        """
        if not texts:
            return []

        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            batch_embeddings = self._call_api(batch)
            all_embeddings.extend(batch_embeddings)

        return all_embeddings

    def _call_api(self, texts: List[str]) -> List[List[float]]:
        """
        Call the remote embedding API.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors

        Raises:
            Exception: If API call fails
        """
        try:
            payload = {"text": texts}
            response = self.session.post(
                self.api_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self.timeout,
            )
            response.raise_for_status()

            result = response.json()

            if isinstance(result, dict):
                if "embeddings" in result:
                    embeddings = result["embeddings"]
                elif "data" in result:
                    embeddings = result["data"]
                elif "vectors" in result:
                    embeddings = result["vectors"]
                else:
                    logger.warning(
                        f"Unknown response format. Keys: {list(result.keys())}"
                    )
                    raise ValueError(f"Unexpected API response format: {result}")
            elif isinstance(result, list):
                embeddings = result
            else:
                raise ValueError(f"Unexpected API response format: {type(result)}")

            if not isinstance(embeddings, list) or len(embeddings) != len(texts):
                raise ValueError(
                    f"API returned {len(embeddings) if isinstance(embeddings, list) else 'invalid'} embeddings for {len(texts)} texts"
                )

            if embeddings:
                first_embedding = embeddings[0]
                if not isinstance(first_embedding, (list, tuple)):
                    raise ValueError(
                        f"Invalid embedding format: {type(first_embedding)}"
                    )

            return embeddings

        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            raise
        except (ValueError, KeyError, json.JSONDecodeError) as e:
            logger.error(f"Failed to parse API response: {e}")
            raise

    def process_article(self, article_json: Dict[str, Any]) -> List[ChunkedArticle]:
        """
        Process a single article with fixed-size field allocation.

        Allocation strategy:
        - Title: max 256 chars (Vietnamese titles ~50-150 chars)
        - Sapo: max 768 chars (lead paragraph ~200-600 chars)
        - Content: max 1024 chars (article body chunks)
        - Total: 2048 chars per chunk (fits easily in 8000 char Milvus limit)

        Args:
            article_json: Article data from JSON
                Expected keys: url, title, sapo, content, date, category, tags

        Returns:
            List of ChunkedArticle objects ready for Milvus insertion
        """
        required_fields = ["url", "title", "sapo", "date", "category", "tags"]
        for field in required_fields:
            if field not in article_json:
                logger.error(f"Missing required field: {field}")
                return []

        date_ts = self._parse_date(article_json["date"])

        main_body = article_json.get("content", "").strip()
        if not main_body:
            main_body = article_json.get("sapo", "")

        if not main_body:
            logger.warning(f"Empty content for article: {article_json.get('url')}")
            return []

        title = article_json["title"][:256]
        sapo = article_json["sapo"][:768]

        content_chunks = self.splitter.split_text(main_body)

        if not content_chunks:
            logger.warning(
                f"No content chunks generated for: {article_json.get('url')}"
            )
            return []

        chunked_articles = []

        for chunk_idx, content_chunk in enumerate(content_chunks):
            enriched_text = (
                f"Tiêu đề: {title}\nTóm tắt: {sapo}\nNội dung: {content_chunk}"
            )
            chunk_id = hashlib.md5(
                (article_json["url"] + str(chunk_idx)).encode()
            ).hexdigest()

            chunked_article = ChunkedArticle(
                id=chunk_id,
                doc_url=article_json["url"],
                content=enriched_text,
                vector_source=enriched_text,
                category=article_json.get("category") or "",
                date_ts=date_ts,
                tags=article_json.get("tags") or [],
                chunk_index=chunk_idx,
            )

            chunked_articles.append(chunked_article)

        logger.info(
            f"Processed article {article_json['url']} - {len(chunked_articles)} chunks"
        )
        return chunked_articles

    def process_articles_batch(
        self, articles: List[Dict[str, Any]]
    ) -> tuple[List[ChunkedArticle], List[List[float]]]:
        """
        Process a batch of articles and generate embeddings.

        Args:
            articles: List of article JSON objects

        Returns:
            Tuple of (chunked_articles, embeddings)
        """
        chunked_articles = []

        for article in articles:
            chunks = self.process_article(article)
            chunked_articles.extend(chunks)

        if not chunked_articles:
            logger.warning("No chunks generated from batch")
            return [], []

        vector_sources = [chunk.vector_source for chunk in chunked_articles]
        embeddings = self.embed_texts(vector_sources)

        logger.info(
            f"Processed batch: {len(articles)} articles → {len(chunked_articles)} chunks"
        )
        return chunked_articles, embeddings

    def close(self):
        """Close HTTP session."""
        self.session.close()
