"""PDF parser using Mineru API for LLM-ready content extraction."""

import io
import os
import time
import zipfile
import requests
import base64
import json
import re
from typing import List, Optional, Tuple
from pathlib import Path
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.logging import logger

load_dotenv()


class MineruPDFParser:
    """Parser for converting PDFs to markdown using Mineru API with LLM post-processing."""

    def __init__(
        self,
        mineru_api_key: Optional[str] = None,
        language: str = "vi",
        enable_formula: bool = True,
        enable_table: bool = True,
        base_url: str = "https://mineru.net/api/v4/extract/task",
        poll_interval: int = 5,
        poll_timeout: int = 300,
        llm_model: str = "gemini-2.0-flash",
        chunk_size: int = 2048,
        chunk_overlap: int = 0,
    ):
        """
        Initialize PDF parser.

        Args:
            mineru_api_key: Mineru API key (defaults to env var MINERU_API_KEY)
            language: Document language (default: "vi" for Vietnamese)
            enable_formula: Whether to extract mathematical formulas
            enable_table: Whether to extract and structure tables
            base_url: Mineru API base URL
            poll_interval: Seconds between status polls
            poll_timeout: Max seconds to wait for task completion
            llm_model: LLM model to use for post-processing (default: gemini-2.0-flash)
            chunk_size: Size of text chunks for LLM processing
            chunk_overlap: Overlap between chunks for LLM processing
        """
        self.mineru_api_key = mineru_api_key or os.getenv("MINERU_API_KEY")
        if not self.mineru_api_key:
            raise ValueError("MINERU_API_KEY not found in environment or parameters")

        self.language = language
        self.enable_formula = enable_formula
        self.enable_table = enable_table
        self.base_url = base_url
        self.poll_interval = poll_interval
        self.poll_timeout = poll_timeout
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.mineru_api_key}",
        }

        # Initialize LLM if post-processing is enabled
        self.llm = ChatGoogleGenerativeAI(
            model=llm_model,
            temperature=0.0,
            max_tokens=None,
            timeout=None,
            max_retries=2,
        )

    def parse_pdf(self, pdf_url: str) -> str:
        """
        Parse a PDF with LLM post-processing.

        Extracts PDF to markdown via Mineru API, converts tables using LLM vision,
        and cleans up text formatting.

        Args:
            pdf_url: URL to PDF file

        Returns:
            Enhanced markdown content

        Raises:
            RuntimeError: If processing fails
        """
        logger.info(f"Parsing PDF with LLM post-processing: {pdf_url}")

        task_id = self._create_task(pdf_url)
        result = self._poll_task(task_id)
        markdown_content = self._download_and_extract_markdown(
            result["full_zip_url"], task_id
        )

        table_map = self._load_content_list(task_id)

        chunks = self._split_text_preserving_tables(
            markdown_content, self.chunk_size, self.chunk_overlap
        )
        logger.info(f"Generated {len(chunks)} chunks")

        final_markdown = self._process_chunks_with_llm(chunks, table_map, task_id)

        logger.info("✅ Processing completed")
        return final_markdown

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
            logger.info(f"📁 Saving result to: {results_dir}")

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

    def _load_content_list(self, task_id: str) -> dict:
        """
        Load the content_list.json file for a given task_id.

        Args:
            task_id: The task ID (UUID)

        Returns:
            Dictionary mapping HTML table bodies to their image paths and metadata
        """
        results_dir = Path(__file__).parent / "results"
        task_path = results_dir / task_id
        content_list_files = list(task_path.glob("*_content_list.json"))

        if not content_list_files:
            logger.warning(f"No content_list.json found for task {task_id}")
            return {}

        content_list_path = content_list_files[0]

        with open(content_list_path, "r", encoding="utf-8") as f:
            content_list = json.load(f)

        # Build a mapping of HTML table bodies to their image paths
        table_map = {}
        for item in content_list:
            if (
                item.get("type") == "table"
                and "table_body" in item
                and "img_path" in item
            ):
                # Normalize the HTML (remove extra whitespace for matching)
                html_body = item["table_body"].strip()
                img_path = item["img_path"]

                # Store the full path to the image
                full_img_path = task_path / img_path

                table_map[html_body] = {
                    "img_path": str(full_img_path),
                }

        logger.info(f"Loaded {len(table_map)} tables from content_list.json")
        return table_map

    def _split_text_preserving_tables(
        self, content: str, chunk_size: int = 2048, chunk_overlap: int = 0
    ) -> List[Tuple[str, str]]:
        """
        Split text while keeping each <table>...</table> as a complete, separate element.

        Returns:
            List of tuples: (chunk_type, chunk_content) where chunk_type is "text" or "table"
        """
        table_pattern = r"<table>.*?</table>"
        tables = []
        table_positions = []

        for match in re.finditer(table_pattern, content, re.DOTALL):
            tables.append(match.group())
            table_positions.append((match.start(), match.end()))

        chunks = []
        last_end = 0
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, chunk_overlap=chunk_overlap
        )

        for idx, (start, end) in enumerate(table_positions):
            text_before = content[last_end:start].strip()

            if text_before:
                split_texts = text_splitter.split_text(text_before)
                for text_chunk in split_texts:
                    if text_chunk.strip():
                        chunks.append(("text", text_chunk.strip()))

            chunks.append(("table", tables[idx]))
            last_end = end

        text_after = content[last_end:].strip()
        if text_after:
            split_texts = text_splitter.split_text(text_after)
            for text_chunk in split_texts:
                if text_chunk.strip():
                    chunks.append(("text", text_chunk.strip()))

        return chunks

    def _process_chunks_with_llm(
        self, chunks: List[Tuple[str, str]], table_map: dict, task_id: str
    ) -> str:
        """
        Process text chunks with LLM for Vietnamese text cleanup and convert HTML tables to markdown.

        Args:
            chunks: List of (chunk_type, chunk_content) tuples
            table_map: Dictionary mapping HTML tables to their image paths
            task_id: Task ID for saving output

        Returns:
            Final processed markdown content
        """
        text_system_message = SystemMessage(
            content=(
                "You are a helpful assistant specialized in cleaning and formatting Markdown content. "
                "Your tasks are:\n"
                "1. Correct all Vietnamese spelling, diacritic, and grammar errors while preserving the original meaning.\n"
                "2. Ensure proper markdown formatting for headers, lists, and other elements.\n"
                "3. Convert any remaining HTML elements into their proper Markdown equivalents.\n"
                "4. Keep the content concise and readable, without altering factual information.\n\n"
                "Output rules:\n"
                "- Return ONLY the final cleaned Markdown content.\n"
                "- Do NOT include explanations, comments, code fences, or extra text.\n"
                "- Do NOT mention that corrections or conversions were made."
            )
        )

        final_content = []

        for index, (chunk_type, chunk_content) in enumerate(chunks):
            logger.info(f"[{index + 1}/{len(chunks)}] Processing {chunk_type} chunk")

            if chunk_type == "table":
                markdown_table = self._replace_html_table_with_markdown(
                    chunk_content, table_map
                )
                final_content.append(markdown_table)
            else:
                messages = [
                    text_system_message,
                    HumanMessage(
                        content=f"Convert the following content into Markdown format:\n\n{chunk_content}"
                    ),
                ]
                response = self.llm.invoke(messages)
                cleaned_content = self._clean_markdown_response(response.content)
                final_content.append(cleaned_content)

        results_dir = Path(__file__).parent / "results" / task_id
        output_file = results_dir / "full_fixed.md"
        logger.info(f"Saved output to {output_file}")

        final_markdown = "\n\n".join(final_content)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(final_markdown)

        return final_markdown

    def _image_to_base64(self, image_path: str) -> str:
        """
        Convert an image file to base64 string.

        Args:
            image_path: Path to the image file

        Returns:
            Base64 encoded string of the image
        """
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    def _convert_table_image_to_markdown(self, image_path: str) -> str:
        """
        Convert a table image to markdown using LLM with vision capabilities.

        Args:
            image_path: Path to the table image

        Returns:
            Markdown formatted table
        """
        if not os.path.exists(image_path):
            logger.warning(f"Image not found at {image_path}")
            return "[Table image not found]"

        system_prompt = (
            "You are a helpful assistant specialized in converting table images into clean, well-structured Markdown tables. "
            "Your tasks are:\n"
            "1. Analyze the table image carefully and extract all data accurately.\n"
            "2. Convert the table into proper Markdown table format.\n"
            "3. Preserve all headers, rows, and cell content exactly as shown.\n"
            "4. Correct any Vietnamese spelling, diacritic, and grammar errors.\n"
            "5. Maintain proper alignment and formatting.\n\n"
            "Output rules:\n"
            "- Return ONLY the Markdown table.\n"
            "- Do NOT include explanations, comments, code fences, or extra text.\n"
            "- Ensure the table is valid Markdown format."
        )

        user_prompt = "Convert this table image into a Markdown table format:"

        # Get base64 encoded image
        image_base64 = self._image_to_base64(image_path)

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(
                content=[
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"},
                    },
                ]
            ),
        ]

        try:
            logger.info(f"  Converting table image: {os.path.basename(image_path)}")
            response = self.llm.invoke(messages)
            markdown_table = self._clean_markdown_response(response.content)

            return markdown_table
        except Exception as e:
            logger.error(f"Error converting table image {image_path}: {e}")
            return f"[Error converting table: {e}]"

    def _replace_html_table_with_markdown(
        self, html_table: str, table_map: dict
    ) -> str:
        """
        Convert a single HTML table to markdown using its image.

        Args:
            html_table: HTML table string (e.g., "<table>...</table>")
            table_map: Dictionary mapping HTML tables to their image paths

        Returns:
            Markdown formatted table or original HTML if not found
        """
        html_table = html_table.strip()

        if html_table in table_map:
            table_info = table_map[html_table]
            markdown_table = self._convert_table_image_to_markdown(
                table_info["img_path"],
            )
            return markdown_table
        else:
            logger.warning("  No matching image found for HTML table")
            return html_table

    def _clean_markdown_response(self, content: str) -> str:
        """Remove markdown code fences from LLM response if present."""
        content = content.strip()

        if content.startswith("```"):
            first_newline = content.find("\n")
            if first_newline != -1:
                content = content[first_newline + 1 :]

        if content.endswith("```"):
            content = content[:-3].rstrip()

        return content


if __name__ == "__main__":
    import argparse

    parser_args = argparse.ArgumentParser(
        description="Parse PDF using Mineru API with optional LLM post-processing"
    )
    parser_args.add_argument(
        "--url",
        type=str,
        default="https://cafef1.mediacdn.vn/Images/Uploaded/DuLieuDownload/PhanTichBaoCao/MBB_2025_12_04_SSIResearch08122025094945.pdf",
        help="URL of PDF to parse",
    )
    parser_args.add_argument(
        "--model",
        type=str,
        default="gemini-2.0-flash",
        help="LLM model to use for post-processing",
    )

    args = parser_args.parse_args()

    # Initialize parser
    parser = MineruPDFParser(
        llm_model=args.model,
    )

    markdown = parser.parse_pdf(args.url)

    print("=" * 80)
    print("RESULT:")
    print("=" * 80)
    print(markdown)
