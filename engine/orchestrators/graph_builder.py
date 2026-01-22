"""Phase 1 Orchestrator: Build Knowledge Graph."""

import os
from typing import Optional

from langchain_core.language_models.chat_models import BaseChatModel
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend

from core.logging import logger
from engine.prompts.graph_builder_prompt import GRAPH_BUILDER_PROMPT
from utils.load_agents import load_agents


class GraphBuilderOrchestrator:
    """
    Phase 1 Orchestrator for building knowledge graphs.

    Workflow:
    1. Gather data from knowledge_search and financial_research
    2. Extract entities, events, relationships using LLMGraphTransformer
    3. Store in Neo4j with temporal indexing

    Example:
        >>> orchestrator = GraphBuilderOrchestrator(model)
        >>> agent = orchestrator.create()
        >>> result = agent.invoke({"messages": [{"role": "user", "content": "..."}]})
    """

    # Subagents for Phase 1
    SUBAGENT_NAMES = [
        "knowledge_search",
        "financial_research",
        "graph_extractor",
    ]

    def __init__(
        self,
        model: BaseChatModel,
        session_id: Optional[str] = None,
        output_base_path: str = "outputs",
    ):
        self.model = model
        self.session_id = session_id
        self.output_base_path = output_base_path
        self._agent = None

    def create(self):
        """Create and return the orchestrator agent."""
        subagents = load_agents(names=self.SUBAGENT_NAMES)
        logger.info(f"Graph Builder: Loaded {len(subagents)} subagent(s)")

        config = {"recursion_limit": 100}
        backend = None
        workspace_path = None

        if self.session_id:
            workspace_path = os.path.join(self.output_base_path, self.session_id)
            os.makedirs(workspace_path, exist_ok=True)
            backend = FilesystemBackend(root_dir=workspace_path, virtual_mode=True)
            config["configurable"] = {"thread_id": self.session_id}
            logger.info(f"Graph Builder workspace: {workspace_path}")

        agent = create_deep_agent(
            model=self.model,
            tools=[],
            system_prompt=GRAPH_BUILDER_PROMPT,
            subagents=subagents,
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


def create_graph_builder_orchestrator(
    model: BaseChatModel,
    session_id: Optional[str] = None,
    output_base_path: str = "outputs",
):
    """
    Factory function to create the Graph Builder orchestrator.

    Args:
        model: LangChain chat model
        session_id: Optional session ID for workspace
        output_base_path: Base path for outputs

    Returns:
        Configured orchestrator agent
    """
    orchestrator = GraphBuilderOrchestrator(
        model=model,
        session_id=session_id,
        output_base_path=output_base_path,
    )
    return orchestrator.create()
