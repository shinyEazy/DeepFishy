"""Spider for crawling article URLs from category pages."""

from typing import List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import sleep
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from .base import BaseSpider


class ArticleURLSpider(BaseSpider):
    """Spider for extracting article URLs from vneconomy.vn category pages."""

    def __init__(self, base_url: str = "https://vneconomy.vn", max_retries: int = 5):
        """
        Initialize the Article URL spider.

        Args:
            base_url: Base URL for constructing absolute URLs
            max_retries: Maximum retry attempts
        """
        super().__init__(base_url, max_retries)
        self.url_template = "{base_url}/{path}.htm?page={page}"

    def extract_article_urls(self, html_content: str) -> List[str]:
        """
        Extract all article URLs from HTML content.

        Args:
            html_content: HTML content as string

        Returns:
            List of article URLs
        """
        soup = BeautifulSoup(html_content, "html.parser")

        # Find the main-page section
        main_page = soup.find("main", class_="main-page")
        if not main_page:
            print("Warning: main-page section not found")
            return []

        # Find all article items
        article_items = main_page.find_all(
            "div", class_="featured-row_item featured-column_item"
        )

        urls = []
        for item in article_items:
            # Find the href in the link-layer-imt anchor tag
            link = item.find("a", class_="link-layer-imt")
            if link and link.get("href"):
                href = link.get("href")
                # Construct absolute URL
                absolute_url = urljoin(self.base_url, href)
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

        for attempt in range(1, self.max_retries + 1):
            try:
                html_content = self.fetch_html(url)
                if html_content:
                    urls = self.extract_article_urls(html_content)
                    print(f"✓ Path: {path}, Page {page}: Found {len(urls)} articles")
                    return (path, page, urls)
            except Exception as e:
                if attempt < self.max_retries:
                    print(
                        f"⚠ Attempt {attempt}/{self.max_retries} failed for {url}: {e}"
                    )
                    sleep(2)
                else:
                    print(f"✗ Failed after {self.max_retries} attempts - {url}: {e}")

        return (path, page, [])

    async def crawl(
        self, paths: List[str], max_pages: int = 2000, max_workers: int = 5
    ) -> List[str]:
        """
        Crawl article URLs from multiple category paths.

        Args:
            paths: List of category paths to crawl
            max_pages: Maximum pages per path to crawl
            max_workers: Maximum concurrent workers

        Returns:
            List of unique article URLs
        """
        all_urls = []
        unique_urls = []

        for path in paths:
            print(f"\n{'='*60}")
            print(f"Processing path: {path}")
            print(f"{'='*60}")

            page = 1
            while page < max_pages:
                # Create batch of tasks (process 10 pages at a time concurrently)
                batch_tasks = [
                    (path, p) for p in range(page, min(page + 10, max_pages))
                ]

                # Process batch concurrently
                batch_results = []
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    future_to_task = {
                        executor.submit(self._fetch_page_urls, path, p): (path, p)
                        for path, p in batch_tasks
                    }

                    for future in as_completed(future_to_task):
                        path_result, page_result, urls = future.result()
                        batch_results.append((page_result, urls))
                        all_urls.extend(urls)

                # Sort batch results by page number for sequential checking
                batch_results.sort(key=lambda x: x[0])

                should_skip = False
                for page_num, urls in batch_results:
                    if len(urls) == 0:
                        print(
                            f"⏭ Page {page_num} returned 0 articles. Moving to next path."
                        )
                        should_skip = True
                        break

                    # Track unique URL count before adding this page's URLs
                    unique_count_before = len(unique_urls)

                    # Add only new unique URLs
                    for url in urls:
                        if url not in unique_urls:
                            unique_urls.append(url)

                    # Check if any new URLs were added
                    unique_count_after = len(unique_urls)

                    if unique_count_after == unique_count_before:
                        print(
                            f"⏭ Page {page_num} contains only duplicate URLs. Skipping category from here."
                        )
                        should_skip = True
                        break

                if should_skip:
                    break

                # Move to next batch
                page += 10

        print(f"\n--- Crawl Complete ---")
        print(f"Total URLs collected: {len(all_urls)}")
        print(f"Unique URLs: {len(unique_urls)}")

        return unique_urls
