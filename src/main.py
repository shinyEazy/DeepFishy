import os
import json
import base64
import datetime
from typing import Any, Literal
from tavily import TavilyClient
from deepagents import create_deep_agent
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
import os
import re
import yaml
from prompts.orchestrator_prompt import ORCHESTRATOR_PROMPT
from utils.serializers import save_readable_response
from tools.search_engine_tavily import search_engine_tavily
from utils.load_agents import load_agents

load_dotenv()


custom_model = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
subagents = load_agents(names=["research", "critique"])

# Create the agent
agent = create_deep_agent(
    tools=[search_engine_tavily],
    instructions=ORCHESTRATOR_PROMPT,
    model=custom_model,
    subagents=subagents,
).with_config({"recursion_limit": 10})

# Invoke the agent
result = agent.invoke(
    {
        "messages": [
            {
                "role": "user",
                "content": "write a summary about 200 letter about Viet Nam",
            }
        ]
    }
)

output_path = os.path.join(os.getcwd(), "src/output/response.json")
save_readable_response(result, output_path)
print(f"Agent response written to: {output_path}")
