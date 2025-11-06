from langchain_core.tools import tool
from datetime import datetime


@tool
def get_current_date():
    """Get current date."""

    try:
        return datetime.now().strftime("%Y-%m-%d")
    except Exception as exc:
        return {"error": str(exc)}
