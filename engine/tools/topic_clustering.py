"""Topic clustering tool for extracting topic clusters from knowledge graph.

Uses LLM to analyze extracted entities and group them into semantic topic
clusters for coverage evaluation in the research pipeline.

NOTE: These tools use SYNC Neo4j driver to avoid async event loop conflicts.
"""

import json
from typing import Dict, Any
from langchain_core.tools import tool
from neo4j import GraphDatabase

from core.logging import logger
from core.config import settings


def _get_llm_client():
    """Lazy import to get LLM client for clustering."""
    from utils.model_factory import create_llm_client
    from utils.load_config import get_default_llm_name

    model_name = get_default_llm_name()
    return create_llm_client(model_name)


def _get_neo4j_driver():
    """Get a synchronous Neo4j driver."""
    return GraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
    )


TOPIC_CLUSTERING_PROMPT = """You are an expert at analyzing entities and grouping them into semantic topic clusters.

Given the following entities extracted from Vietnamese financial news articles:

{entities_json}

Group these entities into meaningful topic clusters that would be relevant for a financial analysis report.

Consider:
- Political/Government topics (policies, leaders, diplomatic relations)
- Economic topics (trade, tariffs, GDP, inflation)
- Market topics (stocks, indices, sectors)
- Company-specific topics (businesses, executives)
- Geographic/Regional topics (countries, regions involved)

Return a JSON object with this structure:
{{
    "topics": [
        {{
            "name": "Topic name in Vietnamese",
            "entities": ["entity1", "entity2", ...],
            "summary": "Brief 1-2 sentence description of this topic cluster",
            "importance": "high" | "medium" | "low"
        }}
    ],
    "total_entities": <number>,
    "coverage_assessment": "Brief assessment of topic diversity"
}}

Guidelines:
- Create 3-7 topic clusters
- Each entity should belong to exactly one cluster
- Prioritize topics most relevant to financial analysis
- Use Vietnamese for topic names and summaries
- Mark importance based on relevance to financial reporting
"""


