"""
Disk-based backend for persisting agent filesystem to actual disk.
This allows tracking todos, context, and memory files in a real directory.
"""

import os
import json
from typing import Optional, Dict, Any
from pathlib import Path


class DiskBackend:
    """
    Backend that persists agent filesystem operations to disk.

    This writes all agent files (todos, context, memories) to a specified
    directory on disk, making them trackable and persistent across runs.

    Args:
        base_path: Base directory where agent files will be stored
        thread_id: Optional thread ID for organizing files by session
    """

    def __init__(
        self, base_path: str = "agent_workspace", thread_id: Optional[str] = None
    ):
        self.base_path = Path(base_path)
        self.thread_id = thread_id

        # Create base directory if it doesn't exist
        if thread_id:
            self.workspace_path = self.base_path / thread_id
        else:
            self.workspace_path = self.base_path

        self.workspace_path.mkdir(parents=True, exist_ok=True)

        # Create standard subdirectories
        (self.workspace_path / "todos").mkdir(exist_ok=True)
        (self.workspace_path / "context").mkdir(exist_ok=True)
        (self.workspace_path / "memories").mkdir(exist_ok=True)

    def _get_full_path(self, path: str) -> Path:
        """Convert agent filesystem path to actual disk path."""
        # Remove leading slash if present
        clean_path = path.lstrip("/")
        return self.workspace_path / clean_path

    def ls(self, path: str = "/") -> list:
        """List files in a directory."""
        full_path = self._get_full_path(path)

        if not full_path.exists():
            return []

        if full_path.is_file():
            return [full_path.name]

        items = []
        for item in full_path.iterdir():
            if item.is_dir():
                items.append(f"{item.name}/")
            else:
                items.append(item.name)

        return sorted(items)

    def read_file(
        self,
        path: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
    ) -> str:
        """Read a file from disk."""
        full_path = self._get_full_path(path)

        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                if start_line is None and end_line is None:
                    return f.read()

                lines = f.readlines()

                if start_line is not None and end_line is not None:
                    return "".join(lines[start_line - 1 : end_line])
                elif start_line is not None:
                    return "".join(lines[start_line - 1 :])
                elif end_line is not None:
                    return "".join(lines[:end_line])

        except Exception as e:
            raise IOError(f"Error reading file {path}: {e}")

    def write_file(self, path: str, content: str) -> None:
        """Write a file to disk."""
        full_path = self._get_full_path(path)

        # Create parent directories if needed
        full_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            raise IOError(f"Error writing file {path}: {e}")

    def edit_file(self, path: str, old_content: str, new_content: str) -> None:
        """Edit a file by replacing content."""
        full_path = self._get_full_path(path)

        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                current_content = f.read()

            if old_content not in current_content:
                raise ValueError(f"Content to replace not found in {path}")

            updated_content = current_content.replace(old_content, new_content)

            with open(full_path, "w", encoding="utf-8") as f:
                f.write(updated_content)

        except Exception as e:
            raise IOError(f"Error editing file {path}: {e}")

    def delete_file(self, path: str) -> None:
        """Delete a file from disk."""
        full_path = self._get_full_path(path)

        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        try:
            if full_path.is_file():
                full_path.unlink()
            elif full_path.is_dir():
                import shutil

                shutil.rmtree(full_path)
        except Exception as e:
            raise IOError(f"Error deleting {path}: {e}")

    def get_metadata(self, path: str) -> Dict[str, Any]:
        """Get file metadata."""
        full_path = self._get_full_path(path)

        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        stat = full_path.stat()

        return {
            "size": stat.st_size,
            "created": stat.st_ctime,
            "modified": stat.st_mtime,
            "is_directory": full_path.is_dir(),
        }

    def save_todos(self, todos: list) -> None:
        """
        Save todos to a dedicated JSON file.
        This provides easy tracking of agent planning.
        """
        todos_path = self.workspace_path / "todos" / "current_todos.json"

        try:
            with open(todos_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "todos": todos,
                        "timestamp": (
                            str(Path(todos_path).stat().st_mtime)
                            if todos_path.exists()
                            else None
                        ),
                    },
                    f,
                    indent=2,
                    ensure_ascii=False,
                )
        except Exception as e:
            print(f"Warning: Could not save todos: {e}")

    def load_todos(self) -> Optional[list]:
        """Load the current todos from disk."""
        todos_path = self.workspace_path / "todos" / "current_todos.json"

        if not todos_path.exists():
            return None

        try:
            with open(todos_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("todos", [])
        except Exception as e:
            print(f"Warning: Could not load todos: {e}")
            return None

    def get_workspace_summary(self) -> Dict[str, Any]:
        """Get a summary of the workspace contents."""
        summary = {
            "workspace_path": str(self.workspace_path),
            "thread_id": self.thread_id,
            "todos": self.ls("todos"),
            "context_files": self.ls("context"),
            "memory_files": self.ls("memories"),
            "total_files": len(list(self.workspace_path.rglob("*"))),
        }

        return summary


__all__ = ["DiskBackend"]
