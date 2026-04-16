"""Pipeline processor for crawler data processing."""

import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime


class CrawlerPipeline:
    """Pipeline for processing crawled data before storage."""

    def __init__(self, output_dir: Path = Path("data")):
        """
        Initialize the pipeline.

        Args:
            output_dir: Output directory for processed data
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)

    def validate_article(self, article: Dict) -> bool:
        """
        Validate article data.

        Args:
            article: Article dictionary to validate

        Returns:
            True if article is valid, False otherwise
        """
        required_fields = ["url", "title"]
        return all(field in article and article[field] for field in required_fields)

    def enrich_article(self, article: Dict) -> Dict:
        """
        Enrich article with additional metadata.

        Args:
            article: Article dictionary

        Returns:
            Enriched article dictionary
        """
        enriched = article.copy()
        enriched["crawled_at"] = datetime.now().isoformat()
        enriched["content_length"] = len(article.get("content", ""))
        enriched["tags_count"] = len(article.get("tags", []))

        # Extract domain from URL
        from urllib.parse import urlparse

        parsed_url = urlparse(article.get("url", ""))
        enriched["domain"] = parsed_url.netloc

        return enriched

    def normalize_text(self, text: Optional[str]) -> Optional[str]:
        """
        Normalize text content.

        Args:
            text: Text to normalize

        Returns:
            Normalized text
        """
        if not text:
            return text

        # Remove extra whitespace
        text = " ".join(text.split())
        return text

    def process_article(self, article: Dict) -> Optional[Dict]:
        """
        Process a single article.

        Args:
            article: Raw article dictionary

        Returns:
            Processed article or None if invalid
        """
        # Validate
        if not self.validate_article(article):
            print(f"✗ Invalid article: missing required fields")
            return None

        # Normalize text fields
        article["title"] = self.normalize_text(article.get("title"))
        article["content"] = self.normalize_text(article.get("content"))
        article["sapo"] = self.normalize_text(article.get("sapo"))

        # Enrich
        article = self.enrich_article(article)

        return article

    def process_articles(self, articles: List[Dict]) -> tuple[int, int]:
        """
        Process multiple articles.

        Args:
            articles: List of raw article dictionaries

        Returns:
            Tuple of (processed_count, failed_count)
        """
        processed = 0
        failed = 0

        for idx, article in enumerate(articles, 1):
            try:
                processed_article = self.process_article(article)

                if processed_article:
                    # Save processed article
                    url_path = article.get("url", "").rstrip("/").split("/")[-1]
                    filename = f"{url_path}_processed.json"
                    output_path = self.output_dir / filename

                    with open(output_path, "w", encoding="utf-8") as f:
                        json.dump(processed_article, f, ensure_ascii=False, indent=2)

                    print(f"✓ [{idx}] Processed: {processed_article['title']}")
                    processed += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"✗ [{idx}] Error processing article: {e}")
                failed += 1

        return processed, failed

    def process_json_files(self, json_dir: Path) -> tuple[int, int]:
        """
        Process all JSON files in a directory.

        Args:
            json_dir: Directory containing JSON files

        Returns:
            Tuple of (processed_count, failed_count)
        """
        json_dir = Path(json_dir)
        json_files = list(json_dir.glob("*.json"))

        print(f"Found {len(json_files)} JSON files to process")

        processed = 0
        failed = 0

        for json_file in json_files:
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    article = json.load(f)

                processed_article = self.process_article(article)

                if processed_article:
                    output_path = self.output_dir / json_file.name
                    with open(output_path, "w", encoding="utf-8") as f:
                        json.dump(processed_article, f, ensure_ascii=False, indent=2)

                    print(f"✓ Processed: {json_file.name}")
                    processed += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"✗ Error processing {json_file.name}: {e}")
                failed += 1

        return processed, failed

    def get_statistics(self, json_dir: Path) -> Dict:
        """
        Get statistics from JSON files in directory.

        Args:
            json_dir: Directory containing JSON files

        Returns:
            Statistics dictionary
        """
        from deepfishy.shared.logging import logger

        json_dir = Path(json_dir)
        json_files = list(json_dir.glob("*.json"))

        total_articles = 0
        total_content_length = 0
        categories = set()
        dates = []  # Collect all dates for proper min/max

        for json_file in json_files:
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    article = json.load(f)

                total_articles += 1
                total_content_length += len(article.get("content", ""))

                if article.get("category"):
                    categories.add(article["category"])

                if article.get("date"):
                    dates.append(article["date"])  # Collect dates
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.error(f"Invalid JSON file {json_file.name}: {e}")
            except Exception as e:
                logger.error(f"Error reading {json_file.name}: {e}")

        # Properly compute date range (was: just overwriting min every time)
        date_range = {"min": None, "max": None}
        if dates:
            sorted_dates = sorted(dates)
            date_range = {"min": sorted_dates[0], "max": sorted_dates[-1]}

        return {
            "total_articles": total_articles,
            "total_content_length": total_content_length,
            "avg_content_length": (
                total_content_length // total_articles if total_articles > 0 else 0
            ),
            "unique_categories": len(categories),
            "categories": sorted(list(categories)),  # Sorted for consistency
            "date_range": date_range,
        }
