"""LLM-backed response generation service."""

from collections.abc import Iterator
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from deepfishy.infra.config.settings import settings
from deepfishy.infra.llm.chat_factory import create_llm_client
from deepfishy.shared.logging import logger


class ResponseService:
    """Generate simple chat responses with the configured LLM."""

    def __init__(self) -> None:
        self.model_name = settings.RESPONSE_MODEL
        self.location = settings.GOOGLE_CLOUD_LOCATION
        self.project = settings.GOOGLE_CLOUD_PROJECT
        self.api_key = (
            settings.GOOGLE_API_KEY
            or settings.GEMINI_API_KEY
            or settings.GOOGLE_CLOUD_API_KEY
        )

    def generate_response(self, contents: list[dict[str, Any]]) -> str:
        """Generate a text response from conversational contents."""
        llm = self._create_llm()
        response = llm.invoke(
            [
                message
                for item in contents
                if (message := self._to_langchain_message(item)) is not None
            ]
        )

        response_text = getattr(response, "text", None) or getattr(
            response, "content", None
        )
        if response_text and response_text.strip():
            return response_text.strip()

        logger.warning("Gemini returned an empty response payload")
        return "I couldn't generate a response right now."

    def stream_response(self, contents: list[dict[str, Any]]) -> Iterator[str]:
        """Stream response chunks from the configured model."""
        llm = self._create_llm()
        messages = [
            message
            for item in contents
            if (message := self._to_langchain_message(item)) is not None
        ]

        saw_content = False
        for chunk in llm.stream(messages):
            chunk_text = self._extract_text(chunk)
            if not chunk_text:
                continue

            saw_content = True
            yield chunk_text

        if not saw_content:
            logger.warning(
                "Gemini stream returned no content; falling back to full invoke"
            )
            fallback = self.generate_response(contents)
            if fallback:
                yield fallback

    def _create_llm(self):
        """Create a LangChain client with the configured settings."""
        llm = create_llm_client(self.model_name)
        if llm is None:
            raise ValueError(
                f"Unable to create response model client: {self.model_name}"
            )
        return llm

    @staticmethod
    def _extract_text(response: Any) -> str:
        """Extract text content from an LLM response or chunk."""
        response_text = getattr(response, "text", None) or getattr(
            response, "content", None
        )
        if isinstance(response_text, str):
            return response_text
        if isinstance(response_text, list):
            return "".join(
                str(item.get("text", ""))
                for item in response_text
                if isinstance(item, dict) and item.get("text")
            )
        return ""

    @staticmethod
    def _to_langchain_message(item: dict[str, Any]) -> Any | None:
        """Convert incoming content items to LangChain messages."""
        content = " ".join(
            str(part.get("text", "")).strip()
            for part in item.get("parts", [])
            if str(part.get("text", "")).strip()
        ).strip()

        if not content:
            return None

        normalized_role = str(item.get("role", "user")).strip().lower()
        if normalized_role == "system":
            return SystemMessage(content=content)
        if normalized_role in {"assistant", "model"}:
            return AIMessage(content=content)
        return HumanMessage(content=content)


__all__ = ["ResponseService"]
