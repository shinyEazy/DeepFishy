"""
Utility script to inspect agent workspace contents.
This helps you track what todos, context, and memories the agent has created.
"""

import os
import json
import argparse
from pathlib import Path
from datetime import datetime


def format_timestamp(timestamp_str: str) -> str:
    """Format timestamp string to human-readable format."""
    try:
        # Parse session ID format: YYYYMMDD_HHMMSS
        dt = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return timestamp_str


def inspect_session(workspace_path: Path, session_id: str):
    """Inspect a specific agent session."""
    session_path = workspace_path / session_id

    if not session_path.exists():
        print(f"❌ Session not found: {session_id}")
        return

    print("\n" + "=" * 70)
    print(f"📂 SESSION: {session_id}")
    print(f"   Time: {format_timestamp(session_id)}")
    print("=" * 70)

    # Check todos
    todos_dir = session_path / "todos"
    if todos_dir.exists() and list(todos_dir.iterdir()):
        print("\n📋 TODOS:")
        print("-" * 70)

        todos_file = todos_dir / "current_todos.json"
        if todos_file.exists():
            try:
                with open(todos_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    todos = data.get("todos", [])

                    if todos:
                        for i, todo in enumerate(todos, 1):
                            status = todo.get("status", "unknown")
                            content = todo.get("content", "No description")

                            status_icon = {
                                "pending": "⏳",
                                "in_progress": "🔄",
                                "completed": "✅",
                                "cancelled": "❌",
                            }.get(status, "❓")

                            print(f"  {i}. {status_icon} [{status.upper()}] {content}")
                    else:
                        print("  No todos found")
            except Exception as e:
                print(f"  ⚠️  Error reading todos: {e}")
        else:
            print("  No todos file found")

    # Check context files
    context_dir = session_path / "context"
    if context_dir.exists() and list(context_dir.iterdir()):
        print("\n📄 CONTEXT FILES:")
        print("-" * 70)

        for file in sorted(context_dir.iterdir()):
            if file.is_file():
                size = file.stat().st_size
                size_str = f"{size:,} bytes" if size < 1024 else f"{size/1024:.1f} KB"
                print(f"  • {file.name} ({size_str})")

                # Show preview for small text files
                if file.suffix in [".txt", ".md"] and size < 500:
                    try:
                        with open(file, "r", encoding="utf-8") as f:
                            preview = f.read()[:200]
                            if len(preview) > 0:
                                print(f"    Preview: {preview[:100]}...")
                    except:
                        pass

    # Check memory files
    memory_dir = session_path / "memories"
    if memory_dir.exists() and list(memory_dir.iterdir()):
        print("\n🧠 MEMORY FILES:")
        print("-" * 70)

        for file in sorted(memory_dir.iterdir()):
            if file.is_file():
                size = file.stat().st_size
                size_str = f"{size:,} bytes" if size < 1024 else f"{size/1024:.1f} KB"
                print(f"  • {file.name} ({size_str})")

    print("\n" + "=" * 70 + "\n")


def list_all_sessions(workspace_path: Path):
    """List all agent sessions."""
    if not workspace_path.exists():
        print(f"❌ Workspace not found: {workspace_path}")
        print(f"   Run the agent first to create workspace files.")
        return []

    sessions = []
    for item in sorted(workspace_path.iterdir(), reverse=True):
        if item.is_dir() and not item.name.startswith("."):
            sessions.append(item.name)

    return sessions


def main():
    parser = argparse.ArgumentParser(
        description="Inspect agent workspace contents (todos, context, memories)"
    )
    parser.add_argument(
        "--workspace",
        default="agent_workspace",
        help="Path to agent workspace directory (default: agent_workspace)",
    )
    parser.add_argument(
        "--session", help="Specific session ID to inspect (format: YYYYMMDD_HHMMSS)"
    )
    parser.add_argument(
        "--latest", action="store_true", help="Inspect the latest session"
    )
    parser.add_argument(
        "--all", action="store_true", help="Show all sessions with summaries"
    )

    args = parser.parse_args()
    workspace_path = Path(args.workspace)

    print("\n" + "=" * 70)
    print("🔍 AGENT WORKSPACE INSPECTOR")
    print("=" * 70)
    print(f"Workspace: {workspace_path.absolute()}")

    # List all sessions
    sessions = list_all_sessions(workspace_path)

    if not sessions:
        print("\n❌ No sessions found.")
        print("   Run the agent to create workspace files:")
        print("   python -m src.app.engine.main --input 'Your query here'")
        return

    print(f"Found {len(sessions)} session(s)\n")

    if args.session:
        # Inspect specific session
        inspect_session(workspace_path, args.session)

    elif args.latest:
        # Inspect latest session
        print(f"📌 Inspecting latest session...\n")
        inspect_session(workspace_path, sessions[0])

    elif args.all:
        # Show all sessions
        for session_id in sessions:
            inspect_session(workspace_path, session_id)

    else:
        # Just list sessions
        print("📅 AVAILABLE SESSIONS:")
        print("-" * 70)
        for i, session_id in enumerate(sessions, 1):
            session_time = format_timestamp(session_id)
            session_path = workspace_path / session_id

            # Count files
            todos_count = (
                len(list((session_path / "todos").iterdir()))
                if (session_path / "todos").exists()
                else 0
            )
            context_count = (
                len(list((session_path / "context").iterdir()))
                if (session_path / "context").exists()
                else 0
            )
            memory_count = (
                len(list((session_path / "memories").iterdir()))
                if (session_path / "memories").exists()
                else 0
            )

            print(f"  {i}. {session_id} ({session_time})")
            print(
                f"     Todos: {todos_count} | Context: {context_count} | Memories: {memory_count}"
            )

        print("\n💡 Usage:")
        print(f"   • Inspect latest: python {__file__} --latest")
        print(f"   • Inspect specific: python {__file__} --session {sessions[0]}")
        print(f"   • Show all: python {__file__} --all")

    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
