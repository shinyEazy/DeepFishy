"""Celery tasks for crawler operations with MinIO storage."""

import asyncio
from datetime import datetime
from typing import List

from celery import chain, shared_task

from deepfishy.shared.constants import (
    CRAWLER_BASE_URL,
    CRAWLER_MAX_PAGES,
    CRAWLER_MAX_WORKERS,
    CRAWLER_PATHS,
)
from deepfishy.infra.storage.minio import MinioService
from deepfishy.shared.logging import logger
from ingestion.crawler.spiders import ArticleContentSpider, ArticleURLSpider


@shared_task(bind=True, name="crawler.crawl_article_urls", queue="crawler")
def crawl_article_urls_task(
    self,
    paths: List[str] = None,
    max_pages: int = None,
    max_workers: int = None,
) -> dict:
    """Crawl article URLs from category pages with checkpoint support."""
    from datetime import timezone

    paths = paths or CRAWLER_PATHS
    max_pages = max_pages or CRAWLER_MAX_PAGES
    max_workers = max_workers or CRAWLER_MAX_WORKERS

    try:
        logger.info(f"🔍 [STEP 1] Crawling article URLs from {len(paths)} paths...")

        try:
            minio = MinioService()
        except Exception as error:
            logger.error(f"❌ Failed to initialize MinIO: {error}")
            return {
                "status": "error",
                "error": f"MinIO initialization failed: {error}",
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
            spider.close()

        logger.info(
            f"✅ Found {len(new_urls)} NEW URLs (session total: {len(all_urls_in_session)})"
        )

        updated_all_urls = list(known_urls.union(set(new_urls)))
        checkpoint_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_known_urls": len(updated_all_urls),
            "new_urls_this_session": len(new_urls),
            "all_urls": updated_all_urls,
            "last_session_urls": new_urls,
        }

        checkpoint_success = minio.upload_json(
            "crawler-data", "checkpoint/urls_checkpoint.json", checkpoint_data
        )
        if checkpoint_success:
            logger.info(
                f"💾 Updated checkpoint with {len(updated_all_urls)} total URLs"
            )

        timestamp = datetime.now().isoformat().replace(":", "-").split(".")[0]
        urls_data = {
            "timestamp": datetime.now().isoformat(),
            "new_urls": len(new_urls),
            "paths": paths,
            "urls": new_urls,
        }

        object_name = f"crawled_urls/urls_{timestamp}.json"
        success = minio.upload_json("crawler-data", object_name, urls_data)

        if success:
            logger.info(f"💾 Saved {len(new_urls)} NEW URLs to MinIO: {object_name}")

        result = {
            "status": "success",
            "new_urls_collected": len(new_urls),
            "urls": new_urls,
            "total_checkpoint_urls": len(updated_all_urls),
            "minio_path": object_name,
        }

        if len(new_urls) > 0:
            logger.info(
                f"🔗 Chaining to content crawl task with {len(new_urls)} new URLs..."
            )
            crawl_article_content_task.apply_async(args=[result], queue="crawler")
        else:
            logger.info("⏭  No new URLs to crawl. Skipping content crawl.")

        return result
    except Exception as error:
        logger.error(f"❌ Error in crawl_article_urls_task: {error}", exc_info=True)
        return {"status": "error", "error": str(error), "urls": []}


@shared_task(bind=True, name="crawler.crawl_article_content", queue="crawler")
def crawl_article_content_task(self, previous_task_result: dict) -> dict:
    """Crawl article content from URLs and chain into embedding."""
    try:
        urls = previous_task_result.get("urls", [])
        if not urls:
            logger.warning("⚠️  No URLs provided for content crawl")
            return {"status": "error", "message": "No URLs provided", "uploaded": 0}

        logger.info(f"🌐 [STEP 2] Crawling content for {len(urls)} URLs...")

        spider = ArticleContentSpider(base_url=CRAWLER_BASE_URL)
        successful, failed, articles_data = asyncio.run(
            spider.crawl(urls, CRAWLER_MAX_WORKERS)
        )
        spider.close()

        logger.info(f"✅ Content crawl: {successful} successful, {failed} failed")
        logger.info("💾 Articles uploaded to MinIO during crawl")

        if successful > 0:
            logger.info(f"🔗 Chaining to embedding task with {successful} articles...")
            from deepfishy.app.workers.tasks.embedding_task import (
                embed_and_insert_articles_task,
            )

            try:
                task_result = embed_and_insert_articles_task.apply_async(
                    args=[articles_data],
                    queue="ingestion",
                    countdown=1,
                )
                logger.info(f"✅ Embedding task queued with ID: {task_result.id}")
            except Exception as error:
                logger.error(
                    f"❌ Failed to queue embedding task: {error}", exc_info=True
                )
                return {
                    "status": "partial",
                    "successful": successful,
                    "failed": failed,
                    "uploaded": successful,
                    "embedding_error": str(error),
                }

        return {
            "status": "success",
            "successful": successful,
            "failed": failed,
            "uploaded": successful,
        }
    except Exception as error:
        logger.error(f"❌ Error in crawl_article_content_task: {error}", exc_info=True)
        return {"status": "error", "error": str(error), "uploaded": 0}


@shared_task(bind=True, name="crawler.crawl_full_pipeline", queue="crawler")
def crawl_full_pipeline_task(self) -> dict:
    """Run the full crawling pipeline sequentially."""
    try:
        logger.info("🚀 Starting FULL CRAWLER PIPELINE...")
        pipeline = chain(
            crawl_article_urls_task.s(),
            crawl_article_content_task.s(),
        )
        result = pipeline.apply_async()
        logger.info(f"🎯 Full pipeline task ID: {result.id}")
        return {
            "status": "queued",
            "pipeline_id": result.id,
            "message": "Full crawler pipeline started",
        }
    except Exception as error:
        logger.error(f"❌ Error in crawl_full_pipeline_task: {error}", exc_info=True)
        return {"status": "error", "error": str(error)}


__all__ = [
    "crawl_article_content_task",
    "crawl_article_urls_task",
    "crawl_full_pipeline_task",
]
