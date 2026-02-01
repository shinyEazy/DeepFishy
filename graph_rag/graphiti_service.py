"""Graphiti service for temporal knowledge graph management.

This service wraps the Graphiti framework to provide session-based
knowledge graph operations for the iterative research pipeline.
"""

import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from dotenv import load_dotenv

from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType
from graphiti_core.llm_client.gemini_client import GeminiClient, LLMConfig
from graphiti_core.embedder.gemini import GeminiEmbedder, GeminiEmbedderConfig
from graphiti_core.cross_encoder.gemini_reranker_client import GeminiRerankerClient
from graphiti_core.search.search_config_recipes import NODE_HYBRID_SEARCH_RRF

from core.logging import logger
from core.config import settings
from utils.load_config import get_llm_config
from services.rag import SearchResult

load_dotenv()


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
    DEFAULT_LLM_MODEL = "gemini-2.0-flash"
    DEFAULT_EMBEDDING_MODEL = "embedding-001"
    DEFAULT_RERANKER_MODEL = "gemini-2.5-flash-lite"

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
            gemini_config = get_llm_config("gemini-2.5-flash")
            if not gemini_config or "api_key" not in gemini_config:
                raise ValueError("Gemini API key not found in config.yaml")

            api_key = gemini_config["api_key"]

            # Initialize Graphiti
            self.graphiti = Graphiti(
                self.neo4j_uri,
                self.neo4j_user,
                self.neo4j_password,
                llm_client=GeminiClient(
                    config=LLMConfig(api_key=api_key, model=self.llm_model)
                ),
                embedder=GeminiEmbedder(
                    config=GeminiEmbedderConfig(
                        api_key=api_key, embedding_model=self.embedding_model
                    )
                ),
                cross_encoder=GeminiRerankerClient(
                    config=LLMConfig(api_key=api_key, model=self.reranker_model)
                ),
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
        Add search results as Graphiti episodes.

        Each SearchResult becomes an episode with temporal metadata
        preserved from the original article.

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

        added = 0
        for result in results:
            try:
                # Create unique episode name
                episode_name = f"{result.url}_{result.chunk_index}"

                # Determine reference time from article timestamp
                if result.date_ts and result.date_ts > 0:
                    reference_time = datetime.fromtimestamp(
                        result.date_ts, tz=timezone.utc
                    )
                else:
                    reference_time = datetime.now(timezone.utc)

                # Build source description with metadata
                source_desc = f"Query: {source_query}"
                if result.category:
                    source_desc += f", Category: {result.category}"
                if result.tags:
                    source_desc += f", Tags: {', '.join(result.tags[:5])}"

                # Add episode to graph
                await self.graphiti.add_episode(
                    name=episode_name,
                    episode_body=result.content,
                    source=EpisodeType.text,
                    source_description=source_desc,
                    reference_time=reference_time,
                )

                added += 1
                logger.debug(f"Added episode: {episode_name}")

            except Exception as e:
                logger.warning(f"Failed to add episode for {result.url}: {e}")
                continue

        logger.info(f"Added {added}/{len(results)} episodes to knowledge graph")
        return added

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
                result = await session.run(
                    """
                    MATCH (n:Entity)
                    RETURN n.uuid as uuid, 
                           n.name as name, 
                           n.summary as summary,
                           labels(n) as labels,
                           n.created_at as created_at
                    ORDER BY n.created_at DESC
                """
                )

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
                # Count entities
                entity_result = await session.run(
                    "MATCH (n:Entity) RETURN count(n) as count"
                )
                entity_count = await entity_result.single()

                # Count edges
                edge_result = await session.run(
                    "MATCH ()-[r]->() RETURN count(r) as count"
                )
                edge_count = await edge_result.single()

                # Count episodes
                episode_result = await session.run(
                    "MATCH (n:Episode) RETURN count(n) as count"
                )
                episode_count = await episode_result.single()

                return {
                    "entity_count": entity_count["count"] if entity_count else 0,
                    "edge_count": edge_count["count"] if edge_count else 0,
                    "episode_count": episode_count["count"] if episode_count else 0,
                }

        except Exception as e:
            logger.error(f"Failed to get graph stats: {e}")
            return {"entity_count": 0, "edge_count": 0, "episode_count": 0}

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


# Singleton instance for reuse - now tracks event loop
_graphiti_service: Optional[GraphitiService] = None
_graphiti_loop_id: Optional[int] = None


async def get_graphiti_service() -> GraphitiService:
    """Get or create the GraphitiService instance for the current event loop.

    The Graphiti/Neo4j async driver is bound to a specific event loop.
    If asyncio.run() creates a new loop, we must reinitialize the service.
    """
    global _graphiti_service, _graphiti_loop_id

    import asyncio

    current_loop = asyncio.get_running_loop()
    current_loop_id = id(current_loop)

    # Check if we need to reinitialize due to event loop change
    if _graphiti_service is not None and _graphiti_loop_id != current_loop_id:
        logger.info("Event loop changed, reinitializing GraphitiService")
        # Don't try to close old service - it's bound to the old loop
        _graphiti_service = None
        _graphiti_loop_id = None

    if _graphiti_service is None:
        _graphiti_service = GraphitiService()
        await _graphiti_service.initialize()
        _graphiti_loop_id = current_loop_id

    return _graphiti_service


def reset_graphiti_service():
    """Reset the global GraphitiService instance.

    Call this before asyncio.run() if you need a fresh service.
    """
    global _graphiti_service, _graphiti_loop_id
    _graphiti_service = None
    _graphiti_loop_id = None
