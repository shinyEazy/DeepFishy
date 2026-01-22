"""PDF parser using Marker - converts PDFs to markdown."""

from typing import List, Optional
from pathlib import Path
import tempfile
import requests
import os

from app.core.logging import logger
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered


class MarkerPDFParser:
    """
    Parser for converting PDFs to markdown using Marker library.

    Features:
    - Fast markdown conversion with high accuracy
    - Table extraction and preservation
    - OCR support for scanned documents
    - Layout detection and reading order
    """

    def __init__(
        self,
        use_llm: bool = False,
    ):
        """
        Initialize Marker PDF parser.

        Args:
            use_llm: Use LLM to improve conversion quality (requires GOOGLE_API_KEY)
        """
        self.use_llm = use_llm
        llm_adapter = None
        if self.use_llm:
            from marker.llm import GeminiV2Adapter

            # This will automatically use GOOGLE_API_KEY from env
            llm_adapter = GeminiV2Adapter()

        # Initialize the PDF converter with model artifacts
        artifact_dict = create_model_dict()
        self.converter = PdfConverter(
            artifact_dict=artifact_dict, llm_adapter=llm_adapter
        )

        # Initialize the PDF converter with model artifacts
        artifact_dict = create_model_dict()
        self.converter = PdfConverter(artifact_dict=artifact_dict)

        logger.info(f"Initialized MarkerPDFParser (use_llm={use_llm}) ")

    def parse_from_url(self, pdf_url: str) -> str:
        """
        Parse a PDF from a remote URL and return markdown content.

        Args:
            pdf_url: URL to PDF file

        Returns:
            Markdown content as string

        Raises:
            RuntimeError: If Marker extraction fails
            requests.RequestException: If URL download fails
        """
        logger.info(f"Parsing PDF from URL: {pdf_url}")

        # Download PDF to temporary file
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = os.path.join(tmpdir, "temp.pdf")

            response = requests.get(pdf_url, timeout=30)
            response.raise_for_status()
            with open(tmp_path, "wb") as f:
                f.write(response.content)

            # Convert PDF using Marker
            markdown_content = self._convert_pdf_to_markdown(tmp_path)
            logger.info(f"✅ Parsed PDF from URL ({len(markdown_content)} chars)")
            return markdown_content

    def parse_from_file(self, file_path: str) -> str:
        """
        Parse a local PDF file and return markdown content.

        Args:
            file_path: Path to local PDF file

        Returns:
            Markdown content as string

        Raises:
            FileNotFoundError: If file doesn't exist
            RuntimeError: If Marker conversion fails
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        logger.info(f"Parsing local PDF file: {file_path}")

        # Convert PDF using Marker
        markdown_content = self._convert_pdf_to_markdown(str(file_path))
        logger.info(f"✅ Parsed PDF ({len(markdown_content)} chars)")
        return markdown_content

    def parse_batch(self, pdf_urls: List[str]) -> List[str]:
        """
        Parse multiple PDFs in sequence and return list of markdown strings.

        Args:
            pdf_urls: List of PDF URLs

        Returns:
            List of markdown strings

        Note: Parses sequentially to avoid rate limiting.
              For high-volume ingestion, consider async processing.
        """
        markdowns = []

        for i, pdf_url in enumerate(pdf_urls, 1):
            try:
                logger.info(f"Parsing {i}/{len(pdf_urls)}: {pdf_url}")
                markdown = self.parse_from_url(pdf_url=pdf_url)
                markdowns.append(markdown)
            except Exception as e:
                logger.error(f"Failed to parse {pdf_url}: {e}")
                # Continue with next PDF instead of failing entire batch
                continue

        logger.info(f"✅ Parsed batch: {len(markdowns)}/{len(pdf_urls)} PDFs")
        return markdowns

    def _convert_pdf_to_markdown(self, file_path: str) -> str:
        """
        Convert PDF file to markdown using Marker.

        Args:
            file_path: Path to PDF file

        Returns:
            Markdown content

        Raises:
            RuntimeError: If conversion fails
        """
        try:
            # Convert document using Marker's PdfConverter
            rendered = self.converter(file_path, langs=["vi"])

            # Extract text (markdown), metadata, and images from rendered output
            markdown_content, _, images = text_from_rendered(rendered)

            if not markdown_content:
                raise RuntimeError("Marker conversion returned empty content")

            return markdown_content

        except Exception as e:
            logger.error(f"Failed to convert PDF with Marker: {e}")
            raise RuntimeError(f"Marker PDF conversion failed: {e}") from e


if __name__ == "__main__":
    parser = MarkerPDFParser(use_llm=True)
    markdown = parser.parse_from_file(
        "../../../../data/pdfs/MBB_2025_12_04_SSIResearch08122025094945.pdf"
    )
    print(markdown)
