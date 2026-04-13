"""Milvus vector database adapter."""

import threading
from typing import Any

from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections

from deepfishy.infra.config.settings import settings
from deepfishy.shared.logging import logger


class MilvusService:
    """Service for interacting with Milvus vector database."""

    COLLECTION_NAME = "articles"
    EMBEDDING_DIM = 1536

    _connection_lock = threading.Lock()
    _connection_count = 0

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        collection_name: str = COLLECTION_NAME,
        embedding_dim: int = EMBEDDING_DIM,
    ):
        self.host = host or settings.MILVUS_HOST
        self.port = port or settings.MILVUS_PORT
        self.collection_name = collection_name
        self.embedding_dim = embedding_dim
        self.collection: Collection | None = None

        self._connect()

    def _connect(self) -> None:
        with MilvusService._connection_lock:
            try:
                try:
                    from pymilvus import connections as milvus_connections

                    conn = milvus_connections._fetch_handler("default")
                    if conn is not None:
                        MilvusService._connection_count += 1
                        self._init_collection()
                        return
                except Exception:
                    pass

                connections.connect("default", host=self.host, port=self.port)
                MilvusService._connection_count = 1
                self._init_collection()

            except Exception as exc:
                logger.error(f"Failed to connect to Milvus: {exc}")
                raise

    def _ensure_connected(self) -> bool:
        try:
            from pymilvus import connections as milvus_connections

            try:
                conn = milvus_connections._fetch_handler("default")
                if conn is None:
                    raise Exception("No connection handler")
                if self.collection:
                    _ = self.collection.num_entities
                return True
            except Exception as exc:
                logger.warning(f"Connection lost, reconnecting: {exc}")
                with MilvusService._connection_lock:
                    try:
                        conn = milvus_connections._fetch_handler("default")
                        if conn is not None:
                            self._init_collection()
                            return True
                    except Exception:
                        pass
                    connections.connect("default", host=self.host, port=self.port)
                    self._init_collection()
                return True

        except Exception as exc:
            logger.error(f"Failed to reconnect to Milvus: {exc}")
            return False

    def _init_collection(self) -> None:
        try:
            try:
                self.collection = Collection(self.collection_name)
            except Exception:
                self._create_collection()
        except Exception as exc:
            logger.error(f"Failed to initialize collection: {exc}")
            raise

    def _create_collection(self) -> None:
        try:
            fields = [
                FieldSchema(
                    name="id",
                    dtype=DataType.VARCHAR,
                    max_length=32,
                    is_primary=True,
                    description="MD5 hash of URL + chunk index",
                ),
                FieldSchema(
                    name="doc_url",
                    dtype=DataType.VARCHAR,
                    max_length=500,
                    description="Article source URL",
                ),
                FieldSchema(
                    name="content",
                    dtype=DataType.VARCHAR,
                    max_length=3000,
                    description="Enriched text with title + sapo + content",
                ),
                FieldSchema(
                    name="embedding",
                    dtype=DataType.FLOAT_VECTOR,
                    dim=self.embedding_dim,
                    description="Text embedding vector",
                ),
                FieldSchema(
                    name="category",
                    dtype=DataType.VARCHAR,
                    max_length=100,
                    description="Article category",
                ),
                FieldSchema(
                    name="date_ts",
                    dtype=DataType.INT64,
                    description="Unix timestamp of publication date",
                ),
                FieldSchema(
                    name="tags",
                    dtype=DataType.VARCHAR,
                    max_length=1000,
                    description="Comma-separated tags",
                ),
                FieldSchema(
                    name="chunk_index",
                    dtype=DataType.INT64,
                    description="Index of chunk within article",
                ),
            ]

            schema = CollectionSchema(
                fields=fields,
                description="Vector database for financial articles",
                enable_dynamic_field=False,
            )

            self.collection = Collection(
                name=self.collection_name,
                schema=schema,
                using="default",
            )
            self._create_index()
            logger.info(f"Created collection: {self.collection_name}")

        except Exception as exc:
            logger.error(f"Failed to create collection: {exc}")
            raise

    def _create_index(self) -> None:
        try:
            if not self.collection:
                logger.error("Collection not initialized")
                return

            index_params = {
                "metric_type": "L2",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 128},
            }

            self.collection.create_index(
                field_name="embedding",
                index_params=index_params,
            )

            logger.info("Created index on embedding field")

        except Exception as exc:
            logger.warning(f"Index creation warning: {exc}")

    def insert_batch(
        self,
        chunked_articles: list[dict[str, Any]],
        embeddings: list[list[float]],
        batch_size: int = 500,
    ) -> dict[str, Any]:
        if not chunked_articles or not embeddings:
            logger.warning("Empty input for batch insertion")
            return {"status": "error", "message": "Empty input"}

        if len(chunked_articles) != len(embeddings):
            logger.error(
                f"Mismatch: {len(chunked_articles)} articles vs {len(embeddings)} embeddings"
            )
            return {
                "status": "error",
                "message": "Mismatch between articles and embeddings",
            }

        try:
            total_inserted = 0
            batch_count = 0

            for i in range(0, len(chunked_articles), batch_size):
                batch_articles = chunked_articles[i : i + batch_size]
                batch_embeddings = embeddings[i : i + batch_size]
                data = self._prepare_insert_data(batch_articles, batch_embeddings)
                mr = self.collection.insert(data)
                inserted_count = len(batch_articles)
                total_inserted += inserted_count
                batch_count += 1
                logger.info(
                    f"Batch {batch_count}: Inserted {inserted_count} documents "
                    f"(IDs: {mr.primary_keys[:3]}...)"
                )

            self.collection.flush()
            logger.info(
                f"Completed batch insertion: {total_inserted} documents in {batch_count} batches"
            )

            return {
                "status": "success",
                "total_inserted": total_inserted,
                "batch_count": batch_count,
            }

        except Exception as exc:
            logger.error(f"Failed to insert batch: {exc}")
            return {"status": "error", "message": str(exc)}

    def insert_articles(
        self,
        articles_with_embeddings: list[dict[str, Any]],
        batch_size: int = 64,
    ) -> int:
        if not articles_with_embeddings:
            logger.warning("Empty articles list for insertion")
            return 0

        try:
            total_inserted = 0
            batch_count = 0

            for i in range(0, len(articles_with_embeddings), batch_size):
                batch = articles_with_embeddings[i : i + batch_size]

                ids = []
                doc_urls = []
                contents = []
                embeddings = []
                categories = []
                date_tss = []
                tags_list = []
                chunk_indices = []

                for article in batch:
                    ids.append(article["id"])
                    doc_urls.append(article.get("doc_url", "") or "")
                    content = article.get("content", "") or ""
                    if len(content) > 8000:
                        logger.warning(
                            f"Content exceeded limit for {article['id']}: {len(content)} chars, truncating"
                        )
                        content = content[:7997] + "..."
                    contents.append(content)
                    embeddings.append(article.get("embedding", []))
                    category = article.get("category") or ""
                    if not isinstance(category, str):
                        category = str(category) if category is not None else ""
                    categories.append(category)
                    date_tss.append(article.get("date_ts", 0) or 0)
                    tags = article.get("tags", []) or []
                    if isinstance(tags, list):
                        tags = ",".join(str(t) for t in tags) if tags else ""
                    else:
                        tags = str(tags) if tags else ""
                    tags_list.append(tags)
                    chunk_indices.append(article.get("chunk_index", 0) or 0)

                data = [
                    ids,
                    doc_urls,
                    contents,
                    embeddings,
                    categories,
                    date_tss,
                    tags_list,
                    chunk_indices,
                ]

                self.collection.insert(data)
                inserted_count = len(batch)
                total_inserted += inserted_count

                batch_count += 1
                logger.debug(f"Batch {batch_count}: Inserted {inserted_count} articles")

            self.collection.flush()
            logger.info(
                f"✓ Inserted {total_inserted} articles in {batch_count} batches"
            )

            return total_inserted

        except Exception as exc:
            logger.error(f"Failed to insert articles: {exc}", exc_info=True)
            return 0

    def _prepare_insert_data(
        self,
        chunked_articles: list[dict[str, Any]],
        embeddings: list[list[float]],
    ) -> list[list[Any]]:
        ids = []
        doc_urls = []
        texts = []
        categories = []
        date_tss = []
        tags_list = []
        chunk_indices = []

        for article in chunked_articles:
            ids.append(article["id"])
            doc_urls.append(article.get("doc_url", ""))
            texts.append(article.get("text", ""))
            categories.append(article.get("category") or "")
            date_tss.append(article.get("date_ts", 0))
            tags = article.get("tags", [])
            if isinstance(tags, list):
                tags = ",".join(tags) if tags else ""
            tags_list.append(tags)
            chunk_indices.append(article.get("chunk_index", 0))

        return [
            ids,
            doc_urls,
            texts,
            embeddings,
            categories,
            date_tss,
            tags_list,
            chunk_indices,
        ]

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        category_filter: str | None = None,
        date_range: tuple | None = None,
    ) -> list[dict[str, Any]]:
        try:
            if not self._ensure_connected():
                logger.error("Failed to ensure Milvus connection")
                return []

            if not self.collection:
                logger.error("Collection not initialized")
                return []

            filter_expr = ""
            if category_filter:
                filter_expr = f'category == "{category_filter}"'
            if date_range:
                start_ts, end_ts = date_range
                date_filter = f"date_ts >= {start_ts} && date_ts <= {end_ts}"
                if filter_expr:
                    filter_expr += f" && {date_filter}"
                else:
                    filter_expr = date_filter

            logger.debug(
                f"Filter expression: '{filter_expr}' (empty={not filter_expr})"
            )
            logger.debug(f"Query embedding dimension: {len(query_embedding)}")
            logger.debug(
                f"Collection info: num_entities={self.collection.num_entities}"
            )

            self.collection.load()
            search_params = {"metric_type": "L2", "params": {"nprobe": 10}}

            results = self.collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                expr=filter_expr if filter_expr else None,
                output_fields=[
                    "id",
                    "doc_url",
                    "content",
                    "category",
                    "date_ts",
                    "tags",
                    "chunk_index",
                ],
            )

            formatted_results = []
            if results and len(results) > 0:
                for hit in results[0]:
                    formatted_results.append(
                        {
                            "id": hit.get("id"),
                            "url": hit.get("doc_url"),
                            "content": hit.get("content"),
                            "category": hit.get("category"),
                            "date_ts": hit.get("date_ts"),
                            "tags": (
                                hit.get("tags", "").split(",")
                                if hit.get("tags")
                                else []
                            ),
                            "score": hit.get("distance"),
                        }
                    )

            if len(formatted_results) == 0:
                logger.warning(
                    f"No results found. Collection has {self.collection.num_entities} entities"
                )
            return formatted_results

        except Exception as exc:
            logger.error(f"Search failed: {exc}", exc_info=True)
            return []

    def count(self) -> int:
        try:
            if not self.collection:
                return 0
            return self.collection.num_entities
        except Exception as exc:
            logger.error(f"Failed to count documents: {exc}")
            return 0

    def drop_collection(self) -> bool:
        try:
            if connections.has_collection(self.collection_name):
                connections.drop_collection(self.collection_name)
                logger.info(f"Dropped collection: {self.collection_name}")
                return True
            return False
        except Exception as exc:
            logger.error(f"Failed to drop collection: {exc}")
            return False

    def disconnect(self) -> None:
        try:
            connections.disconnect("default")
            logger.info("Disconnected from Milvus")
        except Exception as exc:
            logger.warning(f"Disconnect warning: {exc}")
