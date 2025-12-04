import os
from deepagents import create_deep_agent
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from prompts.orchestrator_prompt import ORCHESTRATOR_PROMPT
from app.utils.load_agents import load_agents
from tools.get_current_date import get_current_date

load_dotenv()


custom_model = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
# custom_model = ChatOpenAI(model="gpt-5-nano")

subagents = load_agents(
    names=[
        "market_data",
    ]
)

print("Loaded", len(subagents), "subagents")

# Create the agent
agent = create_deep_agent(
    model=custom_model,
    tools=[],
    system_prompt=ORCHESTRATOR_PROMPT,
    subagents=subagents,
)
