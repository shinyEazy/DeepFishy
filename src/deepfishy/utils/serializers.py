import json
import base64
import datetime
from typing import Any


def make_serializable(obj: Any) -> Any:
    """Recursively convert objects into JSON-serializable structures.

    - dict-like objects are converted recursively
    - lists/tuples/sets are converted to lists
    - objects with `dict()` or `json()` are attempted first
    - datetimes are converted to ISO strings
    - bytes are base64-encoded
    - otherwise fallback to str(obj)
    """
    # Primitives
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj

    # Datetime
    if isinstance(obj, (datetime.datetime, datetime.date, datetime.time)):
        try:
            return obj.isoformat()
        except Exception:
            return str(obj)

    # Bytes
    if isinstance(obj, (bytes, bytearray)):
        try:
            return obj.decode("utf-8")
        except Exception:
            return base64.b64encode(bytes(obj)).decode("ascii")

    # Mapping / dict-like
    if isinstance(obj, dict):
        new = {}
        for k, v in obj.items():
            # make sure keys are strings
            key = k if isinstance(k, str) else str(k)
            new[key] = make_serializable(v)
        return new

    # Iterable (list/tuple/set)
    if isinstance(obj, (list, tuple, set)):
        return [make_serializable(v) for v in obj]

    # Objects with dict() method (pydantic, dataclasses, langchain models)
    try:
        if hasattr(obj, "dict") and callable(getattr(obj, "dict")):
            return make_serializable(obj.dict())
    except Exception:
        pass

    # Objects with __dict__
    if hasattr(obj, "__dict__"):
        try:
            return make_serializable(vars(obj))
        except Exception:
            pass

    # Objects with json() method
    try:
        if hasattr(obj, "json") and callable(getattr(obj, "json")):
            text = obj.json()
            try:
                return json.loads(text)
            except Exception:
                return text
    except Exception:
        pass

    # Fallback to string
    try:
        return str(obj)
    except Exception:
        return repr(obj)


def save_readable_response(response: Any, path: str = "response.json") -> None:
    """Process the agent response and write a pretty JSON file.

    The function will try to reduce complex objects into simple JSON-compatible
    structures so the output is human readable.
    """
    processed = make_serializable(response)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(processed, f, ensure_ascii=False, indent=2)
