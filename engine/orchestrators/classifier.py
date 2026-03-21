from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage

CLASSIFIER_PROMPT = """
You are a classification assistant. Your task is to determine whether the user's research topic is about a specific company or an overall industry/macroeconomic topic.
Respond ONLY with the number '1' if it is about a specific company.
Respond ONLY with the number '2' if it is about an industry, sector, or macroeconomic topic.
Respond ONLY with the number '0' if you cannot classify or determine the type.
Do not include any other text in your response.
"""


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
    content = str(response.content).strip()

    if content == "1":
        return 1
    elif content == "2":
        return 2
    else:
        return 0
