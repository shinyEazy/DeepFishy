"""Shared helpers for loading agent definitions."""

import os
import re
from importlib import import_module
from typing import Any, Optional

import yaml

from deepfishy.infra.llm.chat_factory import create_llm_client
from deepfishy.shared.logging import logger


def _resolve_tool(tool_name: str) -> Any:
    """Resolve a tool name to the actual tool object."""
    tools_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "..", "engine", "tools"
    )
    tools_dir = os.path.abspath(tools_dir)
    if os.path.exists(tools_dir):
        for filename in os.listdir(tools_dir):
            if filename.endswith(".py") and not filename.startswith("_"):
                module_name = filename[:-3]
                try:
                    module = import_module(f"engine.tools.{module_name}")
                    if hasattr(module, tool_name):
                        return getattr(module, tool_name)
                except ImportError:
                    continue

    raise ValueError(f"Could not resolve tool: {tool_name}")


def load_agents(
    folder_path: str = "subagents", names: Optional[list[str]] = None
) -> list[dict]:
    """Load agent definitions from markdown files in `folder_path`."""
    agents = []

    if folder_path == "subagents":
        project_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..")
        )
        folder_path = os.path.join(project_root, "app", "engine", "subagents")

    if names is not None:
        filenames = [name if name.endswith(".md") else f"{name}.md" for name in names]
    else:
        filenames = [
            filename
            for filename in os.listdir(folder_path)
            if filename.endswith(".md")
            and not filename.startswith("_")
            and not filename.startswith("base_")
        ]

    for filename in filenames:
        path = os.path.join(folder_path, filename)
        if not os.path.exists(path):
            continue

        with open(path, "r", encoding="utf-8") as file_handle:
            content = file_handle.read()

        match = re.match(r"---(.*?)---(.*)", content, re.DOTALL)
        if not match:
            continue

        meta = yaml.safe_load(match.group(1))
        prompt = match.group(2).strip()

        tools_field = meta.get("tools", [])
        if isinstance(tools_field, str):
            tool_names = [tool.strip() for tool in tools_field.split(",")]
        elif isinstance(tools_field, (list, tuple)):
            tool_names = [str(tool).strip() for tool in tools_field if tool]
        else:
            tool_names = []

        tools = [_resolve_tool(name) for name in tool_names]

        model_name = meta.get("model")
        model = None
        if model_name:
            model = create_llm_client(model_name)
            if model:
                logger.info(
                    f"Using custom model '{model_name}' for agent '{meta.get('name')}'"
                )
            else:
                logger.warning(
                    f"Model '{model_name}' not found in config for agent '{meta.get('name')}', will use orchestrator model"
                )

        agent_def = {
            "name": meta.get("name", "").strip(),
            "description": meta.get("description", "").strip(),
            "system_prompt": prompt,
            "tools": tools,
        }
        if model is not None:
            agent_def["model"] = model

        agents.append(agent_def)

    return agents


__all__ = ["load_agents"]
