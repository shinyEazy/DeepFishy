import os
import re
import yaml
from typing import List, Dict, Optional


def load_agents(
    folder_path: str = "src/sub_agents", names: Optional[List[str]] = None
) -> List[Dict]:
    """Load agent definitions from markdown files in `folder_path`.

    If `names` is provided, it should be an iterable of filenames (with or without
    the `.md` extension) and only those files will be loaded, in the order
    provided. If `names` is None, the function will scan the directory and
    load all matching markdown files (previous behavior).

    Files are expected to have a YAML front matter section delimited by `---`.
    Returns a list of dicts with keys: name, description, prompt, tools.
    """
    agents = []

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
