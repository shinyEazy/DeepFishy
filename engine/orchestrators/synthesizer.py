import os
from typing import Optional
from datetime import datetime

from langchain_core.language_models.chat_models import BaseChatModel
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from deepagents.middleware.subagents import CompiledSubAgent

from deepfishy.shared.logging import logger
from deepfishy.shared.agents import load_agents
from engine.prompts.synthesizer_orchestrator_prompt import (
    SYNTHESIZER_ORCHESTRATOR_SYSTEM_PROMPT,
)


class SynthesizerOrchestrator:
    """
    Nested orchestrator for synthesizing Bull/Bear cases with chart generation.

    This orchestrator is designed to be used as a CompiledSubAgent by WriterOrchestrator.
    It has chart_generator as its subagent for creating visualizations.
    """

    SUBAGENT_NAMES = ["chart_generator"]

    def __init__(
        self,
        model: BaseChatModel,
        session_id: Optional[str] = None,
        output_base_path: str = "outputs",
    ):
        self.model = model
        self.session_id = session_id
        self.output_base_path = output_base_path

    def create(self) -> CompiledSubAgent:
        """Create and return the synthesizer as a CompiledSubAgent.

        Returns:
            CompiledSubAgent that can be passed to another orchestrator's subagents list.
        """
        subagents = load_agents(names=self.SUBAGENT_NAMES)
        logger.info(
            f"Synthesizer: Loaded {len(subagents)} subagent(s): {[s['name'] for s in subagents]}"
        )

        config = {"recursion_limit": 100}
        backend = None

        if self.session_id:
            workspace_path = os.path.join(self.output_base_path, self.session_id)
            os.makedirs(os.path.join(workspace_path, "images"), exist_ok=True)
            backend = FilesystemBackend(root_dir=workspace_path, virtual_mode=True)
            config["configurable"] = {"thread_id": f"{self.session_id}_synth"}
            logger.info(f"Synthesizer workspace: {workspace_path}")

        agent = create_deep_agent(
            model=self.model,
            tools=[],
            system_prompt=SYNTHESIZER_ORCHESTRATOR_SYSTEM_PROMPT.format(
                current_date=datetime.now().strftime("%Y-%m-%d")
            ),
            subagents=subagents,
            backend=backend,
        ).with_config(config)

        return CompiledSubAgent(
            name="synthesizer_agent",
            description="Synthesizes bull and bear cases into a balanced analysis with data visualizations. Use this after bull_agent and bear_agent have written their findings.",
            runnable=agent,
        )


def create_synthesizer_orchestrator(
    model: BaseChatModel,
    session_id: Optional[str] = None,
    output_base_path: str = "outputs",
) -> CompiledSubAgent:
    """
    Factory function to create the Synthesizer orchestrator as a CompiledSubAgent.

    Args:
        model: LangChain chat model
        session_id: Optional session ID for workspace
        output_base_path: Base path for outputs

    Returns:
        CompiledSubAgent ready to be added to another orchestrator's subagents
    """
    orchestrator = SynthesizerOrchestrator(
        model=model,
        session_id=session_id,
        output_base_path=output_base_path,
    )
    return orchestrator.create()
