"""
Agent Actions — Safe local actions that an agent can request.

The LLM decides what action is needed and supplies its parameters.
DESK decides which local configuration is used to execute that action.
"""

from __future__ import annotations

import shutil
import subprocess
import webbrowser
from urllib.parse import urlparse
from core.applications import open_application


ALLOWED_SCHEMES = {"http", "https"}


def _find_chrome() -> str | None:
    """
    Find a Chrome/Chromium executable available on the system.
    """

    candidates = (
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
    )

    for candidate in candidates:
        path = shutil.which(candidate)

        if path:
            return path

    return None


def open_url(
    url: str,
    chrome_profile: str | None = None,
) -> str:
    """
    Open a URL.

    If chrome_profile is provided, DESK opens the URL using
    that Chrome profile.

    The profile is supplied by DESK configuration.
    It is never chosen by the LLM.
    """

    url = str(url).strip()

    if not url:
        raise ValueError("No URL was provided.")

    parsed = urlparse(url)

    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise ValueError(
            "Only HTTP and HTTPS URLs can be opened."
        )

    if not parsed.netloc:
        raise ValueError("Invalid URL.")

    if chrome_profile:
        chrome = _find_chrome()

        if not chrome:
            raise RuntimeError(
                "Chrome or Chromium could not be found."
            )

        subprocess.Popen(
            [
                chrome,
                f"--profile-directory={chrome_profile}",
                url,
            ],
            start_new_session=True,
        )

        return url

    success = webbrowser.open(url)

    if not success:
        raise RuntimeError(
            "The default browser could not be opened."
        )

    return url


def execute_action(
    action: dict,
    chrome_profile: str | None = None,
) -> str:
    """
    Execute one validated agent action.

    The LLM provides the action and URL.
    DESK provides the Chrome profile.
    """

    if not isinstance(action, dict):
        raise ValueError("Invalid action format.")

    action_name = action.get("action")

    if action_name == "open_url":
        return open_url(
            action.get("url", ""),
            chrome_profile=chrome_profile,
        )

    if action_name == "open_application":
        return open_application(
            action.get("application", ""),
        )
    raise ValueError(
        f"Unknown agent action: {action_name}"
    )
