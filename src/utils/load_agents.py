import os
import re
import yaml
from typing import List, Dict


def load_agents_from_md(folder_path: str = "sub_agents") -> List[Dict]:
    """Load agent definitions from markdown files in `folder_path`.

    Files are expected to have a YAML front matter section delimited by `---`.
    Returns a list of dicts with keys: name, description, prompt, tools.
    """
    agents = []
    for filename in os.listdir(folder_path):
        # Skip non-markdown and hidden/template files
        if (
            not filename.endswith(".md")
            or filename.startswith("_")
            or filename.startswith("base_")
        ):
            continue

        with open(os.path.join(folder_path, filename), "r", encoding="utf-8") as f:
            content = f.read()

        match = re.match(r"---(.*?)---(.*)", content, re.DOTALL)
        if not match:
            continue

        meta = yaml.safe_load(match.group(1))
        prompt = match.group(2).strip()

        # Normalize tools into a list
        tools_field = meta.get("tools", [])
        if isinstance(tools_field, str):
            tools = [tools_field]
        elif isinstance(tools_field, (list, tuple)):
            tools = [str(t).strip() for t in tools_field if t]
        else:
            tools = []

        agent_def = {
            "name": meta.get("name", "").strip(),
            "description": meta.get("description", "").strip(),
            "prompt": prompt,
            "tools": tools,
        }
        agents.append(agent_def)

    return agents
