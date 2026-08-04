"""
MemoryManager — Persists distilled, long-term memory per agent as Markdown.
Location: workspace/memory/<agent_name>.md

This is NOT the raw chat transcript (that's history_manager.py).
This is a condensed, evolving understanding of the user/project —
the kind of thing a competent assistant would jot down after a
meeting so they don't have to be re-briefed every time.

MD Format:
    <!-- DESK MEMORY: AgentName -->
    <!-- updated: 2026-07-09T14:30:00 -->

    ## User Preferences
    - ...

    ## Project Context
    - ...

    ## Key Decisions
    - ...

    ## Open Threads
    - ...

Rules:
- Full overwrite on each distillation. No diffing, no appending.
- Manual edits via the Memory panel are plain file writes — no LLM involved.
- Distillation failures are silent. Chat is never blocked or interrupted
  by a memory update failing.
- Distillation is exchange-count-based, not time-based, so short but
  important conversations aren't lost, and long chatty sessions don't
  spam the memory model every turn.
"""
from pathlib import Path
from datetime import datetime

MEMORY_DIR = Path(__file__).parent.parent / "workspace" / "memory"

MEMORY_TEMPLATE = """<!-- DESK MEMORY: {agent_name} -->
<!-- updated: {timestamp} -->

## User Preferences

## Project Context

## Key Decisions

## Open Threads
"""

# Exchanges (one user message + one assistant reply = 1 exchange) between
# automatic distillation runs.
DISTILL_EVERY_N_EXCHANGES = 4


def _agent_memory_path(agent_name: str) -> Path:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    safe = "".join(c for c in agent_name if c.isalnum() or c in "._- ")
    return MEMORY_DIR / f"{safe}.md"


def load_memory(agent_name: str) -> str:
    """Load raw memory markdown for an agent. Returns '' if none exists yet."""
    path = _agent_memory_path(agent_name)
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def save_memory(agent_name: str, content: str) -> None:
    """
    Overwrite the memory file for an agent.
    Used for BOTH automatic distillation output and manual panel edits.
    Always plain — no LLM call happens in this function.
    """
    path = _agent_memory_path(agent_name)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def delete_agent_memory(agent_name: str) -> None:
    """Called ONLY when an agent is fired (permanently deleted)."""
    path = _agent_memory_path(agent_name)
    if path.exists():
        path.unlink()


def rename_memory(old_name: str, new_name: str) -> None:
    """
    Called when an agent is renamed via EditAgentDialog — same treatment
    as history_manager's rename handling, so a renamed agent keeps its
    accumulated memory instead of starting over.
    """
    old_path = _agent_memory_path(old_name)
    if old_path.exists():
        new_path = _agent_memory_path(new_name)
        old_path.rename(new_path)


def blank_memory(agent_name: str) -> str:
    """A fresh, empty memory file skeleton for a brand-new agent."""
    return MEMORY_TEMPLATE.format(
        agent_name=agent_name,
        timestamp=datetime.now().isoformat(),
    )


def memory_exists(agent_name: str) -> bool:
    return _agent_memory_path(agent_name).exists()


def build_distillation_prompt(agent_name: str, existing_memory: str,
                               recent_exchanges: list[dict]) -> tuple[str, str]:
    """
    Build the (system_prompt, user_prompt) pair sent to the Memory Agent.

    recent_exchanges: list of {"role": "user"/"assistant", "content": str}
    (already flattened to plain text — no attachments/images).

    The model is expected to return the FULL replacement memory file
    content, not a diff — this keeps the writer simple and avoids drift.
    """
    system_prompt = (
        "You are a memory-keeping assistant. Your only job is to maintain "
        "a short, useful memory file for an AI agent, like a note-taker "
        "quietly updating a colleague's notes after a meeting.\n\n"
        "Rules:\n"
        "- Only record information that would genuinely help in a FUTURE "
        "conversation with this specific agent: stable user preferences, "
        "ongoing project context, decisions that were made, and open "
        "threads that still need resolving.\n"
        "- Do NOT record small talk, one-off details, or anything that "
        "won't matter next time (e.g. what the user ate today).\n"
        "- Be concise. Bullet points. No commentary, no preamble.\n"
        "- Preserve existing memory unless it's outdated, contradicted, "
        "or resolved — then update or remove it.\n"
        "- Output ONLY the full replacement markdown file, using exactly "
        "these four headers in this order: '## User Preferences', "
        "'## Project Context', '## Key Decisions', '## Open Threads'. "
        "Keep the '<!-- DESK MEMORY -->' and '<!-- updated -->' comment "
        "lines at the top.\n"
        "- Do not wrap the output in code fences. Output raw markdown only."
    )

    convo_text = "\n".join(
        f"{'User' if m.get('role') == 'user' else 'Agent'}: {m.get('content', '')}"
        for m in recent_exchanges
        if isinstance(m.get("content"), str)
    )

    existing = existing_memory.strip() or blank_memory(agent_name)

    user_prompt = (
        f"Current memory file for agent '{agent_name}':\n\n"
        f"{existing}\n\n"
        f"---\n\n"
        f"Recent conversation to consider:\n\n"
        f"{convo_text}\n\n"
        f"---\n\n"
        f"Output the full updated memory file now."
    )

    return system_prompt, user_prompt


def clean_distillation_output(raw: str, agent_name: str) -> str:
    """
    Sanitize the Memory Agent's raw output before saving.
    Strips code fences if the model ignored instructions, ensures the
    header/timestamp comment lines are present.
    """
    text = raw.strip()

    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    if not text:
        return blank_memory(agent_name)

    if "<!-- DESK MEMORY" not in text:
        text = f"<!-- DESK MEMORY: {agent_name} -->\n{text}"

    ts = datetime.now().isoformat()
    lines = text.split("\n")
    out_lines = []
    replaced_ts = False
    for line in lines:
        if line.strip().startswith("<!-- updated:"):
            out_lines.append(f"<!-- updated: {ts} -->")
            replaced_ts = True
        else:
            out_lines.append(line)
    text = "\n".join(out_lines)
    if not replaced_ts:
        parts = text.split("\n", 1)
        if len(parts) == 2:
            text = f"{parts[0]}\n<!-- updated: {ts} -->\n{parts[1]}"
        else:
            text = f"{text}\n<!-- updated: {ts} -->"

    return text.strip() + "\n"