"""Parse and process LLM evaluation responses."""

import re
import json

from core.logging import logger


def parse_json_response(response_text: str) -> dict | None:
    """Extract and parse JSON from an LLM response."""
    json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", response_text, re.DOTALL)
    json_str = json_match.group(1).strip() if json_match else response_text.strip()

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {e}")
        logger.debug(f"Raw response:\n{response_text[:500]}...")
        return None


def compute_averages(evaluation: dict) -> dict:
    """Compute overall average score for each report evaluation."""
    for report_eval in evaluation.get("evaluations", []):
        scores = report_eval.get("scores", {})
        score_values = [
            dim.get("score", 0) for dim in scores.values() if isinstance(dim, dict)
        ]
        if score_values:
            report_eval["overall_average"] = round(
                sum(score_values) / len(score_values), 2
            )
    return evaluation
