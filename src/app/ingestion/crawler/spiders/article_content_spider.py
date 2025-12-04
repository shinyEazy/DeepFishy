"""Spider for crawling article content from URLs."""

import re
import json
from pathlib import Path
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

    def _process_url(
        self, url: str, output_dir: Path, idx: int, total: int
    ) -> Optional[str]:
        """
        Process a single URL - fetch, extract, and save data.

        Args:
            url: URL to process
            output_dir: Output directory for saving JSON files
            idx: Current index (for progress tracking)
            total: Total URLs

        Returns:
            Filename if successful, None otherwise
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
            output_path = output_dir / filename

            # Save to JSON
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(article_data, f, ensure_ascii=False, indent=2)

            print(f"✓ Saved: {output_path.name}")
            print(f"  Title: {article_data['title']}")
            print(f"  Date: {article_data['date']}")

            return output_path.name

        except Exception as e:
            print(f"✗ Error processing {url}: {e}")
            return None

    async def crawl(
        self,
        urls: List[str],
        output_dir: Path = Path("data"),
        max_workers: int = 5,
    ) -> Dict[str, int]:
        """
        Crawl articles from URLs and save as JSON files.

        Args:
            urls: List of article URLs to crawl
            output_dir: Directory to save JSON files
            max_workers: Maximum concurrent workers

        Returns:
            Dictionary with crawl statistics
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True, parents=True)

        print(f"Starting crawl of {len(urls)} URLs with {max_workers} workers...\n")

        successful = 0
        failed = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_url = {
                executor.submit(self._process_url, url, output_dir, idx, len(urls)): url
                for idx, url in enumerate(urls, 1)
            }

            # Process completed tasks
            for future in as_completed(future_to_url):
                try:
                    result = future.result()
                    if result:
                        successful += 1
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

        return stats
