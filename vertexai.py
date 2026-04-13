import os

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv("docker/.env")


def generate() -> None:
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    model = os.environ.get("GOOGLE_MODEL", "gemini-2.5-flash")
    prompt = os.environ.get("GOOGLE_PROMPT", "hello")

    if not project:
        raise ValueError("Set GOOGLE_CLOUD_PROJECT before running this script.")

    llm = ChatGoogleGenerativeAI(
        vertexai=True,
        project=project,
        location=location,
        model=model,
        temperature=1,
        top_p=0.95,
    )

    for chunk in llm.stream([HumanMessage(content=prompt)]):
        chunk_text = getattr(chunk, "content", "")
        if isinstance(chunk_text, str) and chunk_text:
            print(chunk_text, end="", flush=True)

    print()


if __name__ == "__main__":
    generate()
