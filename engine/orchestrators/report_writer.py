"""Phase 2 Orchestrator: Write Reports with Knowledge Graph Context."""

import os
from typing import Optional

from langchain_core.language_models.chat_models import BaseChatModel
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend

from core.logging import logger
from engine.prompts.write_phase_prompt import WRITE_PHASE_PROMPT
from utils.load_agents import load_agents


class ReportWriterOrchestrator:
    """
    Phase 2 Orchestrator for writing reports with knowledge graph context.

    Workflow:
    1. Gather data from market_data, knowledge_search, financial_research
    2. Query knowledge graph for enhanced context
    3. Create structured report outline
    4. Write sections:
       - Informational: Direct writing
       - Analysis: Bull/Bear debate -> Synthesis
    5. Fill in report content with charts

    Example:
        >>> orchestrator = ReportWriterOrchestrator(model)
        >>> agent = orchestrator.create()
        >>> result = agent.invoke({"messages": [{"role": "user", "content": "..."}]})
    """

    # Subagents for Phase 2
    SUBAGENT_NAMES = [
        "bull_agent",
        "bear_agent",
        "synthesizer_agent",
        # "critique",
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
        logger.info(f"Report Writer: Loaded {len(subagents)} subagent(s)")

        config = {"recursion_limit": 250}
        backend = None
        workspace_path = None

        if self.session_id:
            workspace_path = os.path.join(self.output_base_path, self.session_id)

            # Create standard directory structure
            os.makedirs(os.path.join(workspace_path, "images"), exist_ok=True)

            backend = FilesystemBackend(root_dir=workspace_path, virtual_mode=True)
            config["configurable"] = {"thread_id": self.session_id}
            logger.info(f"Report Writer workspace: {workspace_path}")

        agent = create_deep_agent(
            model=self.model,
            tools=[],
            system_prompt=WRITE_PHASE_PROMPT,
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


def create_report_writer_orchestrator(
    model: BaseChatModel,
    session_id: Optional[str] = None,
    output_base_path: str = "outputs",
):
    """
    Factory function to create the Report Writer orchestrator.

    Args:
        model: LangChain chat model
        session_id: Optional session ID for workspace
        output_base_path: Base path for outputs

    Returns:
        Configured orchestrator agent
    """
    orchestrator = ReportWriterOrchestrator(
        model=model,
        session_id=session_id,
        output_base_path=output_base_path,
    )
    return orchestrator.create()
