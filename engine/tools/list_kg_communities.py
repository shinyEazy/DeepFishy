import asyncio
from typing import List, Dict, Optional

from langchain_core.tools import tool

from graph_rag.graphiti_service import get_graphiti_service, reset_graphiti_service
from engine.tools.search_and_build_graph import get_current_session_id


@tool
def list_kg_communities(group_id: Optional[str] = None) -> str:
    """List all communities in the knowledge graph.

    Communities are clusters of related entities automatically detected by Graphiti.
    Each community has a name, summary, and count of member entities.

    Args:
        group_id: Optional session/namespace filter. If not provided, uses the
                  current session's group_id for proper namespacing.

    Returns:
        List of community dictionaries with:
        - uuid: Unique identifier
        - name: Community name (auto-generated)
        - summary: Description of what the community represents
        - entity_count: Number of entities in the community
        - created_at: When the community was created

    Example:
        >>> communities = list_kg_communities()
        >>> for c in communities:
        ...     print(f"{c['name']}: {c['entity_count']} entities")
    """
    # Use current session_id if no explicit group_id provided
    effective_group_id = group_id if group_id is not None else get_current_session_id()

    async def _get_communities():
        service = await get_graphiti_service()
        await service.build_communities(group_id=effective_group_id)
        return await service.get_communities(group_id=effective_group_id)

    def _format_communities(raw_communities: List[Dict]) -> str:
        """Format communities into readable text for agents."""
        if not raw_communities:
            return "No communities found in knowledge graph."

        lines = [f"Found {len(raw_communities)} communities:\n"]

        for i, c in enumerate(raw_communities, 1):
            # Extract and format fields
            name = c.get("name", "Unnamed")
            summary = c.get("summary", "No summary")
            entity_count = c.get("entity_count", 0)

            lines.append(f"## Community {i}: {name}")
            lines.append(f"- Total Entities: {entity_count}")
            lines.append(f"- Summary: {summary}")
            lines.append("")

        return "\n".join(lines)

    try:
        reset_graphiti_service()
        communities = asyncio.run(_get_communities())

        if not communities:
            return "No communities found in knowledge graph."

        return _format_communities(communities)

    except Exception as e:
        return f"Failed to retrieve communities: {str(e)}"


if __name__ == "__main__":
    communities = list_kg_communities.invoke({})
    print(communities)
