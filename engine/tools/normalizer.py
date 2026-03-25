import json
import asyncio
import os
import re
import ast
import fcntl
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any, Dict, List

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage

from core.logging import logger
from utils.model_factory import create_llm_client
from utils.load_config import get_default_llm_name


def _get_staging_file_path() -> Path:
    """Get the per-session JSONL staging file path."""
    from engine.tools.search_and_build_graph import get_current_session_id

    group_id = get_current_session_id() or "default_session"
    output_dir = os.environ.get("OUTPUT_DIR", os.path.join("outputs", group_id))
    staging_dir = Path(output_dir) / "staging"
    staging_dir.mkdir(parents=True, exist_ok=True)
    return staging_dir / "facts.jsonl"


def _append_staged_record(record: Dict[str, Any]) -> None:
    """Append a single staged record as one JSONL line."""
    staging_file = _get_staging_file_path()
    with staging_file.open("a", encoding="utf-8") as f:
        # Prevent interleaved writes when multiple researcher tasks stage facts concurrently.
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def _load_staged_records() -> List[Dict[str, Any]]:
    """Load all staged records from JSONL file."""
    staging_file = _get_staging_file_path()
    if not staging_file.exists():
        return []

    records: List[Dict[str, Any]] = []
    with staging_file.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                logger.warning("Skipping malformed staged JSON line")
    return records


def _clear_staged_records() -> None:
    """Clear staging file after successful final graph ingestion."""
    staging_file = _get_staging_file_path()
    if staging_file.exists():
        staging_file.unlink()


def _split_facts_into_items(facts: str) -> List[str]:
    """Split normalized markdown/text into individual factual items."""
    text = (facts or "").replace("\r\n", "\n").strip()
    if not text:
        return []

    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    items: List[str] = []
    bullet_prefix = re.compile(r"^[-*•]\s+")
    numbered_prefix = re.compile(r"^\d+[.)]\s+")

    for line in lines:
        if bullet_prefix.match(line):
            line = bullet_prefix.sub("", line, count=1).strip()
        elif numbered_prefix.match(line):
            line = numbered_prefix.sub("", line, count=1).strip()

        if line:
            items.append(line)

    # If no bullet-like structure, treat the whole text as one fact.
    if not items:
        return [text]
    return items


def _extract_urls(text: str) -> List[str]:
    """Extract HTTP(S) URLs in order of appearance, de-duplicated."""
    if not text:
        return []
    found = re.findall(r"https?://[^\s,)]+", text)
    seen = set()
    urls: List[str] = []
    for url in found:
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


# ---------------------------------------------------------------------------
# Normalizer system prompt — defines what the cheap/fast LLM should do
# ---------------------------------------------------------------------------

_NORMALIZER_SYSTEM_PROMPT = """\
You are a financial data normalizer. You receive raw search data from various \
sources (local vector DB excerpts, web search JSON, or financial API tables) and a specific \
research query. 

Your task:
1. Read the raw data carefully.
2. Extract ONLY the factual statements that directly answer the research query.
3. Return a clean, concise bulleted list of facts. Each bullet must:
   - Be a single, complete factual sentence.
   - Include specific numbers, dates, or entities where present.
   - Include the source URL at the end, in parentheses, if available.
4. DISCARD all HTML tags, JSON syntax, irrelevant statistics, marketing text, or \
metadata that does not answer the research query.
5. If no relevant facts are found, return: "No relevant facts found."

Output in Markdown bullet format only. No preamble, no commentary.\
"""


def _get_normalizer_model():
    model = get_default_llm_name()
    if model:
        return create_llm_client(model)

    raise RuntimeError("No LLM model available for normalization.")


def _extract_text_from_model_content(content: Any) -> str:
    """Extract text from model content blocks (string or multimodal list)."""
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts: List[str] = []
        for block in content:
            if isinstance(block, dict):
                # Typical block format: {"type": "text", "text": "..."}
                if block.get("type") == "text" and "text" in block:
                    text_parts.append(str(block["text"]))
                elif "text" in block:
                    text_parts.append(str(block["text"]))
            elif isinstance(block, str):
                text_parts.append(block)

        if text_parts:
            return "\n".join(text_parts)

    return str(content)


