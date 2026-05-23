"""
HistoryManager — Persists chat history per agent as Markdown files.
Location: workspace/history/<agent_name>.md

MD Format:
    <!-- DESK HISTORY: AgentName -->
    <!-- updated: 2025-01-01T12:00:00 -->

    <!-- MSG role:user -->
    Hello, can you help me?
    <!-- END MSG -->

    <!-- MSG role:assistant -->
    Of course! What do you need?
    <!-- END MSG -->

Rules:
- Files are ONLY deleted by explicit user action (Clear button).
- Refresh NEVER touches history files.
- Fire (delete agent) DOES delete their history file.
"""
from pathlib import Path
from datetime import datetime
import re

HISTORY_DIR = Path(__file__).parent.parent / "workspace" / "history"

_MSG_START = re.compile(r"<!-- MSG role:(\w+) -->")
_MSG_END   = "<!-- END MSG -->"
_HEADER    = re.compile(r"<!-- DESK HISTORY: (.+?) -->")


def _agent_path(agent_name: str) -> Path:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    # Sanitize name for filesystem
    safe = "".join(c for c in agent_name if c.isalnum() or c in "._- ")
    return HISTORY_DIR / f"{safe}.md"


def load_history(agent_name: str) -> list[dict]:
    """Load chat history from MD file. Returns list of {role, content} dicts."""
    path = _agent_path(agent_name)
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8")
        messages = []
        lines = text.splitlines()
        i = 0
        while i < len(lines):
            m = _MSG_START.match(lines[i].strip())
            if m:
                role = m.group(1)
                content_lines = []
                i += 1
                while i < len(lines) and lines[i].strip() != _MSG_END:
                    content_lines.append(lines[i])
                    i += 1
                content = "\n".join(content_lines).strip()
                if content:
                    messages.append({"role": role, "content": content})
            i += 1
        return messages
    except Exception:
        return []


def save_history(agent_name: str, messages: list[dict]) -> None:
    """
    Write full chat history to MD file.
    Only saves string-content messages (skips image binary data).
    """
    path = _agent_path(agent_name)
    lines = [
        f"<!-- DESK HISTORY: {agent_name} -->",
        f"<!-- updated: {datetime.now().isoformat()} -->",
        "",
    ]
    for msg in messages:
        content = msg.get("content", "")
        if not isinstance(content, str):
            # Multi-part (has attachments) — extract text parts only
            text_parts = [
                p.get("text", "") for p in content
                if isinstance(p, dict) and p.get("type") == "text"
            ]
            content = " ".join(text_parts).strip()
            if not content:
                continue
        role = msg.get("role", "user")
        lines.append(f"<!-- MSG role:{role} -->")
        lines.append(content)
        lines.append(_MSG_END)
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def clear_history(agent_name: str) -> None:
    """Wipe history file. Called ONLY by the Clear button."""
    path = _agent_path(agent_name)
    if path.exists():
        path.unlink()


def delete_agent_history(agent_name: str) -> None:
    """Called ONLY when an agent is fired (permanently deleted)."""
    clear_history(agent_name)
