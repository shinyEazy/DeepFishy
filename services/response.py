"""LLM-backed response service."""

import os
from collections.abc import Iterator
from typing import Any

from core.logging import logger
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI


class ResponseService:
    """Generate simple chat responses with Gemini via LangChain."""

    def __init__(self) -> None:
        self.model_name = os.getenv("RESPONSE_MODEL", "gemini-3.1-flash-lite-preview")
        self.location = os.getenv("GOOGLE_CLOUD_LOCATION") or os.getenv(
            "GOOGLE_CLOUD_LOCATION", "us-central1"
        )
        self.project = os.getenv("GOOGLE_CLOUD_PROJECT")
        self.api_key = (
            os.getenv("GOOGLE_API_KEY")
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_CLOUD_API_KEY")
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
            logger.warning("Gemini stream returned no content; falling back to full invoke")
            fallback = self.generate_response(contents)
            if fallback:
                yield fallback

    def _create_llm(self) -> ChatGoogleGenerativeAI:
        """Create a LangChain Gemini client with the configured settings."""
        llm_kwargs: dict[str, Any] = {
            "model": self.model_name,
            "location": self.location,
            "temperature": 1,
            "top_p": 0.95,
            "max_tokens": 32768,
            "vertexai": True,
        }
        if self.project:
            llm_kwargs["project"] = self.project
        if self.api_key:
            llm_kwargs["api_key"] = self.api_key
        return ChatGoogleGenerativeAI(**llm_kwargs)

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
