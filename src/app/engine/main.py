import os
from typing import Optional
from datetime import datetime
from deepagents import create_deep_agent
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel

from app.engine.prompts.orchestrator_prompt import ORCHESTRATOR_PROMPT
from app.utils.load_agents import load_agents
from app.engine.tools.get_current_date import get_current_date
from app.utils.load_agents import load_agents
from app.utils.convert_md_to_pdf import convert_md_to_pdf
from app.core.logging import logger
from app.engine.backends import DiskBackend

from prompts.orchestrator_prompt import ORCHESTRATOR_PROMPT

from tools.get_current_date import get_current_date


load_dotenv()

MODEL_PROVIDER = os.getenv("MODEL_PROVIDER")
ENABLE_DISK_BACKEND = os.getenv("ENABLE_DISK_BACKEND", "true").lower() == "true"
AGENT_WORKSPACE_PATH = os.getenv("AGENT_WORKSPACE_PATH", "agent_workspace")


def _create_model() -> Optional[BaseChatModel]:
    """
    Lazy model initialization to avoid credential errors during import.
    Checks for model provider before attempting to initialize models.
    """

    if MODEL_PROVIDER == "google":
        google_api_key = os.getenv("GOOGLE_API_KEY")
        try:
            logger.info("Initializing Gemini model")
            return ChatGoogleGenerativeAI(
                model="gemini-2.5-flash", google_api_key=google_api_key
            )
        except Exception as e:
            logger.warning(f"Failed to initialize Gemini model: {e}")

    elif MODEL_PROVIDER == "openai":
        openai_api_key = os.getenv("OPENAI_API_KEY")
        try:
            logger.info("Initializing OpenAI model")
            return ChatOpenAI(model="gpt-4o-mini", api_key=openai_api_key)
        except Exception as e:
            logger.warning(f"Failed to initialize OpenAI model: {e}")

    else:
        logger.warning(
            "No valid model provider found. Agent will be created without a model."
        )
        logger.warning(
            "Please set MODEL_PROVIDER in your .env file to 'google' or 'openai'"
        )
        return None


def _create_agent():
    """Factory function to create the agent with lazy initialization."""
    custom_model = _create_model()

    subagents = load_agents(
        names=[
            "market_data",
            "knowledge_search",
            "financial_research",
            "financial_report_writer",
        ]
    )

    logger.info(f"Loaded {len(subagents)} subagent(s)")

    # Configure disk backend for persistent tracking
    config = {"recursion_limit": 100}

    if ENABLE_DISK_BACKEND:
        # Generate session ID for this run
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        backend = DiskBackend(base_path=AGENT_WORKSPACE_PATH, thread_id=session_id)

        logger.info(f"Agent workspace: {backend.workspace_path}")
        logger.info("Agent todos and context will be saved to disk")

        # Add configurable_fields for the agent to use custom backend
        config["configurable"] = {"thread_id": session_id, "checkpoint_ns": session_id}

    # Create the agent
    agent = create_deep_agent(
        model=custom_model,
        tools=[],
        system_prompt=ORCHESTRATOR_PROMPT,
        subagents=subagents,
    ).with_config(config)

    # Store backend reference for later use
    if ENABLE_DISK_BACKEND:
        agent._disk_backend = backend

    return agent


agent = _create_agent()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input", type=str, default="Tạo báo cáo tài chính toàn diện về VNINDEX với phân tích xu hướng và biểu đồ 6 tháng gần đây"
    )
    parser.add_argument(
        "--show-workspace",
        action="store_true",
        help="Show agent workspace summary after execution",
    )
    args = parser.parse_args()
    user_input = args.input

    result = agent.invoke({"messages": [{"role": "user", "content": user_input}]})

    final_response = result["messages"][-1].content
    print(final_response)

    # Create results directory if it doesn't exist
    results_dir = "results"
    os.makedirs(results_dir, exist_ok=True)

    # Generate timestamp-based filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_filename = f"{timestamp}.pdf"
    pdf_path = os.path.join(results_dir, pdf_filename)

    # Convert markdown response to PDF
    try:
        convert_md_to_pdf(final_response, pdf_path)
        logger.info(f"PDF report saved to: {pdf_path}")
    except Exception as e:
        logger.error(f"Failed to generate PDF: {e}")

    # Show workspace summary if enabled
    if ENABLE_DISK_BACKEND and hasattr(agent, "_disk_backend"):
        backend = agent._disk_backend

        # Save final response to context
        try:
            backend.write_file("context/final_response.md", final_response)
            backend.write_file("context/user_query.txt", user_input)
            logger.info(f"Agent context saved to: {backend.workspace_path}")
        except Exception as e:
            logger.warning(f"Could not save context: {e}")

        if args.show_workspace:
            summary = backend.get_workspace_summary()
            print("\n" + "=" * 60)
            print("AGENT WORKSPACE SUMMARY")
            print("=" * 60)
            print(f"Location: {summary['workspace_path']}")
            print(f"Session ID: {summary['thread_id']}")
            print(f"Total files: {summary['total_files']}")
            print(
                f"\nTodos: {', '.join(summary['todos']) if summary['todos'] else 'None'}"
            )
            print(
                f"Context files: {', '.join(summary['context_files']) if summary['context_files'] else 'None'}"
            )
            print(
                f"Memory files: {', '.join(summary['memory_files']) if summary['memory_files'] else 'None'}"
            )
            print("=" * 60)
