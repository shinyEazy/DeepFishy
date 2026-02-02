"""Builder Orchestrator: Iterative knowledge graph building pipeline.

This orchestrator implements the iterative research loop:
1. Generate search queries for user topic
2. Search Milvus → get chunks (deduplicated)
3. Add chunks to Graphiti graph
4. Cluster topics via LLM
5. Evaluate coverage via gap_analyzer
6. If insufficient, repeat from step 1
7. When sufficient, hand off to report_outline
"""

import os
import json
import asyncio
from typing import Optional, List, Dict, Any

from langchain_core.language_models.chat_models import BaseChatModel
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend

from core.logging import logger
from engine.prompts.builder_orchestrator_prompt import BUILDER_ORCHESTRATOR_PROMPT
from utils.load_agents import load_agents
from graph_rag.graphiti_service import GraphitiService, get_graphiti_service
from graph_rag.chunk_tracker import ChunkTracker
from services.rag import RAGService, get_rag_service


from engine.tools.topic_clustering import (
    cluster_topics_from_graph,
    get_graph_summary,
    search_graph_for_facts,
)
from engine.tools.search_local_knowledge import search_local_knowledge
from engine.tools.search_and_build_graph import (
    search_and_build_graph,
    get_pending_graph_updates,
    clear_pending_graph_updates,
)


