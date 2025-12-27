"""PDF parser using Mineru API for LLM-ready content extraction."""

from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

from app.core.logging import logger
from app.services.mineru import MineruService


class MineruPDFParser:
    """
    Parser for converting PDFs to structured, LLM-ready markdown content.

    Uses Mineru API to extract and structure PDF content with:
    - Markdown formatting preservation
    - Table extraction
    - Mathematical formula support (optional)
    - Language-aware processing (Vietnamese by default)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        language: str = "vi",
        enable_formula: bool = False,
        enable_table: bool = True,
    ):
        """
        Initialize PDF parser.

        Args:
            api_key: Mineru API key (defaults to env var MINERU_API_KEY)
            language: Document language (default: "vi" for Vietnamese)
            enable_formula: Whether to extract mathematical formulas
            enable_table: Whether to extract and structure tables
        """
        self.mineru_service = MineruService(api_key=api_key)
        self.language = language
        self.enable_formula = enable_formula
        self.enable_table = enable_table

        logger.info(
            f"Initialized MineruPDFParser (language={language}, "
            f"formula={enable_formula}, table={enable_table})"
        )

    def parse_from_url(
        self,
        pdf_url: str,
        doc_title: Optional[str] = None,
        category: str = "PDF",
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Parse a PDF from a remote URL.

        Args:
            pdf_url: URL to PDF file
            doc_title: Document title (extracted from URL if not provided)
            category: Document category for RAG metadata
            tags: List of tags for categorization

        Returns:
            Dictionary with structure compatible with embedding pipeline:
            {
                "url": str,
                "title": str,
                "sapo": str (first 768 chars of content),
                "content": str (full markdown content),
                "date": str (current date),
                "category": str,
                "tags": List[str],
                "source": str ("mineru_pdf")
            }

        Raises:
            RuntimeError: If Mineru extraction fails
            requests.RequestException: If API call fails
        """
        logger.info(f"Parsing PDF from URL: {pdf_url}")

        # Extract using Mineru
        result = self.mineru_service.extract_from_url(
            pdf_url=pdf_url,
            language=self.language,
            enable_formula=self.enable_formula,
            enable_table=self.enable_table,
        )

        markdown_content = result["markdown"]

        # Extract title from URL if not provided
        if not doc_title:
            doc_title = Path(pdf_url).stem.replace("-", " ").replace("_", " ")

        # Create sapo (summary) from first 768 chars of markdown
        sapo = self._create_sapo(markdown_content, max_chars=768)

        # Prepare article-like structure for embedding pipeline
        article = {
            "url": pdf_url,
            "title": doc_title[:256],
            "sapo": sapo,
            "content": markdown_content,
            "date": datetime.now().strftime("%d/%m/%Y, %H:%M"),
            "category": category,
            "tags": tags or ["pdf", "mineru"],
            "source": "mineru_pdf",
            "extraction_task_id": result.get("task_id"),
        }

        logger.info(f"✅ Parsed PDF: {doc_title} ({len(markdown_content)} chars)")
        return article

    def parse_from_file(
        self,
        file_path: str,
        doc_title: Optional[str] = None,
        category: str = "PDF",
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Parse a local PDF file.

        Note: Requires file to be uploaded to MinIO first to get a URL.
        Use this after uploading the file.

        Args:
            file_path: Path to local PDF file
            doc_title: Document title (filename if not provided)
            category: Document category
            tags: List of tags

        Returns:
            Dictionary with parsed content (same structure as parse_from_url)

        Raises:
            FileNotFoundError: If file doesn't exist
            NotImplementedError: Direct file upload not yet implemented
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        logger.info(f"Parsing local PDF file: {file_path}")

        # Extract title from filename if not provided
        if not doc_title:
            doc_title = file_path.stem.replace("-", " ").replace("_", " ")

        # For now, raise NotImplementedError as Mineru requires URLs
        # In production flow:
        # 1. Upload file to MinIO
        # 2. Get signed URL
        # 3. Call parse_from_url

        raise NotImplementedError(
            "Direct local file parsing requires MinIO upload first. "
            "Please upload file to MinIO and use parse_from_url with the signed URL."
        )

    def parse_batch(
        self,
        pdf_urls: List[str],
        category: str = "PDF",
        tags: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Parse multiple PDFs in sequence.

        Args:
            pdf_urls: List of PDF URLs
            category: Document category (applied to all)
            tags: Tags (applied to all)

        Returns:
            List of parsed articles

        Note: Parses sequentially to avoid rate limiting.
              For high-volume ingestion, consider async processing.
        """
        articles = []

        for i, pdf_url in enumerate(pdf_urls, 1):
            try:
                logger.info(f"Parsing {i}/{len(pdf_urls)}: {pdf_url}")
                article = self.parse_from_url(
                    pdf_url=pdf_url,
                    category=category,
                    tags=tags,
                )
                articles.append(article)
            except Exception as e:
                logger.error(f"Failed to parse {pdf_url}: {e}")
                # Continue with next PDF instead of failing entire batch
                continue

        logger.info(f"✅ Parsed batch: {len(articles)}/{len(pdf_urls)} PDFs")
        return articles

    @staticmethod
    def _create_sapo(content: str, max_chars: int = 768) -> str:
        """
        Create a sapo (summary) from markdown content.

        Extracts first max_chars, trying to break at natural boundaries.

        Args:
            content: Full markdown content
            max_chars: Maximum characters for sapo

        Returns:
            Truncated content with natural break
        """
        if len(content) <= max_chars:
            return content

        # Try to break at paragraph boundary
        truncated = content[:max_chars]

        # Find last paragraph break
        last_break = truncated.rfind("\n\n")
        if last_break > max_chars * 0.7:  # Use if reasonably far
            return truncated[:last_break]

        # Fall back to sentence break
        last_period = truncated.rfind(". ")
        if last_period > max_chars * 0.7:
            return truncated[: last_period + 1]

        # Just truncate
        return truncated.rstrip() + "..."
