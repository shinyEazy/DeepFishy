"""Compatibility shim for the chat model factory."""

from deepfishy.infra.llm.chat_factory import create_llm_client, create_vlm_client

__all__ = ["create_llm_client", "create_vlm_client"]
