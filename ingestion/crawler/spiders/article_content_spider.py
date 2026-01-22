"""Spider for crawling article content from URLs."""

import re
import json
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
from .base import BaseSpider


class ArticleContentSpider(BaseSpider):
    """Spider for extracting and saving article content from vneconomy.vn."""

    def extract_article_data(self, html_content: str, url: str) -> Dict:
        """
        Extract article data from HTML content.

        Args:
            html_content: HTML content as string
            url: Source URL

        Returns:
            Dictionary with extracted article data
        """
        soup = BeautifulSoup(html_content, "html.parser")

        # Extract title from meta og:title or first h1/h2
        title = None
        title_meta = soup.find("meta", property="og:title")
        if title_meta:
            title = title_meta.get("content")
        if not title:
            title_element = soup.find(["h1", "h2", "h3"])
            if title_element:
                title = title_element.get_text(strip=True)

        # Extract category - look for breadcrumb next to "Trang chủ"
        category = None
        breadcrumb = soup.find("div", class_=re.compile("breadcrumb", re.I))
        if breadcrumb:
            # Find all links in breadcrumb
            links = breadcrumb.find_all("a", class_="text-breadcrumb")
            # Get the second link (after "Trang chủ")
            if len(links) > 1:
                category = links[1].get_text(strip=True)

        # Extract date from data-field="distributionDate"
        date = None
        date_element = soup.find(
            class_="date", attrs={"data-field": "distributionDate"}
        )
        if date_element:
            date = date_element.get_text(strip=True)

        # Extract content from data-field="body"
        content = ""
        body_element = soup.find(attrs={"data-field": "body"})
        if body_element:
            # Extract all paragraph text
            paragraphs = body_element.find_all("p", class_="text-justify")
            content = "\n\n".join([p.get_text(strip=True) for p in paragraphs])

        # Extract sapo (lead paragraph)
        sapo = ""
        sapo_element = soup.find(attrs={"data-field": "sapo"})
        if sapo_element:
            sapo = sapo_element.get_text(strip=True)

        # Extract tags
        tags = []
        tag_container = soup.find("div", class_="box-keyword")
        if tag_container:
            tag_elements = tag_container.find_all("a", class_="tag")
            tags = [tag.get_text(strip=True) for tag in tag_elements]

        return {
            "url": url,
            "title": title,
            "category": category,
            "date": date,
            "sapo": sapo,
            "content": content,
            "tags": tags,
        }

    @staticmethod
    def _sanitize_filename(title: Optional[str]) -> str:
        """
        Create a safe filename from title.

        Args:
            title: Article title

        Returns:
            Safe filename
        """
        if not title:
            return "untitled"
        # Remove invalid filename characters
        safe_title = re.sub(r'[<>:"/\\|?*]', "", title)
        # Limit length
        safe_title = safe_title[:100]
        return safe_title.strip()

    def _upload_to_minio(
        self, article_data: Dict, url_path: str, max_retries: int = 3
    ) -> bool:
        """
        Upload article to MinIO with exponential backoff retry logic.

        Args:
            article_data: Article dictionary to upload
            url_path: URL path for object naming
            max_retries: Maximum upload attempts (default 3)

        Returns:
            True if successful, False otherwise
        """
        from core.logging import logger
        from time import sleep

        try:
            from services.minio import MinioService
        except ImportError:
            logger.warning(
                f"MinIO service not available - skipping upload for {url_path}"
            )
            return False

        object_name = f"articles/{url_path}.json"

        for attempt in range(1, max_retries + 1):
            try:
                minio = MinioService()
                if minio.upload_json("crawler-data", object_name, article_data):
                    logger.info(f"Uploaded to MinIO: {object_name}")
                    return True
            except (ConnectionError, TimeoutError) as e:
                # Exponential backoff: 1s, 2s, 4s ✅ BETTER RETRY STRATEGY
                backoff_time = 2 ** (attempt - 1)
                if attempt < max_retries:
                    logger.warning(
                        f"Upload attempt {attempt}/{max_retries} failed: {e}. Retrying in {backoff_time}s..."
                    )
                    sleep(backoff_time)
                else:
                    logger.error(f"Upload failed after {max_retries} attempts: {e}")
            except Exception as e:
                logger.error(f"Upload error (non-retryable): {e}")
                return False

        return False

    def _process_url(self, url: str, idx: int, total: int) -> Optional[tuple]:
        """
        Process a single URL - fetch, extract, and upload to MinIO.

        Args:
            url: URL to process
            idx: Current index (for progress tracking)
            total: Total URLs

        Returns:
            Tuple of (filename, article_data) if successful, None otherwise
        """
        print(f"\n[{idx}/{total}] Processing: {url}")

        try:
            # Fetch HTML from URL
            html_content = self.fetch_html(url)
            if not html_content:
                return None

            # Extract data
            article_data = self.extract_article_data(html_content, url)

            # Create filename from URL path
            url_path = url.rstrip("/").split("/")[-1]
            # Remove .htm or .html extension if present
            url_path = re.sub(r"\.(htm|html)$", "", url_path)
            filename = url_path + ".json"

            print(f"✓ Processing: {filename}")
            print(f"  Title: {article_data['title']}")
            print(f"  Date: {article_data['date']}")

            # Upload to MinIO immediately (with retry logic)
            self._upload_to_minio(article_data, url_path, max_retries=3)

            return (filename, article_data)  # Return both filename and data

        except Exception as e:
            print(f"✗ Error processing {url}: {e}")
            return None

    async def crawl(
        self,
        urls: List[str],
        max_workers: int = 5,
    ) -> tuple:
        """
        Crawl articles from URLs and save to MinIO.

        Args:
            urls: List of article URLs to crawl
            max_workers: Maximum concurrent workers

        Returns:
            Tuple of (successful_count, failed_count, articles_data_list)
            - articles_data_list: List of extracted article dictionaries
        """
        print(f"Starting crawl of {len(urls)} URLs with {max_workers} workers...\n")

        successful = 0
        failed = 0
        articles_data = []  # Store article data to return

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_url = {
                executor.submit(self._process_url, url, idx, len(urls)): url
                for idx, url in enumerate(urls, 1)
            }

            # Process completed tasks
            for future in as_completed(future_to_url):
                try:
                    result = future.result()
                    if result:
                        filename, article_data = result
                        successful += 1
                        articles_data.append(article_data)  # Add to return data
                    else:
                        failed += 1
                except Exception as e:
                    print(f"Error in future result: {e}")
                    failed += 1

        stats = {
            "successful": successful,
            "failed": failed,
            "total": len(urls),
        }

        print(f"\n{'='*60}")
        print(f"Crawl completed!")
        print(f"Successful: {stats['successful']}")
        print(f"Failed: {stats['failed']}")
        print(f"Total: {stats['total']}")
        print(f"{'='*60}")

        return successful, failed, articles_data
