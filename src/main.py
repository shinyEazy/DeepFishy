import os
from deepagents import create_deep_agent
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from prompts.orchestrator_prompt import ORCHESTRATOR_PROMPT
from utils.serializers import save_readable_response
from utils.load_agents import load_agents

load_dotenv()


custom_model = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
# custom_model = ChatOpenAI(model="gpt-4o-mini")
subagents = load_agents(
    names=[
        "financial_research",
    ]
)

# Create the agent
agent = create_deep_agent(
    model=custom_model,
    tools=[],
    system_prompt=ORCHESTRATOR_PROMPT,
    subagents=subagents,
)

# Invoke the agent
result = agent.invoke(
    {
        "messages": [
            {
                "role": "user",
                "content": "Giá VN Index hiện tại là bao nhiêu",
            }
        ]
    }
)

output_path = os.path.join(os.getcwd(), "src/output/response.json")
save_readable_response(result, output_path)
print(f"Agent response written to: {output_path}")
