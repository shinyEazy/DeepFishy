"""Tool for querying the Neo4j knowledge graph."""

import asyncio
import re
from typing import Dict, Any, Optional, Literal, List

from langchain_core.tools import tool

from core.logging import logger


def _get_graphiti():
    """Lazy import to avoid circular imports."""
    from graph_rag.graphiti_service import get_graphiti_service

    return get_graphiti_service()


def _get_group_id() -> Optional[str]:
    """Get the current session's group_id for scoped graph queries."""
    try:
        from engine.tools.search_and_build_graph import get_current_session_id

        return get_current_session_id()
    except Exception:
        return None


def _extract_urls(text: str) -> List[str]:
    """Extract HTTP(S) URLs from free text."""
    if not text:
        return []
    return re.findall(r"https?://[^\s,)]+", text)


def _load_article_metadata(urls: List[str]) -> Dict[str, Dict[str, Any]]:
    """Load article title/category metadata by URL from PostgreSQL."""
    clean_urls = [url for url in urls if isinstance(url, str) and url.strip()]
    if not clean_urls:
        return {}

    try:
        from db.models.article import Article
        from db.session import SessionLocal

        db = SessionLocal()
    except Exception as e:
        logger.warning(f"Article metadata unavailable: {e}")
        return {}

    try:
        rows = db.query(Article).filter(Article.url.in_(clean_urls)).all()
        return {
            row.url: {
                "title": row.title,
                "category": row.category,
                "date_published": row.date_published,
            }
            for row in rows
        }
    except Exception as e:
        logger.warning(f"Failed to load article metadata: {e}")
        return {}
    finally:
        db.close()


