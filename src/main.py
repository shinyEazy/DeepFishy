import os
import json
import base64
import datetime
from typing import Any, Literal
from tavily import TavilyClient
from deepagents import create_deep_agent
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
import os
import re
import yaml
from prompts.orchestrator_prompt import ORCHESTRATOR_PROMPT
from utils.serializers import save_readable_response
from tools.search_engine_tavily import search_engine_tavily
from utils.load_agents import load_agents

load_dotenv()


custom_model = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
# custom_model = ChatOpenAI(model="gpt-4o-mini")
subagents = load_agents(
    names=[
        "financial_research",
        "data_analysis",
        "fact_verification",
        "strategic_advisor",
        "report_writer",
    ]
)

# Create the agent
agent = create_deep_agent(
    tools=[search_engine_tavily],
    instructions=ORCHESTRATOR_PROMPT,
    model=custom_model,
    subagents=subagents,
).with_config({"recursion_limit": 100})

# Invoke the agent
result = agent.invoke(
    {
        "messages": [
            {
                "role": "user",
                "content": "Đánh giá triển vọng ngành bất động sản Việt Nam năm 2025, bao gồm tác động của chính sách tiền tệ, lãi suất và xu hướng thị trường",
            }
        ]
    }
)

output_path = os.path.join(os.getcwd(), "src/output/response.json")
save_readable_response(result, output_path)
print(f"Agent response written to: {output_path}")
