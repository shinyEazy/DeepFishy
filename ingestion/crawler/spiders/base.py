"""Base spider class for web crawling operations."""

import requests
from abc import ABC, abstractmethod
from typing import List, Optional
from time import sleep
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class BaseSpider(ABC):
    """Abstract base class for all crawler spiders."""

    def __init__(self, base_url: str = "", max_retries: int = 5):
        """
        Initialize spider.

        Args:
            base_url: Base URL for the spider
            max_retries: Maximum retry attempts for HTTP requests
        """
        self.base_url = base_url
        self.max_retries = max_retries
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create a requests session with retry strategy."""
        session = requests.Session()
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def fetch_html(
        self, url: str, timeout: int = 30, encoding: Optional[str] = None
    ) -> Optional[str]:
        """
        Fetch HTML content from URL with retry.

        Args:
            url: URL to fetch
            timeout: Request timeout in seconds
            encoding: Optional encoding to use (auto-detect if None)

        Returns:
            HTML content or None if failed
        """
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        try:
            response = self.session.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            if encoding:
                response.encoding = encoding
            else:
                response.encoding = response.apparent_encoding
            return response.text
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None

    @abstractmethod
    async def crawl(self, *args, **kwargs):
        """Main crawl method to be implemented by subclasses."""
        pass

    def close(self):
        """Close the session."""
        self.session.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
