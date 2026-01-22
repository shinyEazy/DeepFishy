"""Celery tasks for crawler operations with MinIO storage."""

import asyncio
import json
import re
from typing import List
from datetime import datetime
import requests

from celery import chain, group
from celery_app import celery_app
from ingestion.crawler.spiders import ArticleURLSpider, ArticleContentSpider
from ingestion.crawler.pipeline import CrawlerPipeline
from services.minio import MinioService
from core.logging import logger
from core.constants import (
    CRAWLER_BASE_URL,
    CRAWLER_PATHS,
    CRAWLER_MAX_PAGES,
    CRAWLER_MAX_WORKERS,
)
from core.config import settings
from worker.utils import check_embedding_server_health


@celery_task(bind=True, name="crawler.crawl_article_urls", queue="crawler")
def crawl_article_urls_task(
    self,
    paths: List[str] = None,
    max_pages: int = None,
    max_workers: int = None,
) -> dict:
    """
    Celery task to crawl article URLs from category pages with checkpoint support.

    Workflow:
    1. Check embedding server health (fail-fast before starting any crawl)
    2. Load checkpoint to avoid re-crawling known URLs
    3. Crawl article URLs from category pages
    4. Save URLs to MinIO
    5. Automatically chain to content crawl task

    Args:
        paths: List of category paths to crawl (uses CRAWLER_PATHS if None)
        max_pages: Maximum pages per path (uses CRAWLER_MAX_PAGES if None)
        max_workers: Maximum concurrent workers (uses CRAWLER_MAX_WORKERS if None)

    Returns:
        Dictionary with crawl results including only NEW URLs not in checkpoint
    """
    from datetime import timezone

    # Use constants as defaults (with defensive programming) ✅ CLEANER PATTERN
    paths = paths or CRAWLER_PATHS
    max_pages = max_pages or CRAWLER_MAX_PAGES
    max_workers = max_workers or CRAWLER_MAX_WORKERS

    try:
        # Step 0: Check embedding server health FIRST (before starting any crawl work)
        logger.info(
            "🏥 [STEP 0] Checking embedding server health before crawl pipeline..."
        )
        is_healthy, health_message = check_embedding_server_health(
            timeout=getattr(settings, "EMBEDDING_API_TIMEOUT", 10)
        )

        if not is_healthy:
            error_msg = f"❌ Embedding server is not healthy: {health_message}. Aborting entire crawl pipeline."
            logger.error(error_msg)
            return {
                "status": "error",
                "error": error_msg,
                "urls": [],
            }

        logger.info("✓ Embedding server health check passed. Starting crawl pipeline.")

        logger.info(f"🔍 [STEP 1] Crawling article URLs from {len(paths)} paths...")

        # Load checkpoint from MinIO (all URLs crawled so far)
        try:
            minio = MinioService()  # ✅ BETTER ERROR HANDLING
        except Exception as e:
            logger.error(f"❌ Failed to initialize MinIO: {e}")
            return {
                "status": "error",
                "error": f"MinIO initialization failed: {e}",
                "urls": [],
            }

        checkpoint_data = minio.download_json(
            "crawler-data", "checkpoint/urls_checkpoint.json"
        )
        known_urls = (
            set(checkpoint_data.get("all_urls", [])) if checkpoint_data else set()
        )

        if known_urls:
            logger.info(f"📍 Loaded checkpoint with {len(known_urls)} known URLs")
        else:
            logger.info("📍 No checkpoint found, starting fresh crawl")

        spider = ArticleURLSpider(base_url=CRAWLER_BASE_URL, max_retries=5)
        try:
            all_urls_in_session, new_urls = asyncio.run(
                spider.crawl(paths, max_pages, max_workers, known_urls=known_urls)
            )
        finally:
            spider.close()  # ✅ ENSURE CLEANUP

        logger.info(
            f"✅ Found {len(new_urls)} NEW URLs (session total: {len(all_urls_in_session)})"
        )

        # Update checkpoint with ALL URLs (new + known)
        # Important: keep track of all URLs ever found to avoid re-processing
        updated_all_urls = list(known_urls.union(set(new_urls)))
        checkpoint_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),  # ✅ TIMEZONE-AWARE
            "total_known_urls": len(updated_all_urls),
            "new_urls_this_session": len(new_urls),
            "all_urls": updated_all_urls,  # Complete history - only unique new URLs
            "last_session_urls": new_urls,  # Only NEW URLs found this session
        }

        checkpoint_success = minio.upload_json(
            "crawler-data", "checkpoint/urls_checkpoint.json", checkpoint_data
        )
        if checkpoint_success:
            logger.info(
                f"💾 Updated checkpoint with {len(updated_all_urls)} total URLs"
            )

        # Save this session's URLs to MinIO
        timestamp = datetime.now().isoformat().replace(":", "-").split(".")[0]
        urls_data = {
            "timestamp": datetime.now().isoformat(),
            "new_urls": len(new_urls),
            "paths": paths,
            "urls": new_urls,  # Only new URLs for processing
        }

        object_name = f"crawled_urls/urls_{timestamp}.json"
        success = minio.upload_json("crawler-data", object_name, urls_data)

        if success:
            logger.info(f"💾 Saved {len(new_urls)} NEW URLs to MinIO: {object_name}")

        result = {
            "status": "success",
            "new_urls_collected": len(new_urls),
            "urls": new_urls,  # Only new URLs go to next task
            "total_checkpoint_urls": len(updated_all_urls),
            "minio_path": object_name,
        }

        # Chain to content crawl if we have NEW URLs
        if len(new_urls) > 0:
            logger.info(
                f"🔗 Chaining to content crawl task with {len(new_urls)} new URLs..."
            )
            crawl_article_content_task.apply_async(args=[result], queue="crawler")
        else:
            logger.info("⏭  No new URLs to crawl. Skipping content crawl.")

        return result

    except Exception as e:
        logger.error(f"❌ Error in crawl_article_urls_task: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "urls": [],
        }