def _dedupe_sources(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate source dicts by URL while preserving first-seen order."""
    deduped: List[Dict[str, Any]] = []
    seen = set()

    for source in sources:
        if not isinstance(source, dict):
            continue
        url = str(source.get("url", "")).strip()
        if not url or url in seen:
            continue
        seen.add(url)
        deduped.append(
            {
                "url": url,
                "title": str(source.get("title") or url).strip(),
                "category": source.get("category"),
                "date_published": source.get("date_published"),
            }
        )

    return deduped


def _format_source_brief(source: Dict[str, Any]) -> str:
    """Format one source for compact inline display."""
    title = str(source.get("title") or "").strip()
    url = str(source.get("url") or "").strip()
    if title and title != url:
        return f"{title}: {url}"
    return url


def _build_source_dict(
    url: str,
    article_meta: Dict[str, Dict[str, Any]],
    fallback_title: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a normalized source dictionary from URL + metadata."""
    meta = article_meta.get(url, {})
    return {
        "url": url,
        "title": meta.get("title") or fallback_title or url,
        "category": meta.get("category"),
        "date_published": meta.get("date_published"),
    }


async def _query_knowledge_graph_async(
    query_type: str,
    query_value: str,
    limit: int = 10,
) -> Dict[str, Any]:
    """Async implementation of knowledge graph query."""
    group_id = _get_group_id()
    try:
        graphiti = await _get_graphiti()

        search_query = query_value
        if query_type == "time_period":
            search_query = f"Events in {query_value}"
        elif query_type == "causal_chain":
            search_query = f"Causes and effects of {query_value}"

        # Perform search, scoped to current session
        results = await graphiti.search_facts(
            search_query, limit=limit, group_id=group_id
        )

        related_node_uuids: List[str] = []
        for result in results:
            for key in ("source_node_uuid", "target_node_uuid"):
                node_uuid = result.get(key)
                if node_uuid and node_uuid not in related_node_uuids:
                    related_node_uuids.append(node_uuid)

        provenance_by_uuid = await graphiti.get_node_provenance(
            related_node_uuids, group_id=group_id
        )
        provenance_urls = [
            record.get("source_url")
            for record in provenance_by_uuid.values()
            if record.get("source_url")
        ]
        article_meta = _load_article_metadata(provenance_urls)

        # Format for consistency
        formatted_nodes = []
        context_lines = []
        all_sources: List[Dict[str, Any]] = []

        for r in results:
            fact_text = r.get("fact", "")
            candidate_sources: List[Dict[str, Any]] = []

            for key in ("source_node_uuid", "target_node_uuid"):
                node_uuid = r.get(key)
                provenance = provenance_by_uuid.get(node_uuid or "")
                if not provenance:
                    continue
                source_url = provenance.get("source_url")
                if source_url:
                    candidate_sources.append(
                        _build_source_dict(
                            source_url,
                            article_meta,
                            fallback_title=provenance.get("name"),
                        )
                    )

            # Fallback for facts that already contain explicit URLs.
            for url in _extract_urls(fact_text):
                candidate_sources.append(_build_source_dict(url, article_meta))

            sources = _dedupe_sources(candidate_sources)
            source_urls = [source["url"] for source in sources]

            formatted_nodes.append(
                {
                    "name": fact_text,
                    "source_urls": source_urls,
                    "sources": sources,
                }
            )

            line = f"- {fact_text}"
            if sources:
                line += "\n  Sources: " + "; ".join(
                    _format_source_brief(source) for source in sources
                )
            context_lines.append(line)
            all_sources.extend(sources)

        deduped_sources = _dedupe_sources(all_sources)

        return {
            "status": "success",
            "nodes": formatted_nodes,
            "context": (
                "\n".join(context_lines) if context_lines else "No results found."
            ),
            "sources": deduped_sources,
            "source_urls": [source["url"] for source in deduped_sources],
            "num_results": len(results),
            "group_id": group_id,
        }

    except Exception as e:
        logger.error(f"Graph query failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "context": f"Error querying graph: {str(e)}",
        }


async def _query_graph_natural_async(
    question: str,
    time_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """Async implementation of natural language graph query."""
    group_id = _get_group_id()
    try:
        graphiti = await _get_graphiti()

        full_query = question
        if time_filter:
            full_query = f"{question} (Time context: {time_filter})"

        # Search scoped to current session's group_id
        results = await graphiti.search_nodes(full_query, limit=10, group_id=group_id)

        node_uuids = [r.get("uuid") for r in results if r.get("uuid")]
        provenance_by_uuid = await graphiti.get_node_provenance(
            node_uuids, group_id=group_id
        )
        provenance_urls = [
            record.get("source_url")
            for record in provenance_by_uuid.values()
            if record.get("source_url")
        ]
        article_meta = _load_article_metadata(provenance_urls)

        context_lines = []
        formatted_nodes = []
        all_sources: List[Dict[str, Any]] = []
        for r in results:
            name = r.get("name", "")
            summary = r.get("summary", "")
            provenance = provenance_by_uuid.get(r.get("uuid", ""), {})
            candidate_sources: List[Dict[str, Any]] = []

            source_url = provenance.get("source_url")
            if source_url:
                candidate_sources.append(
                    _build_source_dict(
                        source_url,
                        article_meta,
                        fallback_title=name,
                    )
                )

            for url in _extract_urls(summary):
                candidate_sources.append(_build_source_dict(url, article_meta))

            sources = _dedupe_sources(candidate_sources)
            source_urls = [source["url"] for source in sources]

            if name:
                line = f"- {name}: {summary}"
                if sources:
                    line += "\n  Sources: " + "; ".join(
                        _format_source_brief(source) for source in sources
                    )
                context_lines.append(line)

            formatted_nodes.append(
                {
                    **r,
                    "source_url": source_url,
                    "source_urls": source_urls,
                    "sources": sources,
                }
            )
            all_sources.extend(sources)

        deduped_sources = _dedupe_sources(all_sources)

        return {
            "status": "success",
            "context": (
                "\n".join(context_lines) if context_lines else "No results found."
            ),
            "nodes": formatted_nodes,
            "sources": deduped_sources,
            "source_urls": [source["url"] for source in deduped_sources],
            "num_results": len(results),
            "group_id": group_id,
        }

    except Exception as e:
        logger.error(f"Natural language graph query failed: {e}")
        return {"status": "error", "error": str(e), "context": f"Error: {str(e)}"}


@tool
def query_knowledge_graph(
    query_type: Literal["time_period", "causal_chain", "search", "related"],
    query_value: str,
    limit: int = 10,
) -> Dict[str, Any]:
    """
    Query the Neo4j knowledge graph using Graphiti.

    Args:
        query_type:
            - "search": Semantic/hybrid search
            - "time_period": Search with time context (currently mapped to broad search)
            - "causal_chain": (Mapped to search for now)
            - "related": (Mapped to search for now)
        query_value: The search value or entity name
        limit: Maximum number of results

    Returns:
        Dictionary containing search results
    """
    return asyncio.run(_query_knowledge_graph_async(query_type, query_value, limit))


@tool
def query_graph_natural(
    question: str,
    time_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Query the knowledge graph using natural language.

    Args:
        question: Natural language question to search the knowledge graph
        time_filter: Optional time context filter

    Returns:
        Dictionary with search results and context
    """
    return asyncio.run(_query_graph_natural_async(question, time_filter))
