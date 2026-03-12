from typing import List, Dict, Tuple

from core.logging import logger
from embedding.base_embedding import BaseEmbedding
from services.embeddings import ChunkedArticle
from services.milvus import MilvusService


class EmbeddingPipeline:
    """Pipeline for processing articles into chunked, embedded articles ready for Milvus."""

    def __init__(
        self,
        embedding_provider: BaseEmbedding,
        milvus_service: MilvusService,
        chunking_service=None,
    ):
        """
        Initialize embedding pipeline.

        Args:
            embedding_provider: Provider for generating text embeddings (BaseEmbedding)
            milvus_service: Service for Milvus database operations
            chunking_service: Optional service for chunking articles (uses default if None)
        """
        self.embedding_provider = embedding_provider
        self.milvus_service = milvus_service
        self._chunking_service = chunking_service

    def process_article(self, article: Dict) -> Tuple[List[ChunkedArticle], List[str]]:
        """
        Process a single article into chunked, embedded articles.

        Delegates to EmbeddingService which handles fixed-size field allocation:
        - Title: max 256 chars
        - Sapo: max 768 chars
        - Content: max 1024 chars
        - Total: 2048 chars per chunk

        Args:
            article: Article dictionary from crawler output

        Returns:
            Tuple of (chunked_articles, errors)
        """
        errors = []

        try:
            # Validate article
            if not self._validate_article(article):
                error = "Invalid article: missing required fields"
                logger.warning(error)
                errors.append(error)
                return [], errors

            # Use chunking service if available, otherwise create one for chunking only
            if self._chunking_service:
                chunked_articles = self._chunking_service.process_article(article)
            else:
                from services.embeddings import EmbeddingService

                chunking_svc = EmbeddingService()
                chunked_articles = chunking_svc.process_article(article)

            if not chunked_articles:
                error = (
                    f"Article {article.get('title', 'Unknown')}: no chunks generated"
                )
                logger.warning(error)
                errors.append(error)
                return [], errors

            logger.debug(
                f"✓ Processed article '{article.get('title')}' into {len(chunked_articles)} chunks"
            )
            return chunked_articles, errors

        except Exception as e:
            error = f"Error processing article: {e}"
            logger.error(error, exc_info=True)
            errors.append(error)
            return [], errors

    def process_articles(
        self, articles: List[Dict]
    ) -> Tuple[List[ChunkedArticle], List[str]]:
        """
        Process multiple articles into chunked articles.

        Args:
            articles: List of article dictionaries

        Returns:
            Tuple of (all_chunked_articles, errors)
        """
        all_chunked_articles = []
        all_errors = []

        logger.info(f"Processing {len(articles)} articles...")

        for idx, article in enumerate(articles, 1):
            chunked_articles, errors = self.process_article(article)
            all_chunked_articles.extend(chunked_articles)
            all_errors.extend(errors)

            if idx % 10 == 0:
                logger.debug(
                    f"Progress: {idx}/{len(articles)} articles processed, "
                    f"{len(all_chunked_articles)} chunks created"
                )

        logger.info(
            f"✓ Processed {len(articles)} articles → {len(all_chunked_articles)} chunks"
        )
        if all_errors:
            logger.warning(
                f"⚠️  Encountered {len(all_errors)} errors during processing"
            )

        return all_chunked_articles, all_errors

    def generate_embeddings(
        self, chunked_articles: List[ChunkedArticle]
    ) -> Tuple[List[Dict], List[str]]:
        """
        Generate embeddings for chunked articles.

        Args:
            chunked_articles: List of ChunkedArticle objects

        Returns:
            Tuple of (articles_with_embeddings, errors)
        """
        if not chunked_articles:
            return [], []

        errors = []

        try:
            logger.info(f"Generating embeddings for {len(chunked_articles)} chunks...")

            # Extract texts to embed
            texts_to_embed = [ca.vector_source for ca in chunked_articles]

            # Generate embeddings using new interface (batch_encode)
            embeddings = self.embedding_provider.batch_encode(texts_to_embed)

            if len(embeddings) != len(chunked_articles):
                error = (
                    f"Embedding count mismatch: expected {len(chunked_articles)}, "
                    f"got {len(embeddings)}"
                )
                logger.error(error)
                errors.append(error)
                return [], errors

            # Combine chunked articles with embeddings
            articles_with_embeddings = []
            for chunked_article, embedding in zip(chunked_articles, embeddings):
                # Ensure all string fields are never None
                category = chunked_article.category or "uncategorized"
                if not isinstance(category, str):
                    category = (
                        str(category) if category is not None else "uncategorized"
                    )

                tags = chunked_article.tags or []
                if isinstance(tags, list):
                    tags_str = ",".join(str(t) for t in tags) if tags else ""
                else:
                    tags_str = str(tags) if tags else ""

                article_dict = {
                    "id": chunked_article.id,
                    "doc_url": chunked_article.doc_url or "",
                    "content": chunked_article.content or "",
                    "embedding": embedding,
                    "category": category,
                    "date_ts": chunked_article.date_ts or 0,
                    "tags": tags_str,
                    "chunk_index": chunked_article.chunk_index or 0,
                }
                articles_with_embeddings.append(article_dict)

            logger.info(f"✓ Generated {len(articles_with_embeddings)} embeddings")
            return articles_with_embeddings, errors

        except Exception as e:
            error = f"Error generating embeddings: {e}"
            logger.error(error, exc_info=True)
            errors.append(error)
            return [], [error]

    def insert_to_milvus(
        self, articles_with_embeddings: List[Dict], batch_size: int = 64
    ) -> Tuple[int, List[str]]:
        """
        Insert embedded articles into Milvus in batches.

        Args:
            articles_with_embeddings: List of articles with embeddings
            batch_size: Batch size for insertion

        Returns:
            Tuple of (total_inserted, errors)
        """
        if not articles_with_embeddings:
            return 0, []

        errors = []
        total_inserted = 0

        try:
            logger.info(
                f"Inserting {len(articles_with_embeddings)} articles into Milvus "
                f"in batches of {batch_size}..."
            )

            # Insert in batches
            for i in range(0, len(articles_with_embeddings), batch_size):
                batch = articles_with_embeddings[i : i + batch_size]

                try:
                    inserted = self.milvus_service.insert_articles(batch)
                    total_inserted += inserted
                    logger.debug(
                        f"Batch {i // batch_size + 1}: inserted {inserted} articles"
                    )
                except Exception as e:
                    error = f"Error inserting batch {i // batch_size + 1}: {e}"
                    logger.error(error, exc_info=True)
                    errors.append(error)

            logger.info(f"✓ Inserted {total_inserted} articles into Milvus")
            return total_inserted, errors

        except Exception as e:
            error = f"Error during Milvus insertion: {e}"
            logger.error(error, exc_info=True)
            errors.append(error)
            return 0, [error]

    @staticmethod
    def _validate_article(article: Dict) -> bool:
        """
        Validate article data.

        Args:
            article: Article dictionary

        Returns:
            True if valid, False otherwise
        """
        required_fields = ["url", "title"]
        return all(field in article and article[field] for field in required_fields)
