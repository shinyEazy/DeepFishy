"""Data loader for ingesting articles and PDFs into the knowledge base."""

from typing import List, Dict, Any, Optional
from pathlib import Path

from app.core.logging import logger
from app.ingestion.parsers.mineru_pdf_parser import MineruPDFParser


class DataLoader:
    """
    Unified data loader for ingesting various document types.

    Supports:
    - PDFs via Mineru API
    - Articles from crawlers
    - Batch ingestion with error handling
    """

    def __init__(self, pdf_parser: Optional[MineruPDFParser] = None):
        """
        Initialize data loader.

        Args:
            pdf_parser: Optional MineruPDFParser instance (created if not provided)
        """
        self.pdf_parser = pdf_parser or MineruPDFParser()
        logger.info("Initialized DataLoader")

    def load_pdf_from_url(
        self,
        pdf_url: str,
        doc_title: Optional[str] = None,
        category: str = "PDF",
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Load and parse a PDF from a remote URL.

        Converts PDF to article-like format compatible with embedding pipeline.

        Args:
            pdf_url: URL to PDF file
            doc_title: Document title (extracted from URL if not provided)
            category: Document category for RAG metadata
            tags: List of tags for categorization

        Returns:
            Article dictionary with parsed PDF content:
            {
                "url": str,
                "title": str,
                "sapo": str,
                "content": str (full markdown),
                "date": str,
                "category": str,
                "tags": List[str],
                "source": str
            }

        Raises:
            RuntimeError: If PDF extraction fails
            requests.RequestException: If URL is invalid or unreachable
        """
        logger.info(f"Loading PDF from URL: {pdf_url}")

        article = self.pdf_parser.parse_from_url(
            pdf_url=pdf_url,
            doc_title=doc_title,
            category=category,
            tags=tags,
        )

        logger.info(f"✅ Loaded PDF: {article['title']}")
        return article

    def load_pdfs_batch(
        self,
        pdf_urls: List[str],
        category: str = "PDF",
        tags: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Load multiple PDFs in batch.

        Args:
            pdf_urls: List of PDF URLs
            category: Document category (applied to all)
            tags: Tags (applied to all)

        Returns:
            List of article dictionaries

        Note: Continues on error to maximize ingestion of valid documents
        """
        logger.info(f"Loading batch of {len(pdf_urls)} PDFs")

        articles = self.pdf_parser.parse_batch(
            pdf_urls=pdf_urls,
            category=category,
            tags=tags,
        )

        logger.info(f"✅ Loaded batch: {len(articles)} PDFs")
        return articles

    def load_articles_from_crawler(
        self,
        articles: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Prepare crawler articles for embedding pipeline.

        Validates and normalizes articles from web crawlers.

        Args:
            articles: List of article dictionaries from crawler

        Returns:
            List of validated article dictionaries

        Expected article fields:
            - url: str
            - title: str
            - sapo: str (summary/lead paragraph)
            - content: str (full article body)
            - date: str (format: "DD/MM/YYYY, HH:MM")
            - category: str
            - tags: List[str]
        """
        logger.info(f"Loading {len(articles)} articles from crawler")

        valid_articles = []
        for article in articles:
            # Validate required fields
            required_fields = [
                "url",
                "title",
                "sapo",
                "content",
                "date",
                "category",
                "tags",
            ]
            if not all(field in article for field in required_fields):
                logger.warning(
                    f"Skipping invalid article: missing required fields. Got: {list(article.keys())}"
                )
                continue

            valid_articles.append(article)

        logger.info(
            f"✅ Loaded {len(valid_articles)}/{len(articles)} valid crawler articles"
        )
        return valid_articles

    def load_articles_from_json(
        self,
        json_file_path: str,
    ) -> List[Dict[str, Any]]:
        """
        Load articles from JSON file (from crawler export).

        Args:
            json_file_path: Path to JSON file with articles

        Returns:
            List of article dictionaries

        Expected JSON structure:
            [
                {
                    "url": "...",
                    "title": "...",
                    "sapo": "...",
                    "content": "...",
                    "date": "...",
                    "category": "...",
                    "tags": [...]
                },
                ...
            ]

        Raises:
            FileNotFoundError: If JSON file doesn't exist
            ValueError: If JSON is invalid
        """
        file_path = Path(json_file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"JSON file not found: {json_file_path}")

        logger.info(f"Loading articles from JSON: {json_file_path}")

        try:
            import json

            with open(file_path, "r", encoding="utf-8") as f:
                articles = json.load(f)

            if not isinstance(articles, list):
                raise ValueError("JSON must contain a list of articles")

            return self.load_articles_from_crawler(articles)

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON file: {e}")
            raise ValueError(f"Invalid JSON: {e}")
        except Exception as e:
            logger.error(f"Error loading JSON file: {e}")
            raise

    @staticmethod
    def create_article_from_dict(
        url: str,
        title: str,
        content: str,
        sapo: Optional[str] = None,
        category: str = "General",
        tags: Optional[List[str]] = None,
        date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create an article dictionary from individual fields.

        Useful for manual article creation or format conversion.

        Args:
            url: Document URL or identifier
            title: Document title (max 256 chars)
            content: Full document content
            sapo: Summary/lead paragraph (max 768 chars). Auto-generated if not provided.
            category: Document category
            tags: List of tags
            date: Publication date (format: "DD/MM/YYYY, HH:MM"). Current date if not provided.

        Returns:
            Article dictionary compatible with embedding pipeline
        """
        from datetime import datetime

        # Auto-generate sapo if not provided
        if not sapo:
            # Use first 768 chars, try to break at paragraph
            if len(content) > 768:
                sapo = content[:768]
                last_break = sapo.rfind("\n\n")
                if last_break > 500:
                    sapo = sapo[:last_break]
                else:
                    sapo = sapo.rstrip() + "..."
            else:
                sapo = content

        # Use current date if not provided
        if not date:
            date = datetime.now().strftime("%d/%m/%Y, %H:%M")

        return {
            "url": url,
            "title": title[:256],
            "sapo": sapo[:768],
            "content": content,
            "date": date,
            "category": category,
            "tags": tags or [],
        }
