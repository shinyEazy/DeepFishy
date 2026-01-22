"""Engine tools module for AI agents."""

# Import tools to make them discoverable by load_agents
from engine.tools.extract_to_graph import extract_to_graph, get_graph_stats
from engine.tools.query_knowledge_graph import (
    query_knowledge_graph,
    query_graph_natural,
)

__all__ = [
    "extract_to_graph",
    "get_graph_stats",
    "query_knowledge_graph",
    "query_graph_natural",
]
