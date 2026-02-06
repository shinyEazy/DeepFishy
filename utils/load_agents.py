import os
import re
import yaml
from typing import List, Dict, Optional, Any
from importlib import import_module

from utils.model_factory import create_llm_client
from core.logging import logger


def _resolve_tool(tool_name: str) -> Any:
    """Resolve a tool name to the actual tool object.

    Supports importing from tools module, e.g. 'search_engine_tavily'
    will import from 'tools.search_engine_tavily'.
    """
    tools_dir = os.path.join(os.path.dirname(__file__), "..", "engine", "tools")
    if os.path.exists(tools_dir):
        for filename in os.listdir(tools_dir):
            if filename.endswith(".py") and not filename.startswith("_"):
                module_name = filename[:-3]  # Remove .py extension
                try:
                    module = import_module(f"engine.tools.{module_name}")
                    if hasattr(module, tool_name):
                        return getattr(module, tool_name)
                except ImportError:
                    continue

    raise ValueError(f"Could not resolve tool: {tool_name}")


def load_agents(
    folder_path: str = "subagents", names: Optional[List[str]] = None
) -> List[Dict]:
    """Load agent definitions from markdown files in `folder_path`.

    If `names` is provided, it should be an iterable of filenames (with or without
    the `.md` extension) and only those files will be loaded, in the order
    provided. If `names` is None, the function will scan the directory and
    load all matching markdown files (previous behavior).

    Files are expected to have a YAML front matter section delimited by `---`.
    Returns a list of dicts with keys: name, description, system_prompt, tools.
    """
    agents = []

    # Resolve subagents directory if using default path
    if folder_path == "subagents":
        module_dir = os.path.dirname(os.path.abspath(__file__))
        app_root = os.path.dirname(os.path.dirname(module_dir))
        folder_path = os.path.join(app_root, "app", "engine", "subagents")

    # Normalize names to actual filenames if provided
    if names is not None:
        normalized = []
        for n in names:
            if n.endswith(".md"):
                normalized.append(n)
            else:
                normalized.append(f"{n}.md")
        filenames = normalized
    else:
        # Scan directory for valid files
        filenames = [
            f
            for f in os.listdir(folder_path)
            if f.endswith(".md") and not f.startswith("_") and not f.startswith("base_")
        ]

    for filename in filenames:
        path = os.path.join(folder_path, filename)
        if not os.path.exists(path):
            # skip missing files silently (caller may provide names that don't exist)
            continue

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        match = re.match(r"---(.*?)---(.*)", content, re.DOTALL)
        if not match:
            continue

        meta = yaml.safe_load(match.group(1))
        prompt = match.group(2).strip()

        # Normalize tools into a list and resolve them
        tools_field = meta.get("tools", [])
        tool_names = []
        if isinstance(tools_field, str):
            tool_names = [t.strip() for t in tools_field.split(",")]
        elif isinstance(tools_field, (list, tuple)):
            tool_names = [str(t).strip() for t in tools_field if t]

        tools = [_resolve_tool(name) for name in tool_names]

        # Handle model configuration
        # If model is specified in agent.md, load from config.yaml
        # If not specified, subagent will use orchestrator's model (deepagents default)
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
                    f"Model '{model_name}' not found in config for agent '{meta.get('name')}', "
                    "will use orchestrator model"
                )

        agent_def = {
            "name": meta.get("name", "").strip(),
            "description": meta.get("description", "").strip(),
            "system_prompt": prompt,
            "tools": tools,
        }

        # Only add model to agent_def if explicitly configured
        # This allows deepagents to fall back to orchestrator's model when None
        if model is not None:
            agent_def["model"] = model

        agents.append(agent_def)

    return agents
