
"""
Agent Protocol — Extracts structured action requests from LLM responses.

Supports:
- Multiple actions inside <DESK_ACTIONS>
- Existing single actions inside <DESK_ACTION>
"""

from __future__ import annotations

import json
import re


MULTI_ACTION_PATTERN = re.compile(
    r"<DESK_ACTIONS>\s*(\[.*?\])\s*</DESK_ACTIONS>",
    re.DOTALL,
)

SINGLE_ACTION_PATTERN = re.compile(
    r"<DESK_ACTION>\s*(\{.*?\})\s*</DESK_ACTION>",
    re.DOTALL,
)


def extract_actions(text: str) -> tuple[list[dict], str]:
    """
    Extract one or more actions and return the remaining visible text.

    Multi-action format:
        <DESK_ACTIONS>
        [
            {"action": "open_application", "application": "Chrome"},
            {"action": "open_application", "application": "File Manager"}
        ]
        </DESK_ACTIONS>

    The previous single-action format remains supported.
    """

    if not text:
        return [], text

    match = MULTI_ACTION_PATTERN.search(text)

    if match:
        try:
            actions = json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            return [], text

        if (
            not isinstance(actions, list)
            or not actions
            or not all(isinstance(action, dict) for action in actions)
        ):
            return [], text

        remaining = (
            text[:match.start()] + text[match.end():]
        ).strip()

        return actions, remaining

    # Backward compatibility with the original single-action format.
    match = SINGLE_ACTION_PATTERN.search(text)

    if not match:
        return [], text

    try:
        action = json.loads(match.group(1).strip())
    except json.JSONDecodeError:
        return [], text

    if not isinstance(action, dict):
        return [], text

    remaining = (
        text[:match.start()] + text[match.end():]
    ).strip()

    return [action], remaining


def extract_action(text: str) -> tuple[dict | None, str]:
    """Compatibility wrapper for callers expecting one action."""

    actions, remaining = extract_actions(text)

    if not actions:
        return None, remaining

    return actions[0], remaining
