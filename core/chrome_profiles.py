"""
Chrome Profiles — Discover installed Chrome profiles.

DESK stores the Chrome profile directory in agent configuration.
The LLM never chooses or receives this information.
"""

from __future__ import annotations

import json
from pathlib import Path


def _chrome_user_data_dirs() -> list[Path]:
    """
    Return possible Chrome user-data directories for Linux.
    """

    home = Path.home()

    return [
        home / ".config" / "google-chrome",
        home / ".config" / "chromium",
    ]


def get_chrome_profiles() -> list[dict]:
    """
    Discover Chrome/Chromium profiles.

    Returns:

        [
            {
                "name": "Personal",
                "directory": "Default",
            },
            {
                "name": "Work",
                "directory": "Profile 1",
            },
        ]

    The directory value is what Chrome requires for
    --profile-directory.
    """

    profiles = []

    for user_data_dir in _chrome_user_data_dirs():
        local_state = user_data_dir / "Local State"

        if not local_state.exists():
            continue

        try:
            data = json.loads(
                local_state.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            continue

        info_cache = (
            data
            .get("profile", {})
            .get("info_cache", {})
        )

        for directory, info in info_cache.items():
            if not isinstance(info, dict):
                continue

            name = info.get("name") or directory

            profiles.append({
                "name": str(name),
                "directory": str(directory),
            })

        # Chrome found — don't also return Chromium duplicates.
        if profiles:
            break

    profiles.sort(
        key=lambda profile: profile["name"].lower()
    )

    return profiles
