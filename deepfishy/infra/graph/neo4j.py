"""Neo4j graph database adapter."""

import threading
from typing import Any

from neo4j import Driver, GraphDatabase

from deepfishy.infra.config.settings import settings
from deepfishy.shared.logging import logger


class Neo4jService:
    """
    Service for Neo4j graph database operations.

    Provides both direct driver access and LangChain Neo4jGraph integration
    for use with LLMGraphTransformer.
    """

    _instance: "Neo4jService | None" = None
    _lock = threading.Lock()
    _driver: Driver | None = None
    _graph = None

    def __init__(self):
        self.uri = settings.NEO4J_URI
        self.user = settings.NEO4J_USER
        self.password = settings.NEO4J_PASSWORD
        self.database = settings.NEO4J_DATABASE

    @classmethod
    def get_instance(cls) -> "Neo4jService":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @property
    def driver(self) -> Driver:
        if self._driver is None:
            with self._lock:
                if self._driver is None:
                    self._driver = GraphDatabase.driver(
                        self.uri, auth=(self.user, self.password)
                    )
                    self._driver.verify_connectivity()
                    logger.info(f"Neo4j connection established: {self.uri}")
        return self._driver

    @property
    def graph(self):
        if self._graph is None:
            with self._lock:
                if self._graph is None:
                    from langchain_neo4j import Neo4jGraph

                    logger.info("Initializing LangChain Neo4jGraph")
                    self._graph = Neo4jGraph(
                        url=self.uri,
                        username=self.user,
                        password=self.password,
                        database=self.database,
                    )
        return self._graph

    def query(self, cypher: str, params: dict | None = None) -> list[dict]:
        with self.driver.session(database=self.database) as session:
            result = session.run(cypher, params or {})
            return [record.data() for record in result]

    def execute_write(self, cypher: str, params: dict | None = None) -> Any:
        with self.driver.session(database=self.database) as session:
            return session.execute_write(
                lambda tx: tx.run(cypher, params or {}).consume()
            )

    def create_indices(self) -> None:
        indices = [
            "CREATE INDEX IF NOT EXISTS FOR (n:__Entity__) ON (n.id)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Organization) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Person) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Event) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Event) ON (n.timestamp)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Event) ON (n.time_period)",
        ]

        for index_query in indices:
            try:
                self.execute_write(index_query)
                logger.debug(f"Created index: {index_query[:50]}...")
            except Exception as exc:
                logger.warning(f"Index creation warning: {exc}")

    def get_stats(self) -> dict[str, Any]:
        try:
            node_count = self.query("MATCH (n) RETURN count(n) as count")[0]["count"]
            rel_count = self.query("MATCH ()-[r]->() RETURN count(r) as count")[0][
                "count"
            ]

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
        except Exception as exc:
            logger.error(f"Failed to get Neo4j stats: {exc}")
            return {
                "total_nodes": 0,
                "total_relationships": 0,
                "status": "error",
                "error": str(exc),
            }

    def clear_graph(self) -> dict[str, int]:
        logger.warning("Clearing entire Neo4j graph!")
        result = self.query("MATCH (n) DETACH DELETE n RETURN count(n) as deleted")
        deleted = result[0]["deleted"] if result else 0
        logger.info(f"Deleted {deleted} nodes")
        return {"deleted_nodes": deleted}

    def close(self) -> None:
        if self._driver:
            self._driver.close()
            self._driver = None
            logger.info("Neo4j connection closed")

    def __del__(self):
        self.close()


def get_neo4j_service() -> Neo4jService:
    """Get or create the singleton Neo4jService instance."""
    return Neo4jService.get_instance()
