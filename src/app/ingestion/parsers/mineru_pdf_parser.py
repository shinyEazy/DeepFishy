"""PDF parser using Mineru API for LLM-ready content extraction."""

import io
import os
import time
import zipfile
import requests
from typing import List, Optional
from pathlib import Path

from app.core.logging import logger


class MineruPDFParser:
    """
    Parser for converting PDFs to markdown using Mineru API.

    Simple wrapper around Mineru API that:
    - Takes PDF URL
    - Calls Mineru API
    - Returns markdown string
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        language: str = "vi",
        enable_formula: bool = True,
        enable_table: bool = True,
        base_url: str = "https://mineru.net/api/v4/extract/task",
        poll_interval: int = 5,
        poll_timeout: int = 300,
    ):
        """
        Initialize PDF parser.

        Args:
            api_key: Mineru API key (defaults to env var MINERU_API_KEY)
            language: Document language (default: "vi" for Vietnamese)
            enable_formula: Whether to extract mathematical formulas
            enable_table: Whether to extract and structure tables
            base_url: Mineru API base URL
            poll_interval: Seconds between status polls
            poll_timeout: Max seconds to wait for task completion
        """
        self.api_key = api_key or os.getenv("MINERU_API_KEY")
        if not self.api_key:
            raise ValueError("MINERU_API_KEY not found in environment or parameters")

        self.language = language
        self.enable_formula = enable_formula
        self.enable_table = enable_table
        self.base_url = base_url
        self.poll_interval = poll_interval
        self.poll_timeout = poll_timeout

        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        logger.info(
            f"Initialized MineruPDFParser (language={language}, "
            f"formula={enable_formula}, table={enable_table})"
        )

    def parse_from_url(self, pdf_url: str) -> str:
        """
        Parse a PDF from a remote URL and return markdown.

        Args:
            pdf_url: URL to PDF file

        Returns:
            Markdown-formatted string with the extracted PDF content

        Raises:
            RuntimeError: If Mineru extraction fails
            requests.RequestException: If API call fails
        """
        logger.info(f"Parsing PDF from URL: {pdf_url}")

        task_id = self._create_task(pdf_url)
        result = self._poll_task(task_id)
        markdown_content = self._download_and_extract_markdown(
            result["full_zip_url"], task_id
        )

        return markdown_content

    def parse_batch(self, pdf_urls: List[str]) -> List[str]:
        """
        Parse multiple PDFs in sequence.

        Args:
            pdf_urls: List of PDF URLs

        Returns:
            List of markdown-formatted strings with extracted PDF content

        Note: Parses sequentially to avoid rate limiting.
        """
        markdown_contents = []

        for i, pdf_url in enumerate(pdf_urls, 1):
            try:
                logger.info(f"Parsing {i}/{len(pdf_urls)}: {pdf_url}")
                markdown_content = self.parse_from_url(pdf_url)
                markdown_contents.append(markdown_content)
            except Exception as e:
                logger.error(f"Failed to parse {pdf_url}: {e}")
                # Continue with next PDF instead of failing entire batch
                continue

        logger.info(f"✅ Parsed batch: {len(markdown_contents)}/{len(pdf_urls)} PDFs")
        return markdown_contents

    def _create_task(self, pdf_url: str) -> str:
        """
        Create extraction task in Mineru API from URL.

        Args:
            pdf_url: URL to PDF file

        Returns:
            Task ID for polling

        Raises:
            requests.RequestException: If API call fails
        """
        payload = {
            "url": pdf_url,
            "language": self.language,
        }

        if self.enable_formula:
            payload["enable_formula"] = True
        if self.enable_table:
            payload["enable_table"] = True

        try:
            response = requests.post(
                self.base_url,
                headers=self.headers,
                json=payload,
                timeout=30,
            )
            response.raise_for_status()

            data = response.json()
            task_id = data["data"]["task_id"]
            logger.info(f"✅ Task created: {task_id}")
            return task_id

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to create Mineru task: {e}")
            raise

    def _poll_task(self, task_id: str) -> dict:
        """
        Poll task status until completion.

        Args:
            task_id: Task ID to poll

        Returns:
            Task result data with 'full_zip_url' key

        Raises:
            RuntimeError: If task fails or times out
            requests.RequestException: If API call fails
        """
        url = f"{self.base_url}/{task_id}"
        start_time = time.time()

        while True:
            elapsed = time.time() - start_time
            if elapsed > self.poll_timeout:
                logger.error(f"Task {task_id} timed out after {self.poll_timeout}s")
                raise RuntimeError(
                    f"Task timeout: {task_id} did not complete within {self.poll_timeout} seconds"
                )

            try:
                response = requests.get(url, headers=self.headers, timeout=30)
                response.raise_for_status()

                data = response.json()["data"]
                state = data.get("state")

                if state == "done":
                    logger.info(f"✅ Task {task_id} completed")
                    return data
                elif state == "failed":
                    error_msg = data.get("err_msg", "Unknown error")
                    logger.error(f"❌ Task {task_id} failed: {error_msg}")
                    raise RuntimeError(f"Task failed: {error_msg}")
                else:
                    time.sleep(self.poll_interval)

            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to poll task {task_id}: {e}")
                raise

    def _download_and_extract_markdown(self, zip_url: str, task_id: str) -> str:
        """
        Download results ZIP, extract to disk, and return markdown content.

        Files are saved to: parsers/results/{task_id}/

        Args:
            zip_url: URL to results ZIP file
            task_id: Task ID for folder naming

        Returns:
            Extracted markdown content

        Raises:
            requests.RequestException: If download fails
            FileNotFoundError: If markdown file not found in ZIP
        """
        try:
            results_dir = Path(__file__).parent / "results" / task_id
            results_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"📁 Saving results to: {results_dir}")

            response = requests.get(zip_url, timeout=60)
            response.raise_for_status()

            zip_buffer = io.BytesIO(response.content)
            with zipfile.ZipFile(zip_buffer, "r") as z:
                z.extractall(results_dir)
                markdown_files = [f for f in z.namelist() if f.endswith(".md")]

                if not markdown_files:
                    logger.warning("No markdown files found in ZIP")
                    return ""

                markdown_file = markdown_files[0]
                markdown_path = results_dir / markdown_file

                with open(markdown_path, "r", encoding="utf-8") as f:
                    markdown_content = f.read()

            return markdown_content

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to download results: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to extract markdown: {e}")
            raise


if __name__ == "__main__":
    parser = MineruPDFParser()
    markdown = parser.parse_from_url(
        "https://cafef1.mediacdn.vn/Images/Uploaded/DuLieuDownload/PhanTichBaoCao/MBB_2025_12_04_SSIResearch08122025094945.pdf"
    )
    print(markdown)
