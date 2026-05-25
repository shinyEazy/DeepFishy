import re

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage

CLASSIFIER_PROMPT = """
You are a classification assistant. Your task is to determine whether the user's research topic is about a specific company or an overall industry/macroeconomic topic.
Respond ONLY with the number '1' if it is about a specific company.
Respond ONLY with the number '2' if it is about an industry, sector, or macroeconomic topic.
Respond ONLY with the number '0' if you cannot classify or determine the type.
Do not include any other text in your response.
"""


def extract_classifier_text(content) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text" and "text" in block:
                    text_parts.append(str(block["text"]))
            elif isinstance(block, str):
                text_parts.append(block)
        return "\n".join(text_parts)

    return str(content)


def classify_topic(model: BaseChatModel, user_input: str) -> int:
    """
    Classifies the user input into:
    1: Company
    2: Industry
    0: Unknown
    """
    messages = [
        SystemMessage(content=CLASSIFIER_PROMPT),
        HumanMessage(content=user_input),
    ]
    response = model.invoke(messages)
    content = extract_classifier_text(response.content).strip()
    match = re.search(r"\b[012]\b", content)

    if not match:
        return 0

    return int(match.group(0))
