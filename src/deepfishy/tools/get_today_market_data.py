from typing import Literal
from langchain_core.tools import tool
from vnstock import Quote
from datetime import datetime


def get_current_date():
    try:
        return datetime.now().strftime("%Y-%m-%d")
    except Exception as exc:
        return {"error": str(exc)}


def _normalize_symbol(symbol: str) -> str:
    cleaned = (symbol or "").strip().upper()
    if not cleaned:
        raise ValueError("Symbol must be provided, e.g. 'VNM'.")
    return cleaned


@tool
def get_market_data(
    symbol: str,
):
    """Get market data for a given symbol for today."""

    symbol = _normalize_symbol(symbol)
    try:
        quote = Quote(symbol=symbol)
        today = get_current_date()
        history = quote.history(start=today, end=today, interval="1D")
    except Exception as exc:
        return {"symbol": symbol, "error": str(exc)}
    return history
