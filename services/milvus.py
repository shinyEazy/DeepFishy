import threading
from typing import List, Dict, Any, Optional
from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType

from core.logging import logger
from core.config import settings


class MilvusService:
    """Service for interacting with Milvus vector database."""

    # Collection schema definition
    COLLECTION_NAME = "articles"
    EMBEDDING_DIM = 1536

    # Class-level lock for thread-safe connection management
    _connection_lock = threading.Lock()
    _connection_count = 0  # Track active connections

    def __init__(
        self,
        host: str = None,
        port: int = None,
        collection_name: str = COLLECTION_NAME,
        embedding_dim: int = EMBEDDING_DIM,
    ):
        """
        Initialize Milvus service.

        Args:
            host: Milvus host (default from config)
            port: Milvus port (default from config)
            collection_name: Name of the collection
            embedding_dim: Dimension of embeddings
        """
        self.host = host or getattr(settings, "MILVUS_HOST")
        self.port = port or getattr(settings, "MILVUS_PORT")
        self.collection_name = collection_name
        self.embedding_dim = embedding_dim
        self.collection: Optional[Collection] = None

        self._connect()

    def _connect(self) -> None:
        """Connect to Milvus server (thread-safe)."""
        with MilvusService._connection_lock:
            try:
                # Check if already connected
                try:
                    from pymilvus import connections as milvus_connections

                    conn = milvus_connections._fetch_handler("default")
                    if conn is not None:
                        # Already connected, just increment count and init collection
                        MilvusService._connection_count += 1
                        self._init_collection()
                        return
                except Exception:
                    pass

                # Connect to Milvus
                connections.connect("default", host=self.host, port=self.port)
                MilvusService._connection_count = 1

                # Initialize collection
                self._init_collection()

            except Exception as e:
                logger.error(f"Failed to connect to Milvus: {e}")
                raise

    def _ensure_connected(self) -> bool:
        """Check connection and reconnect if necessary (thread-safe).

        Returns:
            True if connected, False if reconnection failed
        """
        try:
            # Try to check if connection is alive
            from pymilvus import connections as milvus_connections

            # Check if 'default' connection exists and is valid
            try:
                conn = milvus_connections._fetch_handler("default")
                if conn is None:
                    raise Exception("No connection handler")
                # Try a simple operation to verify connection is alive
                if self.collection:
                    _ = self.collection.num_entities
                return True
            except Exception as e:
                logger.warning(f"Connection lost, reconnecting: {e}")
                # Use lock for reconnection
                with MilvusService._connection_lock:
                    # Double-check after acquiring lock
                    try:
                        conn = milvus_connections._fetch_handler("default")
                        if conn is not None:
                            self._init_collection()
                            return True
                    except Exception:
                        pass
                    # Actually need to reconnect
                    connections.connect("default", host=self.host, port=self.port)
                    self._init_collection()
                return True

        except Exception as e:
            logger.error(f"Failed to reconnect to Milvus: {e}")
            return False

    def _init_collection(self) -> None:
        """Initialize or get the articles collection."""
        try:
            # Check if collection exists
            try:
                self.collection = Collection(self.collection_name)
            except Exception:
                # Collection doesn't exist, create it
                self._create_collection()

        except Exception as e:
            logger.error(f"Failed to initialize collection: {e}")
            raise

    def _create_collection(self) -> None:
        """Create the articles collection with schema."""
        try:
            # Define schema fields
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

            # Create index on embedding field
            self._create_index()

            logger.info(f"Created collection: {self.collection_name}")

        except Exception as e:
            logger.error(f"Failed to create collection: {e}")
            raise

    def _create_index(self) -> None:
        """Create index on embedding field for faster search."""
        try:
            if not self.collection:
                logger.error("Collection not initialized")
                return

            # Create IVF_FLAT index
            index_params = {
                "metric_type": "L2",  # Euclidean distance
                "index_type": "IVF_FLAT",
                "params": {"nlist": 128},
            }

            self.collection.create_index(
                field_name="embedding",
                index_params=index_params,
            )

            logger.info("Created index on embedding field")

        except Exception as e:
            logger.warning(f"Index creation warning: {e}")

    def insert_batch(
        self,
        chunked_articles: List[Dict[str, Any]],
        embeddings: List[List[float]],
        batch_size: int = 500,
    ) -> Dict[str, Any]:
        """
        Insert chunked articles and embeddings in batches.

        Args:
            chunked_articles: List of chunked article data (as dicts)
            embeddings: List of embedding vectors
            batch_size: Number of records per batch insert

        Returns:
            Dictionary with insertion statistics
        """
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

            # Process in batches
            for i in range(0, len(chunked_articles), batch_size):
                batch_articles = chunked_articles[i : i + batch_size]
                batch_embeddings = embeddings[i : i + batch_size]

                # Prepare data for insertion
                data = self._prepare_insert_data(batch_articles, batch_embeddings)

                # Insert into Milvus
                mr = self.collection.insert(data)
                inserted_count = len(batch_articles)
                total_inserted += inserted_count

                batch_count += 1
                logger.info(
                    f"Batch {batch_count}: Inserted {inserted_count} documents "
                    f"(IDs: {mr.primary_keys[:3]}...)"
                )

            # Flush to ensure persistence
            self.collection.flush()
            logger.info(
                f"Completed batch insertion: {total_inserted} documents in {batch_count} batches"
            )

            return {
                "status": "success",
                "total_inserted": total_inserted,
                "batch_count": batch_count,
            }

        except Exception as e:
            logger.error(f"Failed to insert batch: {e}")
            return {"status": "error", "message": str(e)}

    def insert_articles(
        self,
        articles_with_embeddings: List[Dict[str, Any]],
        batch_size: int = 64,
    ) -> int:
        """
        Insert articles (with embeddings) in batches.
        Simplified version that directly inserts articles with embeddings.

        Args:
            articles_with_embeddings: List of articles with embedding vectors
                Format: {
                    "id": str,
                    "doc_url": str,
                    "text": str,
                    "embedding": List[float],
                    "category": str,
                    "date_ts": int,
                    "tags": List[str] or comma-separated str (will be converted to comma-separated),
                    "chunk_index": int,
                }
            batch_size: Number of records per batch insert

        Returns:
            Total number of articles inserted
        """
        if not articles_with_embeddings:
            logger.warning("Empty articles list for insertion")
            return 0

        try:
            total_inserted = 0
            batch_count = 0

            # Process in batches
            for i in range(0, len(articles_with_embeddings), batch_size):
                batch = articles_with_embeddings[i : i + batch_size]

                # Prepare data for insertion
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
                    # Content field from embeddings service (~2048 chars)
                    content = article.get("content", "") or ""
                    # Safety check: should never exceed 8000 chars
                    if len(content) > 8000:
                        logger.warning(
                            f"Content exceeded limit for {article['id']}: {len(content)} chars, truncating"
                        )
                        content = content[:7997] + "..."
                    contents.append(content)
                    embeddings.append(article.get("embedding", []))
                    # Convert None to empty string for category
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

                # Insert into Milvus
                self.collection.insert(data)
                inserted_count = len(batch)
                total_inserted += inserted_count

                batch_count += 1
                logger.debug(f"Batch {batch_count}: Inserted {inserted_count} articles")

            # Flush to ensure persistence
            self.collection.flush()
            logger.info(
                f"✓ Inserted {total_inserted} articles in {batch_count} batches"
            )

            return total_inserted

        except Exception as e:
            logger.error(f"Failed to insert articles: {e}", exc_info=True)
            return 0

    def _prepare_insert_data(
        self,
        chunked_articles: List[Dict[str, Any]],
        embeddings: List[List[float]],
    ) -> List[List[Any]]:
        """
        Prepare data in Milvus format.

        Args:
            chunked_articles: List of chunked article data
            embeddings: List of embedding vectors

        Returns:
            List of data in Milvus format [ids, urls, texts, embeddings, categories, dates, tags, indices]
        """
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
        query_embedding: List[float],
        top_k: int = 10,
        category_filter: Optional[str] = None,
        date_range: Optional[tuple] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for similar articles.

        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return
            category_filter: Optional category filter
            date_range: Optional date range (start_ts, end_ts)

        Returns:
            List of search results with scores
        """
        try:
            # Ensure connection is alive before searching
            if not self._ensure_connected():
                logger.error("Failed to ensure Milvus connection")
                return []

            if not self.collection:
                logger.error("Collection not initialized")
                return []

            # Build filter expression
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

            # Load collection into memory
            self.collection.load()

            # Search
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

            # Format results
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

        except Exception as e:
            logger.error(f"Search failed: {e}", exc_info=True)
            return []

    def count(self) -> int:
        """Get total number of documents in collection."""
        try:
            if not self.collection:
                return 0
            return self.collection.num_entities
        except Exception as e:
            logger.error(f"Failed to count documents: {e}")
            return 0

    def drop_collection(self) -> bool:
        """Drop the collection (for cleanup/reset)."""
        try:
            if connections.has_collection(self.collection_name):
                connections.drop_collection(self.collection_name)
                logger.info(f"Dropped collection: {self.collection_name}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to drop collection: {e}")
            return False

    def disconnect(self) -> None:
        """Disconnect from Milvus."""
        try:
            connections.disconnect("default")
            logger.info("Disconnected from Milvus")
        except Exception as e:
            logger.warning(f"Disconnect warning: {e}")
