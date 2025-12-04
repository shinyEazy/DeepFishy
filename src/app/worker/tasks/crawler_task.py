"""Celery tasks for crawler operations."""

import asyncio
from pathlib import Path
from typing import List

from app.celery_app import celery_app
from app.ingestion.crawler.spiders import ArticleURLSpider, ArticleContentSpider
from app.ingestion.crawler.pipeline import CrawlerPipeline
from app.core.logging import logger


@celery_app.task(bind=True, name="crawler.crawl_article_urls")
def crawl_article_urls_task(
    self,
    paths: List[str],
    max_pages: int = 2000,
    max_workers: int = 5,
) -> dict:
    """
    Celery task to crawl article URLs from category pages.

    Args:
        paths: List of category paths to crawl
        max_pages: Maximum pages per path
        max_workers: Maximum concurrent workers

    Returns:
        Dictionary with crawl results
    """
    try:
        logger.info(f"Starting article URL crawl for {len(paths)} paths")

        spider = ArticleURLSpider(max_retries=5)
        urls = asyncio.run(spider.crawl(paths, max_pages, max_workers))
        spider.close()

        logger.info(f"Completed URL crawl: {len(urls)} unique URLs")

        return {
            "status": "success",
            "urls_collected": len(urls),
            "urls": urls,
        }
    except Exception as e:
        logger.error(f"Error in crawl_article_urls_task: {e}")
        return {
            "status": "error",
            "error": str(e),
        }


@celery_app.task(bind=True, name="crawler.crawl_article_content")
def crawl_article_content_task(
    self,
    urls: List[str],
    output_dir: str = "data/articles",
    max_workers: int = 5,
) -> dict:
    """
    Celery task to crawl article content from URLs.

    Args:
        urls: List of article URLs to crawl
        output_dir: Output directory for saving articles
        max_workers: Maximum concurrent workers

    Returns:
        Dictionary with crawl statistics
    """
    try:
        logger.info(f"Starting article content crawl for {len(urls)} URLs")

        spider = ArticleContentSpider()
        stats = asyncio.run(spider.crawl(urls, Path(output_dir), max_workers))
        spider.close()

        logger.info(
            f"Completed content crawl: {stats['successful']} successful, {stats['failed']} failed"
        )

        return {
            "status": "success",
            **stats,
        }
    except Exception as e:
        logger.error(f"Error in crawl_article_content_task: {e}")
        return {
            "status": "error",
            "error": str(e),
        }


@celery_app.task(bind=True, name="crawler.process_articles")
def process_articles_task(
    self,
    json_dir: str = "data/articles",
    output_dir: str = "data/processed_articles",
) -> dict:
    """
    Celery task to process crawled articles.

    Args:
        json_dir: Directory containing raw article JSON files
        output_dir: Output directory for processed articles

    Returns:
        Dictionary with processing results
    """
    try:
        logger.info(f"Starting article processing from {json_dir}")

        pipeline = CrawlerPipeline(output_dir=output_dir)
        processed, failed = pipeline.process_json_files(Path(json_dir))

        # Get statistics
        stats = pipeline.get_statistics(Path(output_dir))

        logger.info(f"Completed processing: {processed} processed, {failed} failed")

        return {
            "status": "success",
            "processed": processed,
            "failed": failed,
            "statistics": stats,
        }
    except Exception as e:
        logger.error(f"Error in process_articles_task: {e}")
        return {
            "status": "error",
            "error": str(e),
        }


@celery_app.task(
    bind=True,
    name="crawler.crawl_full_pipeline",
)
def crawl_full_pipeline_task(
    self,
    paths: List[str],
    max_pages: int = 2000,
    output_dir: str = "data/articles",
    max_workers: int = 5,
) -> dict:
    """
    Celery task to run the full crawling pipeline.
    1. Crawl article URLs
    2. Crawl article content
    3. Process articles

    Args:
        paths: List of category paths to crawl
        max_pages: Maximum pages per path
        output_dir: Output directory for articles
        max_workers: Maximum concurrent workers

    Returns:
        Dictionary with complete pipeline results
    """
    try:
        logger.info("Starting full crawl pipeline")

        # Step 1: Crawl URLs
        logger.info("Step 1: Crawling article URLs")
        url_result = crawl_article_urls_task(paths, max_pages, max_workers)

        if url_result["status"] != "success":
            return {"status": "error", "step": "url_crawl", "error": url_result}

        urls = url_result["urls"]
        logger.info(f"Collected {len(urls)} unique URLs")

        # Step 2: Crawl content
        logger.info("Step 2: Crawling article content")
        content_result = crawl_article_content_task(urls, output_dir, max_workers)

        if content_result["status"] != "error":
            logger.error(f"Failed at content crawl: {content_result}")
            return {"status": "error", "step": "content_crawl", "error": content_result}

        logger.info(f"Crawled {content_result['successful']} articles successfully")

        # Step 3: Process articles
        logger.info("Step 3: Processing articles")
        process_result = process_articles_task(output_dir, f"{output_dir}/processed")

        if process_result["status"] != "success":
            logger.error(f"Failed at processing: {process_result}")
            return {"status": "error", "step": "processing", "error": process_result}

        logger.info("Full pipeline completed successfully")

        return {
            "status": "success",
            "pipeline_steps": {
                "url_crawl": url_result,
                "content_crawl": content_result,
                "processing": process_result,
            },
        }
    except Exception as e:
        logger.error(f"Error in crawl_full_pipeline_task: {e}")
        return {
            "status": "error",
            "error": str(e),
        }
