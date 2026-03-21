"""Graphiti service for temporal knowledge graph management.

This service wraps the Graphiti framework to provide session-based
knowledge graph operations for the iterative research pipeline.
"""

from dotenv import load_dotenv
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType
from graphiti_core.llm_client.gemini_client import GeminiClient, LLMConfig
from graphiti_core.embedder.gemini import GeminiEmbedder, GeminiEmbedderConfig
from graphiti_core.cross_encoder.gemini_reranker_client import GeminiRerankerClient
from graphiti_core.search.search_config_recipes import NODE_HYBRID_SEARCH_RRF
from graphiti_core.utils.bulk_utils import RawEpisode

from core.logging import logger
from core.config import settings
from utils.load_config import get_llm_config
from services.rag import SearchResult
from graph_rag.entity_types import ENTITY_TYPES, EDGE_TYPES, EDGE_TYPE_MAP

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
    DEFAULT_LLM_MODEL = "gemini-2.5-flash"
    DEFAULT_EMBEDDING_MODEL = "gemini-embedding-001"
    DEFAULT_RERANKER_MODEL = "gemini-2.5-flash"

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
                llm_client=GeminiClient(
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
                max_coroutines=10,
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
        group_id: Optional[str] = None,
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
            group_id: Optional namespace for session isolation

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

                # Build source description with metadata
                source_desc = ""
                if result.category:
                    source_desc += f"Category: {result.category}"
                if result.tags:
                    source_desc += f", Tags: {', '.join(result.tags[:5])}"

                # print(f"Episode name: {episode_name}")
                # print(f"Episode content: {result.content}")
                # print(f"Episode source: {result.url}")
                # print(f"Episode source description: {source_desc}")
                # print(f"Episode reference time: {reference_time}")

                raw_episodes.append(
                    RawEpisode(
                        name=episode_name,
                        content=result.content,
                        source=EpisodeType.text,
                        source_description=source_desc,
                        reference_time=reference_time,
                    )
                )

            # Use add_episode_bulk for cross-episode entity deduplication
            # This processes all episodes together, enabling better entity resolution
            bulk_result = await self.graphiti.add_episode_bulk(
                bulk_episodes=raw_episodes,
                group_id=group_id,
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

                Think step-by-step:
                - What happened? → MarketEvent
                - Who is affected? → PublicCompany
                - What number changed? → FinancialMetric
                - Why did it happen? → Causes relationship
                - Is this macro-driven? → MacroIndicator
                """,
            )

            added = len(bulk_result.episodes)
            logger.info(
                f"Bulk added {added} episodes with {len(bulk_result.nodes)} entities, "
                f"{len(bulk_result.edges)} edges (group_id={group_id})"
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
        group_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant facts/relationships in the graph.

        Args:
            query: Natural language search query
            limit: Maximum number of results
            center_node_uuid: Optional center node for reranking
            group_id: Optional namespace to search within

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
                group_ids=[group_id] if group_id else None,
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
        group_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for entity nodes in the graph.

        Args:
            query: Natural language search query
            limit: Maximum number of results
            group_id: Optional namespace to search within

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
                group_ids=[group_id] if group_id else None,
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

    async def build_communities(self, group_id: Optional[str] = None) -> int:
        """
        Build communities using Leiden algorithm.

        Communities group related entity nodes together and provide
        high-level synthesized information about graph contents.

        Args:
            group_id: Optional namespace to scope community building.
                      If provided, only builds communities for this group.
                      Without this, Graphiti processes the ENTIRE graph.

        Returns:
            Number of communities created
        """
        import time as _time
        from graphiti_core.utils.maintenance.community_operations import (
            remove_communities,
            build_community,
        )
        from graphiti_core.helpers import semaphore_gather

        if not self._initialized:
            await self.initialize()

        try:
            group_ids = [group_id] if group_id else None
            driver = self.graphiti.driver
            llm_client = self.graphiti.llm_client

            # Sub-step 1: Remove existing communities
            t0 = _time.time()
            logger.info(
                "[build_communities] Sub-step 1/5: Removing existing communities..."
            )
            await remove_communities(driver)
            logger.info(
                f"[build_communities] Sub-step 1/5: remove_communities done in {_time.time() - t0:.2f}s"
            )

            # Sub-step 2: Get community clusters (label propagation) — INLINED with logging
            t1 = _time.time()
            logger.info(
                f"[build_communities] Sub-step 2/5: Getting community clusters (group_ids={group_ids})..."
            )

            from graphiti_core.nodes import EntityNode
            from graphiti_core.utils.maintenance.community_operations import Neighbor

            community_clusters = []
            effective_group_ids = group_ids

            if effective_group_ids is None:
                group_id_values, _, _ = await driver.execute_query(
                    "MATCH (n:Entity) WHERE n.group_id IS NOT NULL RETURN collect(DISTINCT n.group_id) AS group_ids"
                )
                effective_group_ids = (
                    group_id_values[0]["group_ids"] if group_id_values else []
                )
                logger.info(
                    f"[build_communities]   No group_ids specified, found {len(effective_group_ids)} groups: {effective_group_ids[:5]}..."
                )

            for gid in effective_group_ids:
                t_gid = _time.time()
                logger.info(f"[build_communities]   Processing group_id={gid}...")

                # 2a: Fetch all entity nodes for this group
                t_fetch = _time.time()
                nodes = await EntityNode.get_by_group_ids(driver, [gid])
                logger.info(
                    f"[build_communities]   Fetched {len(nodes)} entity nodes in {_time.time() - t_fetch:.2f}s"
                )

                if not nodes:
                    logger.info(
                        f"[build_communities]   No entities for group_id={gid}, skipping"
                    )
                    continue

                # 2b: Query neighbors for each node (N+1 pattern — this is the bottleneck)
                projection = {}
                t_neighbors = _time.time()
                for idx, node in enumerate(nodes):
                    if idx % 10 == 0 or idx == len(nodes) - 1:
                        logger.info(
                            f"[build_communities]   Querying neighbors: node {idx+1}/{len(nodes)} ({_time.time() - t_neighbors:.2f}s elapsed)..."
                        )

                    t_node = _time.time()
                    records, _, _ = await driver.execute_query(
                        """
                        MATCH (n:Entity {group_id: $group_id, uuid: $uuid})-[e:RELATES_TO]-(m:Entity {group_id: $group_id})
                        WITH count(e) AS count, m.uuid AS uuid
                        RETURN uuid, count
                        """,
                        uuid=node.uuid,
                        group_id=gid,
                    )
                    projection[node.uuid] = [
                        Neighbor(node_uuid=record["uuid"], edge_count=record["count"])
                        for record in records
                    ]

                    node_elapsed = _time.time() - t_node
                    if node_elapsed > 2.0:
                        logger.warning(
                            f"[build_communities]   SLOW: Node {idx+1} ({node.name}) took {node_elapsed:.2f}s"
                        )

                logger.info(
                    f"[build_communities]   All {len(nodes)} neighbor queries done in {_time.time() - t_neighbors:.2f}s"
                )

                # 2c: Label propagation (inlined with max iterations + logging)
                t_lp = _time.time()
                logger.info(
                    f"[build_communities]   Starting label propagation on {len(projection)} nodes..."
                )

                from collections import defaultdict as _defaultdict

                MAX_LP_ITERATIONS = 100
                community_map = {uuid: i for i, uuid in enumerate(projection.keys())}

                for iteration in range(MAX_LP_ITERATIONS):
                    no_change = True
                    new_community_map = {}

                    for uuid, neighbors in projection.items():
                        curr_community = community_map[uuid]
                        community_candidates = _defaultdict(int)
                        for neighbor in neighbors:
                            community_candidates[
                                community_map[neighbor.node_uuid]
                            ] += neighbor.edge_count
                        community_lst = [
                            (count, community)
                            for community, count in community_candidates.items()
                        ]
                        community_lst.sort(reverse=True)
                        candidate_rank, community_candidate = (
                            community_lst[0] if community_lst else (0, -1)
                        )
                        if community_candidate != -1 and candidate_rank > 1:
                            new_community = community_candidate
                        else:
                            new_community = max(community_candidate, curr_community)
                        new_community_map[uuid] = new_community
                        if new_community != curr_community:
                            no_change = False

                    if no_change:
                        logger.info(
                            f"[build_communities]   Label propagation converged after {iteration+1} iterations in {_time.time() - t_lp:.2f}s"
                        )
                        break

                    community_map = new_community_map

                    if iteration % 10 == 9:
                        n_communities = len(set(community_map.values()))
                        logger.info(
                            f"[build_communities]   Label propagation iteration {iteration+1}: {n_communities} communities ({_time.time() - t_lp:.2f}s)"
                        )
                else:
                    logger.warning(
                        f"[build_communities]   Label propagation did NOT converge after {MAX_LP_ITERATIONS} iterations! Stopping anyway."
                    )

                community_cluster_map = _defaultdict(list)
                for uuid, community in community_map.items():
                    community_cluster_map[community].append(uuid)
                cluster_uuids = list(community_cluster_map.values())
                logger.info(
                    f"[build_communities]   Label propagation: {len(cluster_uuids)} clusters in {_time.time() - t_lp:.2f}s"
                )

                from graphiti_core.helpers import semaphore_gather as _sg

                community_clusters.extend(
                    list(
                        await _sg(
                            *[
                                EntityNode.get_by_uuids(driver, cluster)
                                for cluster in cluster_uuids
                            ]
                        )
                    )
                )
                logger.info(
                    f"[build_communities]   Group {gid} done in {_time.time() - t_gid:.2f}s"
                )

            logger.info(
                f"[build_communities] Sub-step 2/5: get_community_clusters done in {_time.time() - t1:.2f}s "
                f"(found {len(community_clusters)} clusters)"
            )

            # Sub-step 3: Build communities (LLM summarization per cluster)
            t2 = _time.time()
            logger.info(
                f"[build_communities] Sub-step 3/5: Building {len(community_clusters)} communities via LLM..."
            )
            import asyncio as _asyncio

            semaphore = _asyncio.Semaphore(10)

            async def _limited_build(i, cluster):
                tc = _time.time()
                logger.info(
                    f"[build_communities]   Cluster {i+1}/{len(community_clusters)}: {len(cluster)} entities, starting LLM summarization..."
                )
                async with semaphore:
                    result = await build_community(llm_client, cluster)
                logger.info(
                    f"[build_communities]   Cluster {i+1}/{len(community_clusters)}: done in {_time.time() - tc:.2f}s"
                )
                return result

            communities = list(
                await semaphore_gather(
                    *[
                        _limited_build(i, cluster)
                        for i, cluster in enumerate(community_clusters)
                    ]
                )
            )
            community_nodes = [c[0] for c in communities]
            community_edges = [edge for c in communities for edge in c[1]]
            logger.info(
                f"[build_communities] Sub-step 3/5: build_community done in {_time.time() - t2:.2f}s ({len(community_nodes)} nodes, {len(community_edges)} edges)"
            )

            # Sub-step 4: Generate embeddings
            t3 = _time.time()
            logger.info(
                f"[build_communities] Sub-step 4/5: Generating embeddings for {len(community_nodes)} community nodes..."
            )
            await semaphore_gather(
                *[
                    node.generate_name_embedding(self.graphiti.embedder)
                    for node in community_nodes
                ],
                max_coroutines=self.graphiti.max_coroutines,
            )
            logger.info(
                f"[build_communities] Sub-step 4/5: Embeddings done in {_time.time() - t3:.2f}s"
            )

            # Sub-step 5: Save to Neo4j
            t4 = _time.time()
            logger.info(
                f"[build_communities] Sub-step 5/5: Saving {len(community_nodes)} nodes + {len(community_edges)} edges to Neo4j..."
            )
            await semaphore_gather(
                *[node.save(driver) for node in community_nodes],
                max_coroutines=self.graphiti.max_coroutines,
            )
            await semaphore_gather(
                *[edge.save(driver) for edge in community_edges],
                max_coroutines=self.graphiti.max_coroutines,
            )
            logger.info(
                f"[build_communities] Sub-step 5/5: Save done in {_time.time() - t4:.2f}s"
            )

            count = len(community_nodes)
            logger.info(
                f"[build_communities] TOTAL: Built {count} communities in {_time.time() - t0:.2f}s (group_id={group_id})"
            )
            return count

        except Exception as e:
            logger.error(f"Failed to build communities: {e}", exc_info=True)
            return 0

    async def get_communities(
        self, group_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve detailed information about all communities.

        Args:
            group_id: Optional namespace to filter communities by

        Returns:
            List of community dictionaries with uuid, name, summary, and entity_count
        """
        if not self._initialized:
            await self.initialize()

        try:
            driver = self.graphiti.driver
            async with driver.session() as session:
                if group_id:
                    query = """
                        MATCH (c:Community)
                        WHERE c.group_id = $group_id
                        OPTIONAL MATCH (c)-[:HAS_MEMBER]->(e:Entity)
                        RETURN c.uuid as uuid, 
                               c.name as name, 
                               c.summary as summary,
                               c.created_at as created_at,
                               count(e) as entity_count
                        ORDER BY entity_count DESC
                    """
                    result = await session.run(query, {"group_id": group_id})
                else:
                    query = """
                        MATCH (c:Community)
                        OPTIONAL MATCH (c)-[:HAS_MEMBER]->(e:Entity)
                        RETURN c.uuid as uuid, 
                               c.name as name, 
                               c.summary as summary,
                               c.created_at as created_at,
                               count(e) as entity_count
                        ORDER BY entity_count DESC
                    """
                    result = await session.run(query)

                communities = []
                async for record in result:
                    communities.append(
                        {
                            "uuid": record["uuid"],
                            "name": record["name"],
                            "summary": record["summary"],
                            "created_at": record["created_at"],
                            "entity_count": record["entity_count"],
                        }
                    )

                return communities

        except Exception as e:
            logger.error(f"Failed to get communities: {e}")
            return []

    async def get_graph_stats(self, group_id: Optional[str] = None) -> Dict[str, int]:
        """
        Get statistics about the current graph state.

        Args:
            group_id: Optional namespace to filter stats by

        Returns:
            Dictionary with entity_count, edge_count, episode_count, community_count
        """
        if not self._initialized:
            await self.initialize()

        try:
            driver = self.graphiti.driver
            async with driver.session() as session:
                # Build WHERE clause for group_id filtering
                # Note: Graphiti uses Episodic label for episode nodes
                if group_id:
                    entity_query = "MATCH (n:Entity) WHERE n.group_id = $group_id RETURN count(n) as count"
                    edge_query = "MATCH (a)-[r]->(b) WHERE a.group_id = $group_id OR b.group_id = $group_id RETURN count(r) as count"
                    episode_query = "MATCH (n:Episodic) WHERE n.group_id = $group_id RETURN count(n) as count"
                    community_query = "MATCH (n:Community) WHERE n.group_id = $group_id RETURN count(n) as count"
                    params = {"group_id": group_id}
                else:
                    entity_query = "MATCH (n:Entity) RETURN count(n) as count"
                    edge_query = "MATCH ()-[r]->() RETURN count(r) as count"
                    episode_query = "MATCH (n:Episodic) RETURN count(n) as count"
                    community_query = "MATCH (n:Community) RETURN count(n) as count"
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

                # Count communities
                community_result = await session.run(community_query, params)
                community_count = await community_result.single()

                return {
                    "entity_count": entity_count["count"] if entity_count else 0,
                    "edge_count": edge_count["count"] if edge_count else 0,
                    "episode_count": episode_count["count"] if episode_count else 0,
                    "community_count": (
                        community_count["count"] if community_count else 0
                    ),
                }

        except Exception as e:
            logger.error(f"Failed to get graph stats: {e}")
            return {
                "entity_count": 0,
                "edge_count": 0,
                "episode_count": 0,
                "community_count": 0,
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
