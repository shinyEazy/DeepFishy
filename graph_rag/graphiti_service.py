"""Graphiti service for temporal knowledge graph management.

This service wraps the Graphiti framework to provide session-based
knowledge graph operations for the iterative research pipeline.
"""

import asyncio
import threading
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType
from graphiti_core.llm_client.gemini_client import GeminiClient, LLMConfig
from graphiti_core.embedder.gemini import GeminiEmbedder, GeminiEmbedderConfig
from graphiti_core.cross_encoder.gemini_reranker_client import GeminiRerankerClient
from graphiti_core.search.search_config_recipes import NODE_HYBRID_SEARCH_RRF
from graphiti_core.utils.bulk_utils import RawEpisode

from deepfishy.shared.logging import logger
from deepfishy.infra.config.settings import settings
from deepfishy.infra.config.model_registry import get_llm_config
from deepfishy.features.knowledge_graph.rag import SearchResult
from graph_rag.entity_types import ENTITY_TYPES, EDGE_TYPES, EDGE_TYPE_MAP

load_dotenv()


class SafeGeminiClient(GeminiClient):
    """Gemini client wrapper that normalizes malformed structured outputs.

    Graphiti expects object-shaped responses for attribute extraction, but Gemini
    occasionally returns a top-level JSON array like `[ {...} ]` even when the
    schema is an object. That crashes downstream code before Pydantic validation
    can help. We coerce obvious single-object arrays back into a dict here.
    """

    @staticmethod
    def _coerce_structured_response(
        response: Any, response_model: type | None
    ) -> Dict[str, Any] | Any:
        if response_model is None or not isinstance(response, list):
            return response

        schema_type = response_model.model_json_schema().get("type")
        if schema_type == "array":
            return response

        if not response:
            logger.warning(
                "SafeGeminiClient received an empty list for object schema; coercing to empty object."
            )
            return {}

        first = response[0]
        if isinstance(first, dict):
            logger.warning(
                "SafeGeminiClient received list output for object schema; using the first item."
            )
            return first

        logger.warning(
            "SafeGeminiClient received non-dict list output for object schema; coercing to empty object."
        )
        return {}

    async def _generate_response(
        self,
        messages,
        response_model=None,
        max_tokens=None,
        model_size=None,
    ):
        response = await super()._generate_response(
            messages=messages,
            response_model=response_model,
            max_tokens=max_tokens,
            model_size=model_size,
        )
        return self._coerce_structured_response(response, response_model)


