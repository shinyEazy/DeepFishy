"""Neo4j query utilities for knowledge graph."""

from typing import List, Dict, Any, Optional
from datetime import datetime

from core.logging import logger
from services.neo4j import get_neo4j_service
from engine.graph_rag.models import GraphQueryResult, TemporalFilter


class GraphQueryService:
    """
    Service for querying the knowledge graph.

    Provides methods for:
    - Temporal queries (by time period)
    - Causal chain traversal
    - Entity search
    - Relationship filtering

    Example:
        >>> service = GraphQueryService()
        >>> result = service.query_by_time_period("Q4/2025")
        >>> print(result.context_text)
    """

    def __init__(self):
        self._neo4j = None

    @property
    def neo4j(self):
        """Lazy load Neo4j service."""
        if self._neo4j is None:
            self._neo4j = get_neo4j_service()
        return self._neo4j

    def query_by_time_period(
        self,
        time_period: str,
        entity_type: Optional[str] = None,
        limit: int = 20,
    ) -> GraphQueryResult:
        """
        Query events and relationships by time period.

        Args:
            time_period: Time filter (e.g., "Q3/2025", "10/2025", "2025")
            entity_type: Optional entity type filter (e.g., "Event", "Organization")
            limit: Max results

        Returns:
            GraphQueryResult with matched nodes and relationships

        Example:
            >>> result = service.query_by_time_period("Q4/2025", entity_type="Event")
        """
        # Build node pattern
        node_pattern = f"(n:{entity_type})" if entity_type else "(n)"

        cypher = f"""
        MATCH {node_pattern}
        WHERE n.time_period CONTAINS $time_period
           OR toString(n.timestamp) CONTAINS $time_period
           OR (n:__Entity__ AND EXISTS((n)<-[r]-() WHERE r.time_period CONTAINS $time_period))
        WITH n LIMIT $limit
        OPTIONAL MATCH (n)-[r]->(m)
        RETURN n, r, m, labels(n) as node_labels
        """

        start = datetime.now()
        try:
            results = self.neo4j.query(
                cypher,
                {
                    "time_period": time_period,
                    "limit": limit,
                },
            )
            query_time = (datetime.now() - start).total_seconds() * 1000

            return self._format_results(
                results, query_time, f"Time period: {time_period}"
            )

        except Exception as e:
            logger.error(f"Time period query failed: {e}")
            return self._empty_result(str(e))

    def query_causal_chain(
        self,
        entity_name: str,
        direction: str = "downstream",
        max_depth: int = 3,
        relationship_types: Optional[List[str]] = None,
    ) -> GraphQueryResult:
        """
        Find causal chain from/to an entity.

        Args:
            entity_name: Starting entity name or ID
            direction: "downstream" (effects) or "upstream" (causes)
            max_depth: Max hops in the chain
            relationship_types: Filter by relationship types

        Returns:
            GraphQueryResult with causal chain paths

        Example:
            >>> result = service.query_causal_chain("FED interest rate", direction="downstream")
        """
        rel_types = relationship_types or ["CAUSES", "AFFECTS", "LEADS_TO"]
        rel_pattern = "|".join(rel_types)

        if direction == "downstream":
            cypher = f"""
            MATCH (start)
            WHERE start.id CONTAINS $name 
               OR toLower(start.id) CONTAINS toLower($name)
            WITH start LIMIT 5
            MATCH path = (start)-[:{rel_pattern}*1..{max_depth}]->(end)
            RETURN path, start, end, 
                   [r IN relationships(path) | type(r)] as rel_types,
                   length(path) as depth
            ORDER BY depth
            LIMIT 20
            """
        else:
            cypher = f"""
            MATCH (end)
            WHERE end.id CONTAINS $name 
               OR toLower(end.id) CONTAINS toLower($name)
            WITH end LIMIT 5
            MATCH path = (start)-[:{rel_pattern}*1..{max_depth}]->(end)
            RETURN path, start, end,
                   [r IN relationships(path) | type(r)] as rel_types,
                   length(path) as depth
            ORDER BY depth
            LIMIT 20
            """

        start_time = datetime.now()
        try:
            results = self.neo4j.query(cypher, {"name": entity_name})
            query_time = (datetime.now() - start_time).total_seconds() * 1000

            return self._format_chain_results(
                results, query_time, f"Causal chain ({direction}) for: {entity_name}"
            )

        except Exception as e:
            logger.error(f"Causal chain query failed: {e}")
            return self._empty_result(str(e))

    def search_entities(
        self,
        query: str,
        entity_types: Optional[List[str]] = None,
        limit: int = 10,
    ) -> GraphQueryResult:
        """
        Full-text search across entities.

        Args:
            query: Search term
            entity_types: Filter by entity types
            limit: Max results

        Returns:
            GraphQueryResult with matched entities
        """
        # Build type filter
        if entity_types:
            type_filter = " OR ".join([f"n:{t}" for t in entity_types])
            type_clause = f"AND ({type_filter})"
        else:
            type_clause = ""

        cypher = f"""
        MATCH (n)
        WHERE (n.id CONTAINS $query 
               OR toLower(n.id) CONTAINS toLower($query))
              {type_clause}
        WITH n LIMIT $limit
        OPTIONAL MATCH (n)-[r]->(m)
        RETURN n, r, m, labels(n) as node_labels
        """

        start = datetime.now()
        try:
            results = self.neo4j.query(cypher, {"query": query, "limit": limit})
            query_time = (datetime.now() - start).total_seconds() * 1000

            return self._format_results(results, query_time, f"Search: {query}")

        except Exception as e:
            logger.error(f"Entity search failed: {e}")
            return self._empty_result(str(e))

    def get_related_entities(
        self,
        entity_name: str,
        relationship_types: Optional[List[str]] = None,
        limit: int = 20,
    ) -> GraphQueryResult:
        """
        Get entities directly related to a given entity.

        Args:
            entity_name: Entity to find relations for
            relationship_types: Filter by relationship types
            limit: Max results
        """
        rel_filter = ""
        if relationship_types:
            rel_pattern = "|".join(relationship_types)
            rel_filter = f":{rel_pattern}"

        cypher = f"""
        MATCH (source)-[r{rel_filter}]-(target)
        WHERE source.id CONTAINS $name
        RETURN source, r, target, type(r) as rel_type
        LIMIT $limit
        """

        start = datetime.now()
        try:
            results = self.neo4j.query(cypher, {"name": entity_name, "limit": limit})
            query_time = (datetime.now() - start).total_seconds() * 1000

            return self._format_results(
                results, query_time, f"Related to: {entity_name}"
            )

        except Exception as e:
            logger.error(f"Related entities query failed: {e}")
            return self._empty_result(str(e))

    def _format_results(
        self,
        results: List[Dict],
        query_time: float,
        context_prefix: str = "",
    ) -> GraphQueryResult:
        """Format Neo4j results into GraphQueryResult."""
        nodes = []
        relationships = []
        seen_nodes = set()

        for record in results:
            # Extract nodes
            for key in ["n", "m", "start", "end", "source", "target"]:
                if key in record and record[key]:
                    node = record[key]
                    node_id = node.get("id") or node.get("name")
                    if node_id and node_id not in seen_nodes:
                        nodes.append(node)
                        seen_nodes.add(node_id)

            # Extract relationships
            if "r" in record and record["r"]:
                relationships.append(record["r"])

        # Format as context text for LLM
        context_lines = [f"📊 {context_prefix}", ""]
        context_lines.append(f"Found {len(nodes)} entities:")

        for node in nodes[:15]:
            name = node.get("name") or node.get("id", "Unknown")
            node_type = node.get("type", "Entity")
            time_info = ""
            if node.get("time_period"):
                time_info = f" [{node['time_period']}]"
            elif node.get("timestamp"):
                time_info = f" [{node['timestamp']}]"

            context_lines.append(f"  • {name} ({node_type}){time_info}")

        if len(nodes) > 15:
            context_lines.append(f"  ... and {len(nodes) - 15} more")

        if relationships:
            context_lines.append(f"\nRelationships: {len(relationships)}")

        return GraphQueryResult(
            nodes=nodes,
            relationships=relationships,
            query_time_ms=query_time,
            context_text="\n".join(context_lines),
            total_results=len(nodes),
        )

    def _format_chain_results(
        self,
        results: List[Dict],
        query_time: float,
        context_prefix: str = "",
    ) -> GraphQueryResult:
        """Format causal chain results."""
        nodes = []
        relationships = []
        paths = []
        seen_nodes = set()

        for record in results:
            # Track path
            if "path" in record:
                paths.append(
                    {
                        "start": record.get("start", {}).get("name"),
                        "end": record.get("end", {}).get("name"),
                        "rel_types": record.get("rel_types", []),
                        "depth": record.get("depth", 0),
                    }
                )

            # Extract nodes
            for key in ["start", "end"]:
                if key in record and record[key]:
                    node = record[key]
                    node_id = node.get("id") or node.get("name")
                    if node_id and node_id not in seen_nodes:
                        nodes.append(node)
                        seen_nodes.add(node_id)

        # Format causal chains for LLM
        context_lines = [f"🔗 {context_prefix}", ""]
        context_lines.append(f"Found {len(paths)} causal paths:")

        for i, path in enumerate(paths[:10], 1):
            chain = " → ".join(path.get("rel_types", []))
            context_lines.append(f"  {i}. {path['start']} --[{chain}]--> {path['end']}")

        if len(paths) > 10:
            context_lines.append(f"  ... and {len(paths) - 10} more paths")

        return GraphQueryResult(
            nodes=nodes,
            relationships=relationships,
            paths=paths,
            query_time_ms=query_time,
            context_text="\n".join(context_lines),
            total_results=len(paths),
        )

    def _empty_result(self, error: str = "") -> GraphQueryResult:
        """Return empty result with error."""
        return GraphQueryResult(
            nodes=[],
            relationships=[],
            query_time_ms=0,
            context_text=f"Query failed: {error}" if error else "No results found",
            total_results=0,
        )


def get_graph_query_service() -> GraphQueryService:
    """Get GraphQueryService instance."""
    return GraphQueryService()