def _get_all_entities_sync() -> list:
    """Get all entities from Neo4j using sync driver."""
    driver = None
    try:
        driver = _get_neo4j_driver()
        with driver.session() as session:
            result = session.run(
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
            for record in result:
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
        logger.error(f"Failed to get entities (sync): {e}")
        return []
    finally:
        if driver:
            driver.close()


def _get_graph_stats_sync() -> Dict[str, int]:
    """Get graph stats using sync driver."""
    driver = None
    try:
        driver = _get_neo4j_driver()
        with driver.session() as session:
            entity_result = session.run("MATCH (n:Entity) RETURN count(n) as count")
            entity_count = entity_result.single()["count"]

            edge_result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            edge_count = edge_result.single()["count"]

            episode_result = session.run("MATCH (n:Episode) RETURN count(n) as count")
            episode_count = episode_result.single()["count"]

            return {
                "entity_count": entity_count,
                "edge_count": edge_count,
                "episode_count": episode_count,
            }

    except Exception as e:
        logger.error(f"Failed to get graph stats (sync): {e}")
        return {"entity_count": 0, "edge_count": 0, "episode_count": 0}
    finally:
        if driver:
            driver.close()


# ============================================================
# Synchronous Tools (for LangGraph compatibility)
# ============================================================


@tool
def cluster_topics_from_graph() -> Dict[str, Any]:
    """Extract and cluster topics from the current knowledge graph.

    This tool analyzes all entities in the Neo4j knowledge graph and
    groups them into semantic topic clusters using LLM analysis.
    Use this to understand what topics are covered and identify gaps.

    Returns:
        Dictionary containing:
        - topics: List of topic clusters with entities and summaries
        - total_entities: Total number of entities analyzed
        - coverage_assessment: Brief assessment of topic diversity
        - error: Error message if clustering failed

    Example usage:
        Use this after adding search results to the graph to evaluate
        whether you have sufficient topic coverage for a report.
    """
    try:
        # Get entities from graph using sync driver
        entities = _get_all_entities_sync()

        if not entities:
            return {
                "topics": [],
                "total_entities": 0,
                "coverage_assessment": "No entities found in knowledge graph. Need to add more content.",
                "needs_more_research": True,
            }

        # Prepare entities for LLM
        entity_list = []
        for entity in entities:
            entity_list.append(
                {
                    "name": entity.get("name", "Unknown"),
                    "summary": (entity.get("summary") or "")[:200],
                    "labels": entity.get("labels", []),
                }
            )

        # Call LLM for clustering
        llm = _get_llm_client()
        if not llm:
            return {
                "topics": [],
                "total_entities": len(entities),
                "coverage_assessment": "LLM not available for clustering",
                "error": "Failed to initialize LLM client",
            }

        prompt = TOPIC_CLUSTERING_PROMPT.format(
            entities_json=json.dumps(entity_list, ensure_ascii=False, indent=2)
        )

        # Use sync invoke instead of ainvoke
        response = llm.invoke(prompt)
        response_text = response.content

        # Parse JSON from response
        try:
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                result = json.loads(json_str)
            else:
                raise ValueError("No JSON found in response")

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse clustering JSON: {e}")
            return {
                "topics": [],
                "total_entities": len(entities),
                "coverage_assessment": response_text[:500],
                "parse_error": str(e),
            }

        result["total_entities"] = len(entities)
        result["needs_more_research"] = len(result.get("topics", [])) < 3

        logger.info(
            f"Clustered {len(entities)} entities into {len(result.get('topics', []))} topics"
        )
        return result

    except Exception as e:
        logger.error(f"Topic clustering failed: {e}", exc_info=True)
        return {
            "topics": [],
            "total_entities": 0,
            "coverage_assessment": f"Clustering failed: {str(e)}",
            "error": str(e),
        }


@tool
def get_graph_summary() -> Dict[str, Any]:
    """Get a summary of the current knowledge graph state.

    Returns statistics about entities, relationships, and episodes
    currently in the graph. Use this to monitor graph building progress.

    Returns:
        Dictionary with entity_count, edge_count, episode_count
    """
    return _get_graph_stats_sync()


@tool
def search_graph_for_facts(query: str, limit: int = 10) -> Dict[str, Any]:
    """Search the knowledge graph for relevant facts and relationships.

    This tool searches the Neo4j knowledge graph for facts related to
    a query. Facts are relationships between entities with temporal
    validity information.

    Args:
        query: Natural language query about what facts to find
        limit: Maximum number of facts to return (default: 10)

    Returns:
        Dictionary containing:
        - facts: List of relevant facts with temporal metadata
        - query: The original query
        - count: Number of facts found
    """
    driver = None
    try:
        driver = _get_neo4j_driver()
        with driver.session() as session:
            # Simple text search in facts
            result = session.run(
                """
                MATCH (s:Entity)-[r]->(t:Entity)
                WHERE r.fact CONTAINS $query OR s.name CONTAINS $query OR t.name CONTAINS $query
                RETURN r.uuid as uuid, 
                       r.fact as fact,
                       s.name as source_name,
                       t.name as target_name,
                       r.valid_at as valid_at,
                       r.invalid_at as invalid_at
                LIMIT $limit
            """,
                query=query,
                limit=limit,
            )

            facts = []
            for record in result:
                facts.append(
                    {
                        "uuid": record["uuid"],
                        "fact": record["fact"],
                        "source": record["source_name"],
                        "target": record["target_name"],
                        "valid_at": (
                            str(record["valid_at"]) if record["valid_at"] else None
                        ),
                        "invalid_at": (
                            str(record["invalid_at"]) if record["invalid_at"] else None
                        ),
                    }
                )

            return {
                "facts": facts,
                "query": query,
                "count": len(facts),
            }

    except Exception as e:
        logger.error(f"Graph fact search failed: {e}")
        return {
            "facts": [],
            "query": query,
            "count": 0,
            "error": str(e),
        }
    finally:
        if driver:
            driver.close()
