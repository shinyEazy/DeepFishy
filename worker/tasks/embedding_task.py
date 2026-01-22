"""Celery task for embedding generation and Milvus insertion."""

import asyncio
import json
from typing import List, Dict, Any
import requests

from app.celery_app import celery_app
from app.services.embeddings import EmbeddingService
from app.services.milvus import MilvusService
from app.services.minio import MinioService
from app.ingestion.embedding_pipeline import EmbeddingPipeline
from app.core.logging import logger
from app.core.config import settings
from app.worker.utils import check_embedding_server_health


def _get_embedding_service():
    """Initialize EmbeddingService for embeddings via remote API."""
    logger.info("Initializing EmbeddingService")
    return EmbeddingService(
        api_url=settings.EMBEDDING_API_URL + "/embed",
        timeout=settings.EMBEDDING_API_TIMEOUT,
        max_retries=settings.EMBEDDING_API_MAX_RETRIES,
    )


@celery_app.task(
    bind=True,
    name="ingestion.embed_and_insert_articles",
    queue="ingestion",
    max_retries=3,
)
def embed_and_insert_articles_task(
    self,
    articles_data_or_bucket: str | List[Dict[str, Any]] = "crawler-data",
    batch_size: int = None,
    embedding_model: str = None,
) -> Dict[str, Any]:
    """
    Embed articles and insert into Milvus in batches.

    Workflow:
    1. Load articles (either from direct parameter or MinIO)
    2. Process articles: chunk text + enrich with title/sapo
    3. Generate embeddings for chunks
    4. Insert into Milvus in batches
    5. Return statistics

    Note: Embedding server health check is performed once at pipeline entry
    (crawl_article_urls_task), so we assume server is healthy here.

    Args:
        articles_data_or_bucket:
            - List[Dict] of article data (direct from crawler), OR
            - str bucket name to load articles from MinIO (default: "crawler-data")
        batch_size: Batch size for Milvus insertion (default from config)
        embedding_model: Model name for embeddings (default from config)

    Returns:
        Dictionary with task result:
        {
            "status": "success" | "error",
            "total_articles": int,
            "total_chunks": int,
            "total_embeddings": int,
            "total_inserted": int,
            "errors": List[str] or None
        }
    """
    batch_size = batch_size or getattr(settings, "BATCH_INSERT_SIZE", 64)
    embedding_model = embedding_model or getattr(settings, "EMBEDDING_MODEL", "default")

    errors = []
    articles_data = []

    try:
        # Step 1: Load articles (handle both direct data and MinIO bucket)
        if isinstance(articles_data_or_bucket, list):
            # Direct article data from crawler
            logger.info(f"🚀 Loading {len(articles_data_or_bucket)} articles (direct)")
            articles_data = articles_data_or_bucket
        else:
            # Load from MinIO bucket
            bucket_name = articles_data_or_bucket
            logger.info(f"☁️  Loading articles from MinIO bucket: {bucket_name}")
            articles_data = _load_articles_from_minio(bucket_name, errors)

        if not articles_data:
            if isinstance(articles_data_or_bucket, list):
                error_msg = "❌ No articles provided"
            else:
                error_msg = f"❌ No articles loaded from MinIO bucket: {articles_data_or_bucket} (errors: {len(errors)})"
            logger.error(error_msg)
            if errors:
                logger.error(f"Load errors: {errors}")
            return {
                "status": "error",
                "message": error_msg,
                "errors": errors,
            }

        logger.info(f"✓ Loaded {len(articles_data)} articles")

        # Step 2: Initialize services
        logger.info("🔧 Initializing EmbeddingService...")
        try:
            embedding_service = _get_embedding_service()
            logger.info("✓ EmbeddingService initialized")
        except Exception as e:
            logger.error(
                f"❌ Failed to initialize EmbeddingService: {e}", exc_info=True
            )
            errors.append(f"EmbeddingService init failed: {e}")
            return {
                "status": "error",
                "message": f"EmbeddingService initialization failed: {e}",
                "errors": errors,
            }

        logger.info("🔧 Initializing MilvusService...")
        milvus_service = MilvusService(
            embedding_dim=embedding_service.embedding_dim,
        )
        logger.info("✓ MilvusService initialized")

        # Step 3: Create embedding pipeline
        pipeline = EmbeddingPipeline(embedding_service, milvus_service)

        # Step 4: Process articles into chunks
        logger.info("🔄 Processing articles and generating embeddings...")
        chunked_articles, processing_errors = pipeline.process_articles(articles_data)
        errors.extend(processing_errors)

        if not chunked_articles:
            error_msg = "No chunks generated from articles"
            logger.error(error_msg)
            return {
                "status": "error",
                "message": error_msg,
                "total_articles": len(articles_data),
                "errors": errors,
            }

        # Step 5: Generate embeddings for all chunks
        articles_with_embeddings, embedding_errors = pipeline.generate_embeddings(
            chunked_articles
        )
        errors.extend(embedding_errors)

        if not articles_with_embeddings:
            error_msg = "Failed to generate embeddings"
            logger.error(error_msg)
            return {
                "status": "error",
                "message": error_msg,
                "total_articles": len(articles_data),
                "total_chunks": len(chunked_articles),
                "errors": errors,
            }

        logger.info(
            f"✓ Generated embeddings for {len(articles_with_embeddings)} chunks"
        )

        # Step 6: Insert into Milvus
        total_inserted, insert_errors = pipeline.insert_to_milvus(
            articles_with_embeddings, batch_size=batch_size
        )
        errors.extend(insert_errors)

        logger.info(
            f"✅ Task completed successfully: "
            f"{len(articles_data)} articles → {len(chunked_articles)} chunks → "
            f"{total_inserted} inserted to Milvus"
        )

        return {
            "status": "success",
            "total_articles": len(articles_data),
            "total_chunks": len(chunked_articles),
            "total_embeddings": len(articles_with_embeddings),
            "total_inserted": total_inserted,
            "errors": errors if errors else None,
        }

    except Exception as e:
        logger.error(f"❌ Task failed with error: {e}", exc_info=True)
        errors.append(str(e))
        return {
            "status": "error",
            "message": str(e),
            "errors": errors,
        }