class BuilderOrchestrator:
    """
    Iterative Builder Orchestrator for building comprehensive knowledge graphs.

    This orchestrator handles the research phase before report writing:
    - Generates diverse search queries to explore a topic
    - Searches Milvus and deduplicates results across iterations
    - Builds a temporal knowledge graph using Graphiti
    - Clusters topics and evaluates coverage
    - Iterates until coverage is sufficient or max iterations reached

    After research is complete, it creates a report outline and can
    hand off to the ReportWriterOrchestrator.

    Example:
        >>> orchestrator = BuilderOrchestrator(model)
        >>> agent = orchestrator.create()
        >>> result = agent.invoke({
        ...     "messages": [{"role": "user", "content": "Phân tích tác động thuế quan Trump"}]
        ... })
    """

    # Pipeline configuration
    MAX_ITERATIONS = 5
    CHUNKS_PER_QUERY = 5
    COVERAGE_THRESHOLD = 0.8

    # Subagents for research phase
    SUBAGENT_NAMES = [
        "query_generator",  # Generates search queries
        "gap_analyzer",  # Evaluates coverage
        "report_outline",  # Creates outline when ready
        "knowledge_search",  # Searches Milvus (existing)
    ]

    def __init__(
        self,
        model: BaseChatModel,
        session_id: Optional[str] = None,
        output_base_path: str = "outputs",
        rag_service: Optional[RAGService] = None,
        graphiti_service: Optional[GraphitiService] = None,
    ):
        """
        Initialize BuilderOrchestrator.

        Args:
            model: LangChain chat model for the orchestrator
            session_id: Optional session ID for workspace persistence
            output_base_path: Base path for output files
            rag_service: Optional RAGService instance (created if not provided)
            graphiti_service: Optional GraphitiService instance (created if not provided)
        """
        self.model = model
        self.session_id = session_id
        self.output_base_path = output_base_path
        self._rag_service = rag_service
        self._graphiti_service = graphiti_service
        self._agent = None

        # Tracking state
        self.chunk_tracker = ChunkTracker()
        self.current_iteration = 0
        self.topics: List[Dict] = []

    async def _ensure_services(self) -> None:
        """Lazy initialization of services."""
        if self._rag_service is None:
            self._rag_service = get_rag_service()

        if self._graphiti_service is None:
            self._graphiti_service = await get_graphiti_service()

    def create(self):
        """Create and return the orchestrator agent."""
        subagents = load_agents(names=self.SUBAGENT_NAMES)
        logger.info(f"Builder: Loaded {len(subagents)} subagent(s)")

        config = {"recursion_limit": 150}
        backend = None
        workspace_path = None

        if self.session_id:
            workspace_path = os.path.join(self.output_base_path, self.session_id)
            os.makedirs(workspace_path, exist_ok=True)
            backend = FilesystemBackend(root_dir=workspace_path, virtual_mode=True)
            config["configurable"] = {"thread_id": self.session_id}
            logger.info(f"Builder workspace: {workspace_path}")

        tools = [
            # cluster_topics_from_graph,
            # get_graph_summary,
            # search_graph_for_facts,
            # search_local_knowledge,
            search_and_build_graph
        ]

        agent = create_deep_agent(
            model=self.model,
            tools=tools,
            system_prompt=BUILDER_ORCHESTRATOR_PROMPT,
            # subagents=subagents,
            backend=backend,
        ).with_config(config)

        if workspace_path:
            agent._workspace_path = workspace_path
            agent._session_id = self.session_id

        self._agent = agent
        return agent

    @property
    def agent(self):
        """Get or create the agent."""
        if self._agent is None:
            self.create()
        return self._agent

    async def reset_session(self) -> None:
        """Reset the research session for a new query.

        Note: Unlike before, we no longer clear the graph. Each session uses
        group_id (session_id) for namespacing, preserving historical data.
        """
        await self._ensure_services()

        # Reset tracking state (no longer clearing graph - using group_id namespacing)
        self.chunk_tracker.reset()
        self.current_iteration = 0
        self.topics = []

        # Clear any pending graph updates from previous session
        clear_pending_graph_updates()

        logger.info(
            f"Research session reset for new query (group_id={self.session_id})"
        )

    async def process_pending_graph_updates(self) -> int:
        """
        Process pending graph updates from sync tool invocations.

        This should be called after each agent invocation to process
        any search results that were queued by the sync search_and_build_graph tool.
        The sync tool cannot add to the graph directly due to event loop conflicts.

        Returns:
            Total number of results added to the graph
        """
        await self._ensure_services()

        updates = get_pending_graph_updates()
        if not updates:
            return 0

        total_added = 0
        for update in updates:
            results = update.get("results", [])
            query = update.get("query", "research")

            # Filter new results and add to graph with session namespace
            new_results = self.chunk_tracker.filter_new(results)
            if new_results:
                added = await self._graphiti_service.add_search_results(
                    results=new_results,
                    source_query=query,
                    group_id=self.session_id,  # Use session_id as namespace
                )
                total_added += added

        if total_added > 0:
            logger.info(
                f"Processed {len(updates)} pending updates, added {total_added} to graph (group_id={self.session_id})"
            )

        return total_added

    async def search_and_add_to_graph(
        self,
        queries: List[str],
    ) -> Dict[str, Any]:
        """
        Execute search queries and add results to graph.

        This method:
        1. Searches Milvus for each query
        2. Deduplicates results across all iterations
        3. Adds new chunks to the Graphiti graph

        Args:
            queries: List of search queries to execute

        Returns:
            Dictionary with search statistics
        """
        await self._ensure_services()

        all_results = []
        for query in queries:
            results = self._rag_service.search(
                query=query,
                top_k=self.CHUNKS_PER_QUERY,
            )
            all_results.extend(results)
            logger.debug(f"Query '{query[:50]}...' returned {len(results)} results")

        # Deduplicate
        new_results = self.chunk_tracker.filter_new(all_results)

        # Add to graph
        added = 0
        if new_results:
            added = await self._graphiti_service.add_search_results(
                results=new_results,
                source_query=queries[0] if queries else "research",
            )

        stats = {
            "queries_executed": len(queries),
            "total_results": len(all_results),
            "new_chunks": len(new_results),
            "added_to_graph": added,
            "total_processed": self.chunk_tracker.count(),
            "iteration": self.current_iteration,
        }

        logger.info(
            f"Iteration {self.current_iteration}: Added {added} new chunks to graph"
        )
        return stats

    async def get_research_state(self) -> Dict[str, Any]:
        """Get the current state of the research session."""
        await self._ensure_services()

        graph_stats = await self._graphiti_service.get_graph_stats()

        return {
            "iteration": self.current_iteration,
            "max_iterations": self.MAX_ITERATIONS,
            "chunks_processed": self.chunk_tracker.count(),
            "unique_urls": len(self.chunk_tracker.get_processed_urls()),
            "graph": graph_stats,
            "topics": self.topics,
            "can_continue": self.current_iteration < self.MAX_ITERATIONS,
        }


def create_builder_orchestrator(
    model: BaseChatModel,
    session_id: Optional[str] = None,
    output_base_path: str = "outputs",
) -> BuilderOrchestrator:
    """
    Factory function to create a Builder Orchestrator.

    Args:
        model: LangChain chat model
        session_id: Optional session ID for workspace
        output_base_path: Base path for outputs

    Returns:
        Configured BuilderOrchestrator instance
    """
    orchestrator = BuilderOrchestrator(
        model=model,
        session_id=session_id,
        output_base_path=output_base_path,
    )
    return orchestrator