def normalize_raw_data(raw_data: Any, query: str) -> str:
    """Pass raw API output through a fast LLM to extract clean factual bullet points.

    This is the core normalization function. It handles any serializable input:
    - Local Milvus result (dict with 'context', 'sources' keys)
    - Tavily web search result (dict with 'results' list)
    - Finance API data (DataFrame converted to string, or dict of metrics)

    Args:
        raw_data: Raw data from any search source. Will be JSON-serialized if not a string.
        query: The original research sub-query this data should answer.

    Returns:
        A clean Markdown string of bullet-point facts, or "No relevant facts found."
    """
    # Serialize raw data to string if needed
    if isinstance(raw_data, str):
        raw_str = raw_data
    else:
        try:
            raw_str = json.dumps(raw_data, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            raw_str = str(raw_data)

    # Truncate to prevent context overflow in the normalizer itself (max ~8k chars)
    if len(raw_str) > 8000:
        raw_str = raw_str[:8000] + "\n...[truncated]"

    try:
        model = _get_normalizer_model()
        messages = [
            SystemMessage(content=_NORMALIZER_SYSTEM_PROMPT),
            HumanMessage(content=f"Research query: {query}\n\nRaw data:\n\n{raw_str}"),
        ]
        response = model.invoke(messages)
        normalized = _extract_text_from_model_content(response.content).strip()
        logger.debug(f"Normalized {len(raw_str)} chars → {len(normalized)} chars")
        return normalized

    except Exception as e:
        logger.error(f"Normalization failed: {e}", exc_info=True)
        # Fallback: return a truncated version of the raw data with a warning
        return f"[Normalization failed: {e}]\n\nRaw excerpt:\n{raw_str[:1000]}"


# ---------------------------------------------------------------------------
# Normalized search tools — wrap existing search APIs with the normalizer
# ---------------------------------------------------------------------------


@tool
def search_local_normalized(
    query: str,
    top_k: int = 5,
    category: Optional[str] = None,
) -> str:
    """Search local Milvus knowledge base and return clean, normalized facts.

    Unlike the raw search tool, this returns pre-processed Markdown bullet points
    directly answering the query — no JSON parsing needed.

    Args:
        query: The specific research sub-query to search for (Query must be in Vietnamese).
        top_k: Number of vector results to retrieve (1-10, default 5).
        category: Optional category filter (e.g. 'tài chính', 'chứng khoán').

    Returns:
        A Markdown bulleted list of relevant facts extracted from the local knowledge
        base, or "No relevant facts found." if no data matched.
    """
    try:
        from services.rag import get_rag_service

        rag_service = get_rag_service()
        top_k = max(1, min(top_k, 10))
        vi_query = (query or "").strip()

        raw_result = rag_service.search_with_context(
            query=vi_query,
            top_k=top_k,
            category=category,
            include_metadata=True,
        )

        logger.info(
            f"Local search: '{vi_query}' → {raw_result.get('num_results', 0)} results, normalizing..."
        )
        normalized = normalize_raw_data(raw_result, vi_query)
        return normalized

    except Exception as e:
        logger.error(f"search_local_normalized failed: {e}", exc_info=True)
        return f"Error searching local knowledge base: {e}"


@tool
def search_web_normalized(
    query: str,
    max_results: int = 5,
) -> str:
    """Search the web via Tavily and return clean, normalized facts.

    Unlike the raw Tavily tool, this strips away JSON structure, irrelevant snippets,
    and HTML artifacts, returning only factual bullet points relevant to the query.

    Args:
        query: The specific research sub-query to search for on the web (Query must be in Vietnamese).
        max_results: Number of web results to fetch (1-5, default 5).

    Returns:
        A Markdown bulleted list of relevant facts from the web, or
        "No relevant facts found." if results were off-topic.
    """
    try:
        import os
        from tavily import TavilyClient
        from dotenv import load_dotenv

        load_dotenv()
        client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
        max_results = max(1, min(max_results, 5))
        vi_query = (query or "").strip()

        raw_result = client.search(
            vi_query,
            max_results=max_results,
            country="vietnam",
        )

        logger.info(
            f"Web search: '{vi_query}' → {len(raw_result.get('results', []))} results, normalizing..."
        )
        normalized = normalize_raw_data(raw_result, vi_query)
        return normalized

    except Exception as e:
        logger.error(f"search_web_normalized failed: {e}", exc_info=True)
        return f"Error searching the web: {e}"


@tool
def get_finance_data_normalized(
    symbol: str,
    start_date: str,
    end_date: str,
) -> str:
    """Fetch structured market/financial data from the vnstock Finance API and return clean facts.

    Unlike raw API calls, this returns pre-processed Markdown bullet points
    summarizing the quantitative data that is relevant to the query.

    Args:
        symbol: Stock ticker symbol, e.g. "MBB", "VNM", "HPG".
        start_date: Start of the date range in YYYY-MM-DD format.
        end_date: End of the date range in YYYY-MM-DD format.

    Returns:
        A Markdown bulleted list of relevant financial facts extracted from the API,
        or an error message if the API call fails.
    """
    try:
        from vnstock import Quote

        symbol = (symbol or "").strip().upper()
        if not symbol:
            return "Error: symbol must be provided, e.g. 'MBB'."

        logger.info(f"Finance API: fetching {symbol} from {start_date} to {end_date}")
        quote = Quote(symbol=symbol)
        history = quote.history(start=start_date, end=end_date, interval="1D")

        # Convert DataFrame/dict to a string the normalizer can handle
        if hasattr(history, "to_markdown"):
            try:
                raw_str = history.to_markdown()
            except ImportError:
                raw_str = history.to_string()
        elif hasattr(history, "to_string"):
            raw_str = history.to_string()
        else:
            raw_str = str(history)

        logger.info(f"Finance API: normalizing {symbol} table data...")
        normalized = normalize_raw_data(
            raw_str, f"Financial data for {symbol} from {start_date} to {end_date}"
        )
        return normalized

    except Exception as e:
        logger.error(f"get_finance_data_normalized failed: {e}", exc_info=True)
        return f"Error fetching finance data for {symbol}: {e}"


@tool
def commit_facts_to_graph(
    facts: str,
    source_urls: str = "normalized://researcher",
    section_id: str = "unknown_section",
) -> Dict[str, Any]:
    """Stage a clean set of facts for later bulk graph ingestion.

    This tool stores normalized facts in temporary per-session staging storage.
    Graph ingestion will be done once at the end of build phase by
    finalize_staged_facts_to_graph() for better performance.

    After gathering facts using search tools and evaluating their sufficiency,
    the researcher agent calls this tool exactly once per sub-query to
    stage findings for batch graph commit.

    Args:
        facts: Clean Markdown bullet points summarizing the research findings.
               Example: "- MBBank Q3 2025 net profit was 9,800 billion VND (+12% YoY)"
        source_urls: Comma-separated string of the actual source URLs from the facts,
                     e.g. "https://vneconomy.vn/mb-...,https://vnfinance.vn/mbb-..."

    Returns:
        Dictionary with staging status and counts.
    """
    if isinstance(facts, str):
        candidate = facts.strip()
        if candidate.startswith("{") and "facts" in candidate:
            payload = None
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError:
                try:
                    payload = ast.literal_eval(candidate)
                except (SyntaxError, ValueError):
                    payload = None

            if isinstance(payload, dict):
                facts = str(payload.get("facts", facts))
                source_urls = str(payload.get("source_urls", source_urls))
                section_id = str(payload.get("section_id", section_id))

    if not facts or facts.strip() == "No relevant facts found.":
        return {
            "status": "skipped",
            "staged_records": 0,
            "message": "No facts to stage.",
        }

    try:
        from engine.tools.search_and_build_graph import get_current_session_id

        group_id = get_current_session_id()
        source_url_list = [u.strip() for u in source_urls.split(",") if u.strip()]
        fact_items = _split_facts_into_items(facts)
        if not fact_items:
            return {
                "status": "skipped",
                "staged_records": 0,
                "message": "No parseable facts to stage.",
            }

        now_ts = int(datetime.now(timezone.utc).timestamp())
        staged_count = 0

        for fact in fact_items:
            fact_urls = _extract_urls(fact)
            merged_urls: List[str] = []
            for u in fact_urls + source_url_list:
                if u and u not in merged_urls:
                    merged_urls.append(u)

            primary_url = (
                fact_urls[0]
                if fact_urls
                else (
                    source_url_list[0] if source_url_list else "normalized://researcher"
                )
            )

            _append_staged_record(
                {
                    "group_id": group_id,
                    "section_id": section_id,
                    "facts": fact,
                    "source_urls": merged_urls,
                    "primary_url": primary_url,
                    "date_ts": now_ts,
                    "category": "normalized_research",
                    "score": 1.0,
                }
            )
            staged_count += 1

        logger.info(
            f"commit_facts_to_graph: staged {staged_count} facts for section={section_id} (group={group_id})"
        )
        return {
            "status": "staged",
            "staged_records": staged_count,
            "group_id": group_id,
            "section_id": section_id,
            "source_urls": source_urls,
            "facts_length": len(facts),
        }

    except Exception as e:
        logger.error(f"commit_facts_to_graph failed: {e}", exc_info=True)
        return {
            "status": "error",
            "staged_records": 0,
            "error": str(e),
        }


def finalize_staged_facts_to_graph() -> Dict[str, Any]:
    """Ingest all staged facts for the current session in one bulk Graphiti call."""
    try:
        from engine.tools.search_and_build_graph import get_current_session_id
        from services.rag import SearchResult
        from graph_rag.graphiti_service import (
            get_graphiti_service,
            reset_graphiti_service,
        )

        group_id = get_current_session_id()
        staged = _load_staged_records()
        if not staged:
            return {
                "status": "skipped",
                "episodes_created": 0,
                "staged_records": 0,
                "message": "No staged facts found.",
            }

        deduped: List[Dict[str, Any]] = []
        seen = set()
        for rec in staged:
            key = (rec.get("primary_url", ""), rec.get("facts", ""))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(rec)

        results: List[SearchResult] = []
        for idx, rec in enumerate(deduped):
            results.append(
                SearchResult(
                    content=rec.get("facts", ""),
                    url=rec.get("primary_url", "normalized://researcher"),
                    chunk_index=idx,
                    category=rec.get("category", "normalized_research"),
                    tags=rec.get("source_urls", [])[:5],
                    date_ts=int(
                        rec.get("date_ts", int(datetime.now(timezone.utc).timestamp()))
                    ),
                    score=float(rec.get("score", 1.0)),
                )
            )

        async def _ingest():
            service = await get_graphiti_service()
            return await service.add_search_results(
                results=results,
                source_query="staged_batch_research",
                group_id=group_id,
            )

        reset_graphiti_service()
        episodes_created = asyncio.run(_ingest())

        if deduped and episodes_created <= 0:
            logger.error(
                "finalize_staged_facts_to_graph: graph ingest returned 0 episodes from non-empty staged data; preserving staging file for retry"
            )
            return {
                "status": "error",
                "episodes_created": episodes_created,
                "staged_records": len(staged),
                "deduped_records": len(deduped),
                "group_id": group_id,
                "message": "Graph ingest failed; staged facts were preserved for retry.",
            }

        _clear_staged_records()

        logger.info(
            f"finalize_staged_facts_to_graph: ingested {episodes_created} episodes from {len(deduped)} staged records (group={group_id})"
        )
        return {
            "status": "success",
            "episodes_created": episodes_created,
            "staged_records": len(staged),
            "deduped_records": len(deduped),
            "group_id": group_id,
        }

    except Exception as e:
        logger.error(f"finalize_staged_facts_to_graph failed: {e}", exc_info=True)
        return {
            "status": "error",
            "episodes_created": 0,
            "error": str(e),
        }


if __name__ == "__main__":
    result = get_finance_data_normalized.invoke(
        {"symbol": "MBB", "start_date": "2023-01-01", "end_date": "2023-12-31"}
    )
    print(result)