@celery_task(bind=True, name="crawler.crawl_article_content", queue="crawler")
def crawl_article_content_task(self, previous_task_result: dict) -> dict:
    """
    Celery task to crawl article content from URLs.
    Receives URLs from previous task (crawl_article_urls_task).
    Saves each article as JSON to MinIO.
    Then chains to embedding_task for vector embedding and Milvus insertion.

    Args:
        previous_task_result: Result from crawl_article_urls_task containing URLs

    Returns:
        Dictionary with crawl statistics
    """
    try:
        # Extract URLs from previous task result
        urls = previous_task_result.get("urls", [])

        if not urls or len(urls) == 0:
            logger.warning("⚠️  No URLs provided for content crawl")
            return {
                "status": "error",
                "message": "No URLs provided",
                "uploaded": 0,
            }

        logger.info(f"🌐 [STEP 2] Crawling content for {len(urls)} URLs...")

        spider = ArticleContentSpider(base_url=CRAWLER_BASE_URL)
        successful, failed, articles_data = asyncio.run(
            spider.crawl(urls, CRAWLER_MAX_WORKERS)
        )
        spider.close()

        logger.info(f"✅ Content crawl: {successful} successful, {failed} failed")
        logger.info(f"💾 Articles uploaded to MinIO during crawl")

        # Chain to embedding task for vector embedding and Milvus insertion
        if successful > 0:
            logger.info(f"🔗 Chaining to embedding task with {successful} articles...")
            from worker.tasks.embedding_task import embed_and_insert_articles_task

            # Pass articles data directly to embedding task (no need to reload from MinIO)
            try:
                task_result = embed_and_insert_articles_task.apply_async(
                    args=[articles_data],  # Pass actual article data directly
                    queue="ingestion",
                    countdown=1,  # Shorter wait
                )
                logger.info(f"✅ Embedding task queued with ID: {task_result.id}")
            except Exception as e:
                logger.error(f"❌ Failed to queue embedding task: {e}", exc_info=True)
                return {
                    "status": "partial",
                    "successful": successful,
                    "failed": failed,
                    "uploaded": successful,
                    "embedding_error": str(e),
                }

        return {
            "status": "success",
            "successful": successful,
            "failed": failed,
            "uploaded": successful,
        }
    except Exception as e:
        logger.error(f"❌ Error in crawl_article_content_task: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "uploaded": 0,
        }


@celery_task(bind=True, name="crawler.crawl_full_pipeline", queue="crawler")
def crawl_full_pipeline_task(self) -> dict:
    """
    Celery task to run the full crawling pipeline SEQUENTIALLY.

    1. Crawl URLs → save to MinIO
    2. Crawl content → save JSON to MinIO
    3. Process articles → enrich & save to MinIO

    This runs as a chain so each step waits for the previous one.
    """
    try:
        logger.info("🚀 Starting FULL CRAWLER PIPELINE...")

        # Execute tasks in sequence (chain)
        # Each task output becomes the next task input
        pipeline = chain(
            crawl_article_urls_task.s(),  # Step 1: Get URLs
            crawl_article_content_task.s(),  # Step 2: Get content (uses URLs from step 1)
        )

        # Run the pipeline
        result = pipeline.apply_async()

        logger.info(f"🎯 Full pipeline task ID: {result.id}")

        return {
            "status": "queued",
            "pipeline_id": result.id,
            "message": "Full crawler pipeline started",
        }

    except Exception as e:
        logger.error(f"❌ Error in crawl_full_pipeline_task: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
        }