class GraphitiService:
    """
    Session-based Graphiti wrapper for temporal knowledge graphs.

    This service manages the lifecycle of a Graphiti knowledge graph,
    including initialization, clearing between sessions, adding episodes
    from search results, and querying for entities and relationships.

    Example:
        >>> service = GraphitiService()
        >>> await service.initialize()
        >>> await service.clear_graph()  # Start fresh session
        >>> await service.add_search_results(results, "user query")
        >>> entities = await service.get_all_entities()
        >>> await service.close()
    """

    # Default configuration
    DEFAULT_LLM_MODEL = "gemini-3.1-flash-lite-preview"
    DEFAULT_EMBEDDING_MODEL = "gemini-embedding-001"
    DEFAULT_RERANKER_MODEL = "gemini-3.1-flash-lite-preview"

    def __init__(
        self,
        neo4j_uri: Optional[str] = None,
        neo4j_user: Optional[str] = None,
        neo4j_password: Optional[str] = None,
        llm_model: str = DEFAULT_LLM_MODEL,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        reranker_model: str = DEFAULT_RERANKER_MODEL,
    ):
        """
        Initialize GraphitiService.

        Args:
            neo4j_uri: Neo4j connection URI (default from settings)
            neo4j_user: Neo4j username (default from settings)
            neo4j_password: Neo4j password (default from settings)
            llm_model: Model name for entity extraction
            embedding_model: Model name for embeddings
            reranker_model: Model name for reranking
        """
        self.neo4j_uri = neo4j_uri or settings.NEO4J_URI
        self.neo4j_user = neo4j_user or settings.NEO4J_USER
        self.neo4j_password = neo4j_password or settings.NEO4J_PASSWORD

        self.llm_model = llm_model
        self.embedding_model = embedding_model
        self.reranker_model = reranker_model

        self.graphiti: Optional[Graphiti] = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize Graphiti client with LLM and embedder."""
        if self._initialized:
            return

        try:
            # Get API key from config
            gemini_config = get_llm_config(self.llm_model)
            if not gemini_config or "api_key" not in gemini_config:
                raise ValueError("Gemini API key not found in config.yaml")

            api_key = gemini_config["api_key"]

            self.graphiti = Graphiti(
                self.neo4j_uri,
                self.neo4j_user,
                self.neo4j_password,
                llm_client=SafeGeminiClient(
                    config=LLMConfig(api_key=api_key, model=self.llm_model)
                ),
                embedder=GeminiEmbedder(
                    config=GeminiEmbedderConfig(
                        api_key=api_key,
                        embedding_model=self.embedding_model,
                        embedding_dim=1536,
                    )
                ),
                cross_encoder=GeminiRerankerClient(
                    config=LLMConfig(api_key=api_key, model=self.reranker_model)
                ),
                max_coroutines=50,
            )

            self._initialized = True
            logger.info(f"GraphitiService initialized with Neo4j at {self.neo4j_uri}")

        except Exception as e:
            logger.error(f"Failed to initialize GraphitiService: {e}")
            raise

    async def clear_graph(self) -> None:
        """
        Clear all nodes and edges for a new session.

        This should be called at the start of each research pipeline run
        to ensure a fresh knowledge graph.
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Use Neo4j driver directly to clear the graph
            driver = self.graphiti.driver
            async with driver.session() as session:
                await session.run("MATCH (n) DETACH DELETE n")

            logger.info("Cleared knowledge graph for new session")

        except Exception as e:
            logger.error(f"Failed to clear graph: {e}")
            raise

    async def add_search_results(
        self,
        results: List[SearchResult],
        source_query: str,
    ) -> int:
        """
        Add search results as Graphiti episodes using bulk ingestion.

        Uses add_episode_bulk for cross-episode entity deduplication:
        - Extracts entities from ALL episodes together
        - Deduplicates entities in memory BEFORE saving
        - Uses name matching + embedding similarity for resolution
        - Applies custom Vietnamese financial entity types

        Args:
            results: List of SearchResult objects from Milvus
            source_query: The query that produced these results (for context)

        Returns:
            Number of episodes successfully added
        """
        if not self._initialized:
            await self.initialize()

        if not results:
            return 0

        try:
            # Build RawEpisode objects for bulk ingestion
            raw_episodes: List[RawEpisode] = []

            for result in results:
                # Create unique episode name
                episode_name = f"{result.url}_{result.chunk_index}"
                # episode_name = f"{result.title} - Part {result.chunk_index}"

                # Determine reference time from article timestamp
                if result.date_ts and result.date_ts > 0:
                    reference_time = datetime.fromtimestamp(
                        result.date_ts, tz=timezone.utc
                    )
                else:
                    reference_time = datetime.now(timezone.utc)

                # Build source description with provenance metadata.
                source_desc_parts: List[str] = []
                if result.url:
                    source_desc_parts.append(f"Source URL: {result.url}")
                if result.category:
                    source_desc_parts.append(f"Category: {result.category}")
                if result.tags:
                    source_desc_parts.append(f"Tags: {', '.join(result.tags[:5])}")
                source_desc = ", ".join(source_desc_parts)

                # Prepend provenance so extraction has direct access to URLs.
                related_urls = [
                    tag
                    for tag in (result.tags or [])
                    if isinstance(tag, str)
                    and tag.startswith(("http://", "https://"))
                    and tag != result.url
                ]
                provenance_lines: List[str] = []
                if result.url:
                    provenance_lines.append(f"Source URL: {result.url}")
                if related_urls:
                    provenance_lines.append(
                        f"Related Source URLs: {', '.join(related_urls[:5])}"
                    )
                episode_content = result.content
                if provenance_lines:
                    episode_content = "\n".join(provenance_lines + ["", result.content])

                # print(f"Episode name: {episode_name}")
                # print(f"Episode content: {result.content}")
                # print(f"Episode source: {result.url}")
                # print(f"Episode source description: {source_desc}")
                # print(f"Episode reference time: {reference_time}")

                raw_episodes.append(
                    RawEpisode(
                        name=episode_name,
                        content=episode_content,
                        source=EpisodeType.text,
                        source_description=source_desc,
                        reference_time=reference_time,
                    )
                )

            # Use add_episode_bulk for cross-episode entity deduplication
            # This processes all episodes together, enabling better entity resolution
            bulk_result = await self.graphiti.add_episode_bulk(
                bulk_episodes=raw_episodes,
                entity_types=ENTITY_TYPES,
                edge_types=EDGE_TYPES,
                edge_type_map=EDGE_TYPE_MAP,
                custom_extraction_instructions="""
                You are an expert financial knowledge graph extraction agent for the Vietnamese stock market.

                Your task is to extract structured entities and relationships STRICTLY following the provided ontology.

                IMPORTANT PRINCIPLES:
                1. Only extract entities that match the defined ENTITY TYPES.
                2. Do NOT invent entities, relationships, or attributes.
                3. Every extracted entity and relationship MUST be grounded in the source text.
                4. Prefer MarketEvent as the causal anchor whenever something "happens".
                5. Do NOT confuse:
                - Stock Exchanges (HOSE, HNX, UPCOM) with PublicCompany
                - MarketIndex with FinancialMetric
                - Rumors/Announcements with confirmed events
                """,
            )

            added = len(bulk_result.episodes)
            logger.info(
                f"Bulk added {added} episodes with {len(bulk_result.nodes)} entities, "
                f"{len(bulk_result.edges)} edges"
            )
            return added

        except Exception as e:
            logger.error(f"Failed to bulk add episodes: {e}", exc_info=True)
            return 0

    async def get_all_entities(self) -> List[Dict[str, Any]]:
        """
        Retrieve all entity nodes from the current graph.

        Returns:
            List of entity dictionaries with uuid, name, summary, labels
        """
        if not self._initialized:
            await self.initialize()

        try:
            driver = self.graphiti.driver
            async with driver.session() as session:
                result = await session.run("""
                    MATCH (n:Entity)
                    RETURN n.uuid as uuid, 
                           n.name as name, 
                           n.summary as summary,
                           labels(n) as labels,
                           n.created_at as created_at
                    ORDER BY n.created_at DESC
                """)

                entities = []
                async for record in result:
                    entities.append(
                        {
                            "uuid": record["uuid"],
                            "name": record["name"],
                            "summary": record["summary"],
                            "labels": record["labels"],
                            "created_at": record["created_at"],
                        }
                    )

                return entities

        except Exception as e:
            logger.error(f"Failed to get entities: {e}")
            return []

    async def search_facts(
        self,
        query: str,
        limit: int = 10,
        center_node_uuid: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant facts/relationships in the graph.

        Args:
            query: Natural language search query
            limit: Maximum number of results
            center_node_uuid: Optional center node for reranking

        Returns:
            List of fact dictionaries with uuid, fact, valid_at, invalid_at
        """
        if not self._initialized:
            await self.initialize()

        try:
            results = await self.graphiti.search(
                query,
                center_node_uuid=center_node_uuid,
                num_results=limit,
            )

            facts = []
            for result in results:
                facts.append(
                    {
                        "uuid": result.uuid,
                        "fact": result.fact,
                        "valid_at": getattr(result, "valid_at", None),
                        "invalid_at": getattr(result, "invalid_at", None),
                        "source_node_uuid": getattr(result, "source_node_uuid", None),
                        "target_node_uuid": getattr(result, "target_node_uuid", None),
                    }
                )

            return facts

        except Exception as e:
            logger.error(f"Failed to search facts: {e}")
            return []

    async def search_nodes(
        self,
        query: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search for entity nodes in the graph.

        Args:
            query: Natural language search query
            limit: Maximum number of results

        Returns:
            List of node dictionaries
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Use node search recipe
            node_search_config = NODE_HYBRID_SEARCH_RRF.model_copy(deep=True)
            node_search_config.limit = limit

            results = await self.graphiti._search(
                query=query,
                config=node_search_config,
            )

            nodes = []
            for node in results.nodes:
                nodes.append(
                    {
                        "uuid": node.uuid,
                        "name": node.name,
                        "summary": node.summary[:200] if node.summary else "",
                        "labels": list(node.labels) if node.labels else [],
                        "created_at": node.created_at,
                    }
                )

            return nodes

        except Exception as e:
            logger.error(f"Failed to search nodes: {e}")
            return []

    async def get_node_provenance(
        self,
        node_uuids: List[str],
    ) -> Dict[str, Dict[str, Any]]:
        """Fetch provenance fields for entity nodes by UUID.

        Returns a mapping keyed by node UUID with best-effort provenance
        metadata such as `source_url` and `extraction_date`.
        """
        if not node_uuids:
            return {}

        if not self._initialized:
            await self.initialize()

        try:
            driver = self.graphiti.driver
            async with driver.session() as session:
                result = await session.run(
                    """
                    MATCH (n:Entity)
                    WHERE n.uuid IN $uuids
                    RETURN n.uuid AS uuid,
                           n.name AS name,
                           n.source_url AS source_url,
                           n.extraction_date AS extraction_date,
                           labels(n) AS labels
                    """,
                    {"uuids": node_uuids},
                )

                provenance: Dict[str, Dict[str, Any]] = {}
                async for record in result:
                    provenance[record["uuid"]] = {
                        "uuid": record["uuid"],
                        "name": record["name"],
                        "source_url": record["source_url"],
                        "extraction_date": record["extraction_date"],
                        "labels": record["labels"] or [],
                    }

                return provenance

        except Exception as e:
            logger.warning(f"Failed to fetch node provenance: {e}")
            return {}

    async def get_graph_stats(self) -> Dict[str, int]:
        """
        Get statistics about the current graph state.

        Returns:
            Dictionary with entity_count, edge_count, episode_count
        """
        if not self._initialized:
            await self.initialize()

        try:
            driver = self.graphiti.driver
            async with driver.session() as session:
                entity_query = "MATCH (n:Entity) RETURN count(n) as count"
                edge_query = "MATCH ()-[r]->() RETURN count(r) as count"
                episode_query = "MATCH (n:Episodic) RETURN count(n) as count"
                params = {}

                # Count entities
                entity_result = await session.run(entity_query, params)
                entity_count = await entity_result.single()

                # Count edges
                edge_result = await session.run(edge_query, params)
                edge_count = await edge_result.single()

                # Count episodes
                episode_result = await session.run(episode_query, params)
                episode_count = await episode_result.single()

                return {
                    "entity_count": entity_count["count"] if entity_count else 0,
                    "edge_count": edge_count["count"] if edge_count else 0,
                    "episode_count": episode_count["count"] if episode_count else 0,
                }

        except Exception as e:
            logger.error(f"Failed to get graph stats: {e}")
            return {
                "entity_count": 0,
                "edge_count": 0,
                "episode_count": 0,
            }

    async def close(self) -> None:
        """Close Graphiti connection and release resources."""
        if self.graphiti:
            try:
                await self.graphiti.close()
                logger.info("GraphitiService connection closed")
            except Exception as e:
                logger.warning(f"Error closing GraphitiService: {e}")
            finally:
                self.graphiti = None
                self._initialized = False


# Cache Graphiti services per event loop because the async Neo4j driver
# is loop-bound and cannot be safely reused across independent asyncio.run() calls.
_graphiti_services: Dict[int, GraphitiService] = {}
_graphiti_services_lock = threading.Lock()


async def get_graphiti_service() -> GraphitiService:
    """Get or create the GraphitiService instance for the current event loop."""
    current_loop = asyncio.get_running_loop()
    current_loop_id = id(current_loop)

    with _graphiti_services_lock:
        existing_service = _graphiti_services.get(current_loop_id)
    if existing_service is not None:
        return existing_service

    logger.info("Event loop changed, initializing GraphitiService for a new loop")
    new_service = GraphitiService()
    await new_service.initialize()

    with _graphiti_services_lock:
        existing_service = _graphiti_services.get(current_loop_id)
        if existing_service is None:
            _graphiti_services[current_loop_id] = new_service
            return new_service

    # Another coroutine won the race while we were initializing.
    await new_service.close()
    return existing_service


def reset_graphiti_service():
    """Reset cached GraphitiService instances.

    If called from inside a running event loop, the service for that loop is
    closed asynchronously. Otherwise we just clear the cache so future calls
    build fresh loop-local clients.
    """
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    if current_loop is None:
        with _graphiti_services_lock:
            _graphiti_services.clear()
        return

    current_loop_id = id(current_loop)
    with _graphiti_services_lock:
        service = _graphiti_services.pop(current_loop_id, None)

    if service is not None:
        current_loop.create_task(service.close())
