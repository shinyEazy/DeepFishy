"""Celery tasks for embedding and vector insertion."""

from typing import Any, Dict, List

from celery import shared_task

from deepfishy.infra.config.settings import settings
from deepfishy.infra.llm.embedding_factory import (
    get_embedding_dim,
    get_embedding_provider,
)
from deepfishy.infra.storage.minio import MinioService
from deepfishy.infra.vector.milvus import MilvusService
from deepfishy.shared.logging import logger
from ingestion.embedding_pipeline import EmbeddingPipeline


def _get_embedding_provider(model_name: str = None):
    """Get embedding provider from config.yaml."""
    logger.info(
        f"Initializing embedding provider: {model_name or 'default from config'}"
    )
    return get_embedding_provider(model_name)


@shared_task(
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
    """Embed articles and insert into Milvus in batches."""
    batch_size = batch_size or getattr(settings, "BATCH_INSERT_SIZE", 64)
    embedding_model = embedding_model or getattr(settings, "EMBEDDING_MODEL", "default")

    errors = []
    articles_data = []

    try:
        if isinstance(articles_data_or_bucket, list):
            logger.info(f"🚀 Loading {len(articles_data_or_bucket)} articles (direct)")
            articles_data = articles_data_or_bucket
        else:
            bucket_name = articles_data_or_bucket
            logger.info(f"☁️  Loading articles from MinIO bucket: {bucket_name}")
            articles_data = _load_articles_from_minio(bucket_name, errors)

        if not articles_data:
            error_msg = (
                "❌ No articles provided"
                if isinstance(articles_data_or_bucket, list)
                else f"❌ No articles loaded from MinIO bucket: {articles_data_or_bucket} (errors: {len(errors)})"
            )
            logger.error(error_msg)
            if errors:
                logger.error(f"Load errors: {errors}")
            return {"status": "error", "message": error_msg, "errors": errors}

        logger.info(f"✓ Loaded {len(articles_data)} articles")

        logger.info("🔧 Initializing embedding provider...")
        try:
            embedding_provider = _get_embedding_provider(embedding_model)
            logger.info("✓ Embedding provider initialized")
        except Exception as error:
            logger.error(
                f"❌ Failed to initialize embedding provider: {error}",
                exc_info=True,
            )
            errors.append(f"Embedding provider init failed: {error}")
            return {
                "status": "error",
                "message": f"Embedding provider initialization failed: {error}",
                "errors": errors,
            }

        logger.info("🔧 Initializing MilvusService...")
        milvus_service = MilvusService(embedding_dim=get_embedding_dim(embedding_model))
        logger.info("✓ MilvusService initialized")

        pipeline = EmbeddingPipeline(embedding_provider, milvus_service)

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
    except Exception as error:
        logger.error(f"❌ Task failed with error: {error}", exc_info=True)
        errors.append(str(error))
        return {"status": "error", "message": str(error), "errors": errors}


def _load_articles_from_minio(
    bucket_name: str,
    errors: List[str],
) -> List[Dict[str, Any]]:
    """Load articles from MinIO bucket."""
    articles = []

    try:
        minio_service = MinioService()
        object_names = minio_service.list_objects(bucket_name)

        for object_name in object_names:
            try:
                data = minio_service.download_json(bucket_name, object_name)
                if data:
                    articles.append(data)
            except Exception as error:
                message = f"Error reading {object_name} from MinIO: {error}"
                logger.warning(message)
                errors.append(message)
    except Exception as error:
        message = f"Error accessing MinIO bucket {bucket_name}: {error}"
        logger.error(message)
        errors.append(message)

    return articles


@shared_task(
    bind=True,
    name="ingestion.embed_single_article",
    queue="ingestion",
)
def embed_single_article_task(
    self,
    article_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Embed and insert a single article for real-time processing."""
    try:
        embedding_provider = _get_embedding_provider()
        milvus_service = MilvusService(embedding_dim=get_embedding_dim())
        pipeline = EmbeddingPipeline(embedding_provider, milvus_service)

        chunked_articles, errors = pipeline.process_article(article_data)
        if not chunked_articles:
            return {"status": "error", "message": "No chunks generated", "errors": errors}

        articles_with_embeddings, embedding_errors = pipeline.generate_embeddings(
            chunked_articles
        )
        if not articles_with_embeddings:
            return {
                "status": "error",
                "message": "Failed to generate embeddings",
                "errors": embedding_errors,
            }

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
    except Exception as error:
        logger.error(f"❌ Single article task failed: {error}", exc_info=True)
        return {"status": "error", "message": str(error)}


__all__ = ["embed_and_insert_articles_task", "embed_single_article_task"]
