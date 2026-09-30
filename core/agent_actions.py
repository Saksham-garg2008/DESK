"""
Agent Actions — Safe local actions that an agent can request.

The LLM decides what action is needed and supplies its parameters.
This module only validates and executes the requested action.
"""

from __future__ import annotations

from urllib.parse import urlparse
import webbrowser


ALLOWED_SCHEMES = {"http", "https"}


def open_url(url: str) -> str:
    """
    Open a URL in the user's default browser.

    Returns a human-readable result for the chat layer.
    """
    url = str(url).strip()

    if not url:
        raise ValueError("No URL was provided.")

    parsed = urlparse(url)

    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise ValueError("Only HTTP and HTTPS URLs can be opened.")

    if not parsed.netloc:
        raise ValueError("Invalid URL.")

    success = webbrowser.open(url)

    if not success:
        raise RuntimeError("The default browser could not be opened.")

    return url


def execute_action(action: dict) -> str:
    """
    Execute one validated agent action.

    Expected format:

        {
            "action": "open_url",
            "url": "https://www.youtube.com"
        }
    """
    if not isinstance(action, dict):
        raise ValueError("Invalid action format.")

    action_name = action.get("action")

    if action_name == "open_url":
        return open_url(action.get("url", ""))

    raise ValueError(f"Unknown agent action: {action_name}")
