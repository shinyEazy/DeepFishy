import os
import base64
from typing import Optional

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage

from utils.model_factory import create_vlm_client
from utils.load_config import get_default_vlm_name
from engine.tools.prompts.critique_chart_prompt import (
    CRITIQUE_CHART_SYSTEM_PROMPT,
)


def _encode_image_to_base64(image_path: str) -> str:
    """Encode an image file to base64 string."""
    with open(image_path, "rb") as image_file:
        return base64.standard_b64encode(image_file.read()).decode("utf-8")


def _get_image_media_type(image_path: str) -> str:
    """Get the media type based on file extension."""
    ext = os.path.splitext(image_path)[1].lower()
    media_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    return media_types.get(ext, "image/png")


@tool
def critique_chart(
    image_path: str,
    context: Optional[str] = None,
) -> str:
    """
    Analyze a chart image and provide structured feedback for improvement.

    This tool uses a vision-capable LLM to evaluate chart quality and provide
    actionable suggestions for improvement.

    Args:
        image_path: Path to the chart image file (PNG, JPG, etc.)
        context: Optional context about the chart's purpose or data source

    Returns:
        JSON string with structured critique including scores and suggestions.
    """
    # Validate file exists
    if not os.path.exists(image_path):
        return f"Error: Image file not found at {image_path}"

    try:
        # Encode the image
        image_data = _encode_image_to_base64(image_path)
        media_type = _get_image_media_type(image_path)

        # Build the prompt
        prompt = CRITIQUE_CHART_SYSTEM_PROMPT
        if context:
            prompt += f"\n\n## Context\n{context}"

        default_model_name = get_default_vlm_name()
        model = create_vlm_client(default_model_name)

        # Create message with image
        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{media_type};base64,{image_data}"},
                },
            ]
        )

        # Get the critique
        response = model.invoke([message])
        return response.content

    except Exception as e:
        return f"Error analyzing chart: {str(e)}"


__all__ = ["critique_chart"]


if __name__ == "__main__":
    result = critique_chart.invoke(
        {
            "image_path": "outputs/20260206_001955/images/interest_rate_trend_20260206_002132_7a4228f0.png"
        }
    )
    print(result)
