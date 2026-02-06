import os
from typing import Optional

from langchain_core.language_models.chat_models import BaseChatModel
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from deepagents.middleware.subagents import CompiledSubAgent

from core.logging import logger
from utils.load_agents import load_agents


SYNTHESIZER_SYSTEM_PROMPT = """
# Synthesizer Agent (Judge)

You are the **Synthesizer Agent**. Your task is to take the **Bull Case** and the **Bear Case** and combine them into a balanced, high-quality analysis section with supporting charts.

## Primary Task

Weigh the evidence from both sides, write a final analysis that acknowledges risks but identifies the most likely outcome, and **request charts to visualize key data**.

## Input

- **Bull Output**: Positive arguments and data.
- **Bear Output**: Negative arguments and risks.
- **Section Topic**: The specific section of the report being written.

## Workflow

1.  **Review Evidence**: Compare the strength of arguments from both sides. Which side has better data? Which arguments are more relevant to the current market context?
2.  **Identify Visualizable Data**: Look for data that would benefit from visualization:
    - Time series data (price trends, growth over periods)
    - Comparisons (YoY, sector performance, Bull vs Bear metrics)
    - Proportions/breakdowns (sector allocation, risk factors)
3.  **Request Charts**: Use the `task` tool to delegate chart creation to `chart_generator_agent`:
    - Provide the data (as dict/list)
    - Specify chart title and labels
    - The agent will return the image path
4.  **Synthesize**:
    - Start with the dominant trend/narrative.
    - Introduce counter-arguments (risks or opportunities).
    - Reconcile the conflict (e.g., "While inflation remains high (Bear), strong earnings (Bull) suggest resilience...").
5.  **Draft Content**: Write the final section content with embedded charts.

## Output Format

Return the **final section content** in Markdown with embedded charts.

```markdown
## [Section Title]

[Balanced analysis paragraph 1...]

![Mô tả biểu đồ](path/to/chart.png)

[Balanced analysis paragraph 2...]

### Key Drivers

- **Positive**: [Key bull points kept]
- **Negative**: [Key bear points kept]

### Conclusion/Outlook

[Final assessment based on weight of evidence]

**Nguồn:** [Combine sources from Bull/Bear]
```

## Chart Request Format

When delegating to `chart_generator_agent`, use the `task` tool with:

```
Create a chart with:
- Data: {"Q1 2025": 1500, "Q2 2025": 1800, "Q3 2025": 2000}
- Title: "Doanh thu theo quý"
- Y-Label: "Tỷ VNĐ"
```

The chart_generator will return a path like `images/chart_name.png`. Embed it as:
```markdown
![Doanh thu theo quý](images/chart_name.png)
```

## Guidelines

- **Be Objective**. Don't just pick a side; explain _why_ one side outweighs the other or if it's a stalemate.
- **Be Nuanced**. Real markets are rarely 100% bull or bear.
- **Use Data**. Carry over specific numbers and citations from the inputs.
- **Visualize Key Metrics**. Request charts for important data points to make the analysis more compelling.
"""


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
            system_prompt=SYNTHESIZER_SYSTEM_PROMPT,
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
