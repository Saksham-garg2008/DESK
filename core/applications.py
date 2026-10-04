"""
Application discovery and launching for DESK.

The LLM supplies only a human-readable application name.
DESK resolves that name using the host operating system.

No application names, executable paths, or aliases are hardcoded.
"""

from __future__ import annotations

import difflib
import os
import shlex
import subprocess
import sys
from pathlib import Path


MIN_MATCH_SCORE = 0.70


def _normalize_name(value: str) -> str:
    """Normalize text for comparison without changing its meaning."""

    return "".join(
        char.lower()
        for char in str(value)
        if char.isalnum()
    )


def _score_name(query: str, candidate: str) -> float:
    """
    Calculate how well an application metadata value matches
    the user's requested application name.
    """

    query = _normalize_name(query)
    candidate = _normalize_name(candidate)

    if not query or not candidate:
        return 0.0

    if query == candidate:
        return 1.0

    if candidate.startswith(query):
        return 0.95

    if query in candidate:
        return 0.90

    return difflib.SequenceMatcher(
        None,
        query,
        candidate,
    ).ratio()


def _score_application(
    query: str,
    name: str,
    generic_name: str,
    keywords: list[str],
    filename: str,
) -> float:
    """
    Score an application using metadata supplied by the OS.

    Nothing here contains application-specific knowledge.
    """

    scores = [
        _score_name(query, name),
        _score_name(query, generic_name),
        _score_name(query, filename),
    ]

    for keyword in keywords:
        scores.append(
            _score_name(query, keyword)
        )

    return max(scores, default=0.0)


def _parse_desktop_file(
    path: Path,
) -> tuple[str, str, list[str], str] | None:
    """
    Read useful metadata from a Linux .desktop file.

    Returns:
        (name, generic_name, keywords, exec_command)
    """

    try:
        lines = path.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines()
    except OSError:
        return None

    name = ""
    generic_name = ""
    keywords: list[str] = []
    exec_command = ""
    hidden = False
    no_display = False
    terminal = False

    for line in lines:
        if line == "Hidden=true":
            hidden = True

        elif line == "NoDisplay=true":
            no_display = True

        elif line == "Terminal=true":
            terminal = True

        elif not name and line.startswith("Name="):
            name = line[5:].strip()

        elif not generic_name and line.startswith("GenericName="):
            generic_name = line[12:].strip()

        elif line.startswith("Keywords="):
            raw_keywords = line[9:].strip()
            keywords = [
                keyword.strip()
                for keyword in raw_keywords.split(";")
                if keyword.strip()
            ]

        elif not exec_command and line.startswith("Exec="):
            exec_command = line[5:].strip()

    if hidden or no_display or terminal:
        return None

    if not name or not exec_command:
        return None

    return (
        name,
        generic_name,
        keywords,
        exec_command,
    )


def _linux_application_entries() -> list[dict]:
    """
    Discover applications from the Linux XDG application database.

    Searches:
      - XDG_DATA_HOME
      - XDG_DATA_DIRS

    No application list is maintained by DESK.
    """

    data_home = Path(
        os.environ.get(
            "XDG_DATA_HOME",
            Path.home() / ".local" / "share",
        )
    )

    data_dirs = [
        data_home,
        *[
            Path(path)
            for path in os.environ.get(
                "XDG_DATA_DIRS",
                "/usr/local/share:/usr/share",
            ).split(":")
            if path
        ],
    ]

    entries: list[dict] = []
    seen: set[Path] = set()

    for data_dir in data_dirs:
        applications_dir = data_dir / "applications"

        if not applications_dir.is_dir():
            continue

        for path in applications_dir.rglob("*.desktop"):
            try:
                resolved = path.resolve()
            except OSError:
                continue

            if resolved in seen:
                continue

            seen.add(resolved)

            metadata = _parse_desktop_file(path)

            if metadata is None:
                continue

            (
                name,
                generic_name,
                keywords,
                command,
            ) = metadata

            entries.append(
                {
                    "name": name,
                    "generic_name": generic_name,
                    "keywords": keywords,
                    "filename": path.stem,
                    "command": command,
                }
            )

    return entries


