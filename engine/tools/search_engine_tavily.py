import os
from typing import Literal
from tavily import TavilyClient
from langchain_core.tools import tool
from dotenv import load_dotenv

load_dotenv()


def _get_tavily_client():
    return TavilyClient(api_key=os.environ["TAVILY_API_KEY"])


@tool
def search_engine_tavily(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
    include_raw_content: bool = False,
):
    """Run a web search using Tavily.

    Exported so other modules (including `src/main.py`) can import the search tool.
    """
    client = _get_tavily_client()
    return client.search(
        query,
        max_results=max_results,
        include_raw_content=include_raw_content,
        topic=topic,
        country="vietnam",
    )
