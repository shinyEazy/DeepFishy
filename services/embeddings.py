import hashlib
from datetime import datetime
from dataclasses import dataclass
from typing import List, Dict, Any
from langchain_text_splitters import RecursiveCharacterTextSplitter

from core.logging import logger


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
    """Service for chunking articles into Milvus-ready pieces.

    Handles fixed-size field allocation per chunk:
    - Title:   max 256 chars
    - Sapo:    max 768 chars
    - Content: max 1024 chars (per chunk)
    - Total:   ~2048 chars per chunk

    Embedding is delegated to the embedding provider (e.g. Gemini API)
    via the BaseEmbedding interface — this service does NOT call any
    embedding API itself.
    """

    def __init__(self):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=1024,
            chunk_overlap=102,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )
        logger.info("Initialized EmbeddingService")

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

    def process_article(self, article_json: Dict[str, Any]) -> List[ChunkedArticle]:
        """
        Process a single article into chunked articles ready for embedding.

        Allocation strategy:
        - Title: max 256 chars (Vietnamese titles ~50-150 chars)
        - Sapo: max 768 chars (lead paragraph ~200-600 chars)
        - Content: max 1024 chars (article body chunks)
        - Total: ~2048 chars per chunk (fits easily in 8000 char Milvus limit)

        Args:
            article_json: Article data from JSON.
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
