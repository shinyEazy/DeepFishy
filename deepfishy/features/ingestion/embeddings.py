"""Article chunking service for vector ingestion."""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

from deepfishy.shared.logging import logger


@dataclass
class ChunkedArticle:
    """Represents a chunked article for Milvus insertion."""

    id: str
    doc_url: str
    content: str
    vector_source: str
    category: str
    date_ts: int
    tags: list[str]
    chunk_index: int


class EmbeddingService:
    """Service for chunking articles into Milvus-ready pieces."""

    def __init__(self):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=1024,
            chunk_overlap=102,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )
        logger.info("Initialized EmbeddingService")

    def _parse_date(self, date_str: str) -> int:
        """Parse date string to Unix timestamp."""
        if not date_str:
            return int(datetime.now().timestamp())

        try:
            dt_obj = datetime.strptime(date_str, "%d/%m/%Y, %H:%M")
            return int(dt_obj.timestamp())
        except (ValueError, TypeError) as error:
            logger.warning(
                f"Failed to parse date '{date_str}': {error}, using current timestamp"
            )
            return int(datetime.now().timestamp())

    def process_article(self, article_json: dict[str, Any]) -> list[ChunkedArticle]:
        """Process a single article into chunked articles ready for embedding."""
        required_fields = ["url", "title", "sapo", "date", "category", "tags"]
        for field in required_fields:
            if field not in article_json:
                logger.error(f"Missing required field: {field}")
                return []

        date_ts = self._parse_date(article_json["date"])

        main_body = article_json.get("content", "").strip() or article_json.get(
            "sapo", ""
        )
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

            chunked_articles.append(
                ChunkedArticle(
                    id=chunk_id,
                    doc_url=article_json["url"],
                    content=enriched_text,
                    vector_source=enriched_text,
                    category=article_json.get("category") or "",
                    date_ts=date_ts,
                    tags=article_json.get("tags") or [],
                    chunk_index=chunk_idx,
                )
            )

        logger.info(
            f"Processed article {article_json['url']} - {len(chunked_articles)} chunks"
        )
        return chunked_articles


__all__ = ["ChunkedArticle", "EmbeddingService"]
