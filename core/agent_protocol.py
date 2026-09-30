"""
Agent Protocol — Detects structured action requests in LLM responses.

The model decides which action to request.
DESK parses the request and passes it to the action executor.
"""

from __future__ import annotations

import json
import re


ACTION_PATTERN = re.compile(
    r"<DESK_ACTION>\s*(\{.*?\})\s*</DESK_ACTION>",
    re.DOTALL,
)


def extract_action(text: str) -> tuple[dict | None, str]:
    """
    Extract an action request from an LLM response.

    Expected model output:

        <DESK_ACTION>
        {"action": "open_url", "url": "https://www.youtube.com"}
        </DESK_ACTION>

    Returns:

        (action_dict, remaining_text)

    If no action exists:

        (None, original_text)
    """

    if not text:
        return None, text

    match = ACTION_PATTERN.search(text)

    if not match:
        return None, text

    raw_json = match.group(1).strip()

    try:
        action = json.loads(raw_json)
    except json.JSONDecodeError:
        return None, text

    if not isinstance(action, dict):
        return None, text

    remaining = (
        text[:match.start()] +
        text[match.end():]
    ).strip()

    return action, remaining
