"""Mineru PDF extraction service for converting PDFs to markdown."""

import io
import os
import time
import requests
import zipfile
from urllib.parse import urlparse
from pathlib import Path
from typing import Optional, Dict, Any

from app.core.logging import logger
from app.core.config import settings


class MineruService:
    """
    Service for extracting text and structure from PDFs using Mineru API.

    Converts PDFs to markdown with structure preservation, suitable for RAG.
    Supports both remote URLs and local PDF files.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://mineru.net/api/v4/extract/task",
        poll_interval: int = 5,
        poll_timeout: int = 300,
    ):
        """
        Initialize Mineru service.

        Args:
            api_key: Mineru API key (defaults to MINERU_API_KEY env var)
            base_url: Base URL for Mineru API
            poll_interval: Seconds between status polls
            poll_timeout: Max seconds to wait for task completion
        """
        self.api_key = api_key or os.getenv("MINERU_API_KEY")
        if not self.api_key:
            raise ValueError("MINERU_API_KEY not found in environment or parameters")

        self.base_url = base_url
        self.poll_interval = poll_interval
        self.poll_timeout = poll_timeout

        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        logger.info("Initialized MineruService")

    def extract_from_url(
        self,
        pdf_url: str,
        language: str = "vi",
        enable_formula: bool = False,
        enable_table: bool = True,
    ) -> Dict[str, Any]:
        """
        Extract text from a PDF at a remote URL.

        Args:
            pdf_url: URL to PDF file
            language: Document language (default: "vi" for Vietnamese)
            enable_formula: Whether to extract mathematical formulas
            enable_table: Whether to extract and structure tables

        Returns:
            Dictionary with extracted content:
            {
                "markdown": str,
                "task_id": str,
                "full_zip_url": str,
                "state": str
            }

        Raises:
            RuntimeError: If task fails or times out
            requests.RequestException: If API call fails
        """
        logger.info(f"Starting PDF extraction from URL: {pdf_url}")

        # Create extraction task
        task_id = self._create_task(
            pdf_url=pdf_url,
            language=language,
            enable_formula=enable_formula,
            enable_table=enable_table,
        )

        # Poll for completion
        result = self._poll_task(task_id)

        # Download and extract results
        markdown_content = self._download_and_extract_markdown(
            result.get("full_zip_url")
        )

        return {
            "markdown": markdown_content,
            "task_id": task_id,
            "full_zip_url": result.get("full_zip_url"),
            "state": result.get("state"),
        }

    def extract_from_file(
        self,
        file_path: str,
        language: str = "vi",
        enable_formula: bool = False,
        enable_table: bool = True,
    ) -> Dict[str, Any]:
        """
        Extract text from a local PDF file.

        Currently uploads to a temporary location first.
        For production, consider direct file upload support.

        Args:
            file_path: Path to local PDF file
            language: Document language (default: "vi" for Vietnamese)
            enable_formula: Whether to extract mathematical formulas
            enable_table: Whether to extract and structure tables

        Returns:
            Dictionary with extracted content (same as extract_from_url)

        Raises:
            FileNotFoundError: If file doesn't exist
            NotImplementedError: Direct file upload not yet implemented
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        logger.info(f"Extracting from local file: {file_path}")

        # Note: Current Mineru API requires URL input
        # For production use, you may need to:
        # 1. Upload file to MinIO/cloud storage first
        # 2. Get a signed URL
        # 3. Pass URL to Mineru
        # Or implement direct file upload if Mineru supports it

        raise NotImplementedError(
            "Direct file upload not yet implemented. "
            "Please upload to MinIO first and use extract_from_url."
        )

    def _create_task(
        self,
        pdf_url: str,
        language: str = "vi",
        enable_formula: bool = False,
        enable_table: bool = True,
    ) -> str:
        """
        Create extraction task in Mineru.

        Args:
            pdf_url: URL to PDF file
            language: Document language
            enable_formula: Whether to extract formulas
            enable_table: Whether to extract tables

        Returns:
            Task ID for polling

        Raises:
            requests.RequestException: If API call fails
        """
        payload = {
            "url": pdf_url,
            "language": language,
        }

        if enable_formula:
            payload["enable_formula"] = True
        if enable_table:
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

    def _poll_task(self, task_id: str) -> Dict[str, Any]:
        """
        Poll task status until completion.

        Args:
            task_id: Task ID to poll

        Returns:
            Task result data

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
                    f"Mineru task timeout: {task_id} did not complete within {self.poll_timeout} seconds"
                )

            try:
                response = requests.get(url, headers=self.headers, timeout=30)
                response.raise_for_status()

                data = response.json()["data"]
                state = data.get("state")

                logger.info(f"⏳ Task {task_id} state: {state}")

                if state == "done":
                    logger.info(f"✅ Task {task_id} completed")
                    return data
                elif state == "failed":
                    error_msg = data.get("err_msg", "Unknown error")
                    logger.error(f"❌ Task {task_id} failed: {error_msg}")
                    raise RuntimeError(f"Mineru task failed: {error_msg}")
                else:
                    time.sleep(self.poll_interval)

            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to poll task {task_id}: {e}")
                raise

    def _download_and_extract_markdown(self, zip_url: str) -> str:
        """
        Download results ZIP and extract markdown content.

        Processes ZIP in memory to avoid filesystem issues like race conditions
        or read-only filesystem problems in concurrent environments.

        Args:
            zip_url: URL to results ZIP file

        Returns:
            Extracted markdown content

        Raises:
            requests.RequestException: If download fails
            FileNotFoundError: If markdown file not found in ZIP
        """
        try:
            logger.info("⬇️ Downloading results ZIP")
            response = requests.get(zip_url, timeout=60)
            response.raise_for_status()

            # Process ZIP in memory using BytesIO
            logger.info("📦 Extracting markdown from results")
            zip_buffer = io.BytesIO(response.content)
            markdown_content = None

            with zipfile.ZipFile(zip_buffer, "r") as z:
                # Look for markdown file
                markdown_files = [f for f in z.namelist() if f.endswith(".md")]

                if not markdown_files:
                    logger.warning("No markdown files found in ZIP")
                    return ""

                # Use first markdown file found
                markdown_file = markdown_files[0]
                logger.info(f"Found markdown file: {markdown_file}")

                with z.open(markdown_file) as f:
                    markdown_content = f.read().decode("utf-8")

            logger.info(f"✅ Extracted {len(markdown_content)} characters")
            return markdown_content

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to download results: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to extract markdown: {e}")
            raise
