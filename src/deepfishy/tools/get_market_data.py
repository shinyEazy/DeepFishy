from typing import Literal
from langchain_core.tools import tool
from vnstock import Quote


def _normalize_symbol(symbol: str) -> str:
    cleaned = (symbol or "").strip().upper()
    if not cleaned:
        raise ValueError("Symbol must be provided, e.g. 'VNM'.")
    return cleaned


@tool
def get_market_data(
    symbol: str,
    start_date: str,
    end_date: str,
):
    """Get market data for a given symbol between start and end dates."""

    symbol = _normalize_symbol(symbol)
    try:
        quote = Quote(symbol=symbol)
        history = quote.history(start=start_date, end=end_date, interval="1D")
    except Exception as exc:
        return {"symbol": symbol, "error": str(exc)}
    return history