def _load_articles_from_minio(
    bucket_name: str,
    errors: List[str],
) -> List[Dict[str, Any]]:
    """Load articles from MinIO bucket."""
    articles = []

    try:
        minio_service = MinioService()

        # List objects in bucket
        object_names = minio_service.list_objects(bucket_name)

        for object_name in object_names:
            try:
                # Download and parse JSON from MinIO
                data = minio_service.download_json(bucket_name, object_name)
                if data:
                    articles.append(data)

            except Exception as e:
                error = f"Error reading {object_name} from MinIO: {e}"
                logger.warning(error)
                errors.append(error)

    except Exception as e:
        error = f"Error accessing MinIO bucket {bucket_name}: {e}"
        logger.error(error)
        errors.append(error)

    return articles


@celery_app.task(
    bind=True,
    name="ingestion.embed_single_article",
    queue="ingestion",
)
def embed_single_article_task(
    self,
    article_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Embed and insert a single article (for real-time processing).

    Args:
        article_data: Single article JSON data

    Returns:
        Dictionary with result
    """
    try:
        embedding_service = _get_embedding_service()
        milvus_service = MilvusService(
            embedding_dim=embedding_service.embedding_dim,
        )

        # Create pipeline for single article
        pipeline = EmbeddingPipeline(embedding_service, milvus_service)

        # Process single article
        chunked_articles, errors = pipeline.process_article(article_data)

        if not chunked_articles:
            return {
                "status": "error",
                "message": "No chunks generated",
                "errors": errors,
            }

        # Generate embeddings
        articles_with_embeddings, embedding_errors = pipeline.generate_embeddings(
            chunked_articles
        )

        if not articles_with_embeddings:
            return {
                "status": "error",
                "message": "Failed to generate embeddings",
                "errors": embedding_errors,
            }

        # Insert into Milvus
        total_inserted, insert_errors = pipeline.insert_to_milvus(
            articles_with_embeddings
        )

        logger.info(
            f"✓ Single article processed: {len(chunked_articles)} chunks, "
            f"{total_inserted} inserted to Milvus"
        )

        return {
            "status": "success",
            "chunks_created": len(chunked_articles),
            "chunks_inserted": total_inserted,
            "errors": (
                embedding_errors + insert_errors
                if (embedding_errors or insert_errors)
                else None
            ),
        }

    except Exception as e:
        logger.error(f"❌ Single article task failed: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e),
        }
