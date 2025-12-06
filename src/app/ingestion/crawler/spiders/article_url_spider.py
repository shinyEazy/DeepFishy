"""Spider for crawling article URLs from category pages."""

from typing import List, Tuple, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.core.logging import logger
from .base import BaseSpider


class ArticleURLSpider(BaseSpider):
    """Spider for extracting article URLs from vneconomy.vn category pages."""

    def __init__(
        self,
        base_url: str = "https://vneconomy.vn",
        max_retries: int = 5,
        batch_size: int = 10,
    ):
        """
        Initialize the Article URL spider.

        Args:
            base_url: Base URL for constructing absolute URLs
            max_retries: Maximum retry attempts
            batch_size: Number of pages to process concurrently
        """
        super().__init__(base_url, max_retries)
        self.url_template = "{base_url}/{path}.htm?page={page}"
        self.batch_size = batch_size

    def extract_article_urls(self, html_content: str) -> List[str]:
        """
        Extract all article URLs from HTML content.

        Args:
            html_content: HTML content as string

        Returns:
            List of article URLs
        """
        soup = BeautifulSoup(html_content, "html.parser")
        main_page = soup.find("main", class_="main-page")

        if not main_page:
            logger.warning("main-page section not found in HTML")
            return []

        article_items = main_page.find_all(
            "div", class_="featured-row_item featured-column_item"
        )

        urls = []
        for item in article_items:
            link = item.find("a", class_="link-layer-imt")
            if link and link.get("href"):
                absolute_url = urljoin(self.base_url, link.get("href"))
                urls.append(absolute_url)

        return urls

    def _fetch_page_urls(self, path: str, page: int) -> Tuple[str, int, List[str]]:
        """
        Fetch URLs from a single page.

        Args:
            path: Category path
            page: Page number

        Returns:
            Tuple of (path, page, list of URLs)
        """
        url = self.url_template.format(base_url=self.base_url, path=path, page=page)

        html_content = self.fetch_html(url)
        if html_content:
            urls = self.extract_article_urls(html_content)
            logger.info(f"Path: {path}, Page {page}: Found {len(urls)} articles")
            return (path, page, urls)
        else:
            logger.warning(f"Failed to fetch HTML from {url}")
            return (path, page, [])

    async def crawl(
        self,
        paths: List[str],
        max_pages: int = 2000,
        max_workers: int = 5,
        known_urls: Set[str] = None,
    ) -> Tuple[List[str], List[str]]:
        """
        Crawl article URLs from multiple category paths with checkpoint support.

        Args:
            paths: List of category paths to crawl
            max_pages: Maximum pages per path to crawl
            max_workers: Maximum concurrent workers
            known_urls: Set of already-crawled URLs. Stops when encountering these

        Returns:
            Tuple of (all_discovered_urls, new_urls_only)
            - all_discovered_urls: All unique URLs found in this session
            - new_urls_only: Only URLs not in known_urls checkpoint
        """
        if not paths:
            logger.warning("Empty paths list provided")
            return [], []

        if max_pages < 1:
            logger.warning(f"Invalid max_pages={max_pages}, using default 2000")
            max_pages = 2000

        known_urls = known_urls or set()
        all_discovered = known_urls.copy()
        new_urls = []

        for path in paths:
            logger.info(f"Processing category: {path}")
            page = 1

            while page <= max_pages:
                batch_end = min(page + self.batch_size, max_pages)
                batch_tasks = [(path, p) for p in range(page, batch_end)]

                batch_results = []
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    future_to_task = {
                        executor.submit(self._fetch_page_urls, p, pg): (p, pg)
                        for p, pg in batch_tasks
                    }

                    for future in as_completed(future_to_task):
                        _, page_num, urls = future.result()
                        batch_results.append((page_num, urls))

                batch_results.sort(key=lambda x: x[0])

                should_stop_path = False
                for page_num, urls in batch_results:
                    if not urls:
                        logger.info(f"Page {page_num} empty, stopping path {path}")
                        should_stop_path = True
                        break

                    known_count = sum(1 for url in urls if url in known_urls)
                    if known_count > 0:
                        logger.info(
                            f"Page {page_num} has {known_count} known URLs, stopping path {path}"
                        )
                        should_stop_path = True
                        break

                    new_count = 0
                    for url in urls:
                        if url not in all_discovered:
                            all_discovered.add(url)
                            new_urls.append(url)
                            new_count += 1

                    if new_count == 0:
                        logger.info(
                            f"Page {page_num} has only duplicates, stopping path {path}"
                        )
                        should_stop_path = True
                        break

                if should_stop_path:
                    break

                page = batch_end

        logger.info(
            f"Crawl complete: {len(new_urls)} new URLs, {len(all_discovered)} total unique"
        )
        return list(all_discovered), new_urls
