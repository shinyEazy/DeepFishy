"""Neo4j database service for knowledge graph operations."""

import os
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
import threading

from neo4j import GraphDatabase, Driver

from core.logging import logger
from core.config import settings


class Neo4jService:
    """
    Service for Neo4j graph database operations.

    Provides both direct driver access and LangChain Neo4jGraph integration
    for use with LLMGraphTransformer.
    """

    _instance: Optional["Neo4jService"] = None
    _lock = threading.Lock()
    _driver: Optional[Driver] = None
    _graph = None  # Lazy import Neo4jGraph

    def __init__(self):
        self.uri = settings.NEO4J_URI
        self.user = settings.NEO4J_USER
        self.password = settings.NEO4J_PASSWORD
        self.database = settings.NEO4J_DATABASE

    @classmethod
    def get_instance(cls) -> "Neo4jService":
        """Get or create singleton instance (thread-safe)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @property
    def driver(self) -> Driver:
        """Get Neo4j driver (lazy initialization)."""
        if self._driver is None:
            with self._lock:
                if self._driver is None:
                    logger.info(f"Connecting to Neo4j at {self.uri}")
                    self._driver = GraphDatabase.driver(
                        self.uri, auth=(self.user, self.password)
                    )
                    # Verify connectivity
                    self._driver.verify_connectivity()
                    logger.info("Neo4j connection established")
        return self._driver

    @property
    def graph(self):
        """
        Get LangChain Neo4jGraph for LLMGraphTransformer.

        Returns:
            Neo4jGraph instance for use with graph transformers
        """
        if self._graph is None:
            with self._lock:
                if self._graph is None:
                    # Lazy import to avoid dependency issues
                    from langchain_neo4j import Neo4jGraph

                    logger.info("Initializing LangChain Neo4jGraph")
                    self._graph = Neo4jGraph(
                        url=self.uri,
                        username=self.user,
                        password=self.password,
                        database=self.database,
                    )
        return self._graph

    def query(self, cypher: str, params: Optional[Dict] = None) -> List[Dict]:
        """
        Execute a Cypher query and return results.

        Args:
            cypher: Cypher query string
            params: Optional query parameters

        Returns:
            List of result records as dictionaries
        """
        with self.driver.session(database=self.database) as session:
            result = session.run(cypher, params or {})
            return [record.data() for record in result]

    def execute_write(self, cypher: str, params: Optional[Dict] = None) -> Any:
        """
        Execute a write transaction.

        Args:
            cypher: Cypher query string
            params: Optional query parameters

        Returns:
            Transaction result
        """
        with self.driver.session(database=self.database) as session:
            return session.execute_write(
                lambda tx: tx.run(cypher, params or {}).consume()
            )

    def create_indices(self) -> None:
        """Create indices for efficient graph queries."""
        indices = [
            # Entity indices
            "CREATE INDEX IF NOT EXISTS FOR (n:__Entity__) ON (n.id)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Organization) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Person) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Event) ON (n.name)",
            # Temporal indices
            "CREATE INDEX IF NOT EXISTS FOR (n:Event) ON (n.timestamp)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Event) ON (n.time_period)",
            # Full-text search (requires APOC)
        ]

        for index_query in indices:
            try:
                self.execute_write(index_query)
                logger.debug(f"Created index: {index_query[:50]}...")
            except Exception as e:
                logger.warning(f"Index creation warning: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the knowledge graph."""
        try:
            node_count = self.query("MATCH (n) RETURN count(n) as count")[0]["count"]
            rel_count = self.query("MATCH ()-[r]->() RETURN count(r) as count")[0][
                "count"
            ]

            # Get node labels distribution
            labels = self.query(
                "MATCH (n) RETURN labels(n) as labels, count(*) as count "
                "ORDER BY count DESC LIMIT 10"
            )

            return {
                "total_nodes": node_count,
                "total_relationships": rel_count,
                "node_labels": labels,
                "status": "connected",
            }
        except Exception as e:
            logger.error(f"Failed to get Neo4j stats: {e}")
            return {
                "total_nodes": 0,
                "total_relationships": 0,
                "status": "error",
                "error": str(e),
            }

    def clear_graph(self) -> Dict[str, int]:
        """
        Clear all nodes and relationships from the graph.

        WARNING: This deletes all data!

        Returns:
            Count of deleted nodes and relationships
        """
        logger.warning("Clearing entire Neo4j graph!")
        result = self.query("MATCH (n) DETACH DELETE n RETURN count(n) as deleted")
        deleted = result[0]["deleted"] if result else 0
        logger.info(f"Deleted {deleted} nodes")
        return {"deleted_nodes": deleted}

    def close(self) -> None:
        """Close the Neo4j connection."""
        if self._driver:
            self._driver.close()
            self._driver = None
            logger.info("Neo4j connection closed")

    def __del__(self):
        """Cleanup on garbage collection."""
        self.close()


# Singleton accessor
_neo4j_service: Optional[Neo4jService] = None


def get_neo4j_service() -> Neo4jService:
    """
    Get or create the singleton Neo4jService instance.

    Returns:
        Neo4jService instance
    """
    return Neo4jService.get_instance()