def _find_linux_application(
    application: str,
) -> dict:
    """
    Find the best matching installed Linux application.

    A weak match is rejected instead of launching an unrelated
    application.
    """

    matches = []

    for entry in _linux_application_entries():
        score = _score_application(
            application,
            entry["name"],
            entry["generic_name"],
            entry["keywords"],
            entry["filename"],
        )

        if score >= MIN_MATCH_SCORE:
            matches.append(
                (
                    score,
                    entry,
                )
            )

    if not matches:
        raise RuntimeError(
            f"Could not find an installed application "
            f"matching '{application}'."
        )

    matches.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    best_score, best_entry = matches[0]

    # Reject ambiguous results where the best match is not
    # sufficiently better than the second-best match.
    if len(matches) > 1:
        second_score = matches[1][0]

        if (
            best_score < 0.85
            and best_score - second_score < 0.05
        ):
            raise RuntimeError(
                f"Could not determine which installed "
                f"application matches '{application}'."
            )

    return best_entry


def _launch_linux_application(
    application: str,
) -> str:
    """Resolve and launch an installed Linux application."""

    entry = _find_linux_application(application)

    command = entry["command"]

    # Desktop Entry Exec fields may contain field codes such
    # as %f, %F, %u, and %U. DESK is launching the application
    # itself, so these arguments must not be passed.
    args = [
        part
        for part in shlex.split(command)
        if not part.startswith("%")
    ]

    if not args:
        raise RuntimeError(
            f"No launch command is available for "
            f"'{entry['name']}'."
        )

    try:
        subprocess.Popen(
            args,
            start_new_session=True,
        )
    except OSError as exc:
        raise RuntimeError(
            f"Could not launch '{entry['name']}': {exc}"
        ) from exc

    return entry["name"]


def _windows_start_menu_shortcuts() -> list[Path]:
    """
    Find application shortcuts from the user's and system
    Start Menu.
    """

    locations = []

    appdata = os.environ.get("APPDATA")
    programdata = os.environ.get("PROGRAMDATA")

    if appdata:
        locations.append(
            Path(appdata)
            / "Microsoft"
            / "Windows"
            / "Start Menu"
            / "Programs"
        )

    if programdata:
        locations.append(
            Path(programdata)
            / "Microsoft"
            / "Windows"
            / "Start Menu"
            / "Programs"
        )

    shortcuts = []

    for location in locations:
        if location.is_dir():
            shortcuts.extend(
                location.rglob("*.lnk")
            )

    return shortcuts


def _open_application_windows(
    application: str,
) -> str:
    """Find and launch a Windows Start Menu application."""

    matches = []

    for shortcut in _windows_start_menu_shortcuts():
        score = _score_name(
            application,
            shortcut.stem,
        )

        if score >= MIN_MATCH_SCORE:
            matches.append(
                (
                    score,
                    shortcut.stem,
                    shortcut,
                )
            )

    if not matches:
        raise RuntimeError(
            f"Could not find an installed application "
            f"matching '{application}'."
        )

    matches.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    _, name, shortcut = matches[0]

    try:
        os.startfile(str(shortcut))
    except OSError as exc:
        raise RuntimeError(
            f"Could not launch '{name}': {exc}"
        ) from exc

    return name


def _open_application_macos(
    application: str,
) -> str:
    """
    Ask macOS Launch Services to resolve the application.
    """

    result = subprocess.run(
        ["open", "-a", application],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.strip()
            or (
                f"Could not find an installed application "
                f"matching '{application}'."
            )
        )

    return application


def open_application(
    application: str,
) -> str:
    """
    Open an installed application by human-readable name.

    The caller does not need to know:
      - executable paths
      - installation directories
      - desktop-entry filenames
      - OS-specific launch commands
    """

    application = str(application).strip()

    if not application:
        raise ValueError(
            "No application name was provided."
        )

    if sys.platform.startswith("linux"):
        return _launch_linux_application(
            application
        )

    if sys.platform == "win32":
        return _open_application_windows(
            application
        )

    if sys.platform == "darwin":
        return _open_application_macos(
            application
        )

    raise RuntimeError(
        f"Application launching is not supported "
        f"on {sys.platform}."
    )
