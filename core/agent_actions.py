
"""
Agent Actions — Safe local actions that an agent can request.

The LLM requests an action and supplies its parameters.
DESK controls local configuration and filesystem search scope.
"""

from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import webbrowser
from pathlib import Path
from urllib.parse import urlparse

from core.applications import open_application
from core.filesystem_search import search_filesystem


ALLOWED_SCHEMES = {"http", "https"}

# Linux filesystem types that represent virtual/system filesystems,
# not user-mounted storage drives.
_LINUX_VIRTUAL_FILESYSTEMS = {
    "autofs", "binfmt_misc", "bpf", "cgroup", "cgroup2",
    "configfs", "debugfs", "devpts", "devtmpfs", "efivarfs",
    "fusectl", "hugetlbfs", "mqueue", "overlay", "proc",
    "pstore", "ramfs", "securityfs", "squashfs", "sysfs",
    "tmpfs", "tracefs",
}

# Never use these system locations as independent search roots.
# Home is added separately, so the user's own files remain searchable.
_LINUX_SYSTEM_MOUNTPOINTS = {
    "/", "/boot", "/boot/efi", "/dev", "/etc", "/home",
    "/opt", "/proc", "/root", "/run", "/snap", "/sys",
    "/tmp", "/usr", "/var",
}

_NETWORK_FILESYSTEMS = {
    "9p", "cifs", "davfs", "fuse.sshfs", "nfs", "nfs4",
    "smb3",
}


def _find_chrome() -> str | None:
    """Find an available Chrome/Chromium executable."""
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
    """Open an HTTP(S) URL, optionally using DESK's configured profile."""
    url = str(url).strip()

    if not url:
        raise ValueError("No URL was provided.")

    parsed = urlparse(url)

    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise ValueError("Only HTTP and HTTPS URLs can be opened.")

    if not parsed.netloc:
        raise ValueError("Invalid URL.")

    if chrome_profile:
        chrome = _find_chrome()

        if not chrome:
            raise RuntimeError("Chrome or Chromium could not be found.")

        subprocess.Popen(
            [chrome, f"--profile-directory={chrome_profile}", url],
            start_new_session=True,
        )
        return url

    if not webbrowser.open(url):
        raise RuntimeError("The default browser could not be opened.")

    return url


def _windows_search_roots(home: Path) -> list[str]:
    """Use the user's home plus other available logical drives.

    The drive containing Home is not scanned from its root, which avoids
    turning a normal file search into a scan of the entire system drive.
    """
    roots = [str(home)]
    home_drive = os.path.splitdrive(str(home))[0].casefold()

    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetLogicalDrives.restype = ctypes.c_uint32
        drive_mask = kernel32.GetLogicalDrives()

        for index in range(26):
            if not drive_mask & (1 << index):
                continue

            drive = f"{chr(ord('A') + index)}:\\"

            if drive[:2].casefold() == home_drive:
                continue

            if os.path.isdir(drive):
                roots.append(drive)

    except (AttributeError, OSError):
        pass

    return roots


def _linux_mounted_roots(home: Path) -> list[str]:
    """Discover mounted storage from Linux mount information.

    The system root and standard system mountpoints are not used as
    independent roots. User Home is added separately.
    """
    roots: list[str] = []
    mountinfo = Path("/proc/self/mountinfo")

    try:
        lines = mountinfo.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []

    for line in lines:
        try:
            before, after = line.split(" - ", 1)
            fields = before.split()
            filesystem_fields = after.split()

            # Mountpoint is field 5 in the pre-separator section.
            mountpoint = fields[4]
            filesystem_type = filesystem_fields[0].casefold()
            source = filesystem_fields[1] if len(filesystem_fields) > 1 else ""

            # Decode mountinfo's escaped spaces, tabs, newlines and slashes.
            for escaped, decoded in (
                (r"\040", " "),
                (r"\011", "\t"),
                (r"\012", "\n"),
                (r"\134", "\\"),
            ):
                mountpoint = mountpoint.replace(escaped, decoded)

            path = Path(mountpoint)

            if not path.is_absolute() or not path.is_dir():
                continue

            normalized = os.path.normpath(str(path))

            if normalized in _LINUX_SYSTEM_MOUNTPOINTS:
                continue

            if filesystem_type in _LINUX_VIRTUAL_FILESYSTEMS:
                continue

            is_storage_device = source.startswith("/dev/")
            is_network_storage = (
                filesystem_type in _NETWORK_FILESYSTEMS
                or filesystem_type.startswith("fuse.sshfs")
            )

            if not (is_storage_device or is_network_storage):
                continue

            # Do not use a mounted parent of Home as a search root:
            # Home itself is the approved root in that case.
            try:
                path.resolve().relative_to(home.resolve())
                is_inside_home = True
            except (OSError, ValueError):
                is_inside_home = False

            if is_inside_home:
                continue

            roots.append(normalized)

        except (IndexError, ValueError, OSError):
            continue

    return roots


def _macos_mounted_roots() -> list[str]:
    """Discover mounted volumes under macOS's volume mount directory."""
    roots: list[str] = []
    volumes = Path("/Volumes")

    try:
        for entry in volumes.iterdir():
            try:
                if entry.is_dir() and os.path.ismount(entry):
                    roots.append(str(entry.resolve()))
            except OSError:
                continue
    except OSError:
        pass

    return roots


def discover_search_roots() -> list[str]:
    """Return approved search roots without scanning the system root."""
    home = Path.home().resolve()
    roots = [str(home)]

    if os.name == "nt":
        roots.extend(_windows_search_roots(home))
    elif os.sys.platform == "darwin":
        roots.extend(_macos_mounted_roots())
    elif os.sys.platform.startswith("linux"):
        roots.extend(_linux_mounted_roots(home))

    # Deduplicate roots without changing their order.
    unique_roots: list[str] = []
    seen: set[str] = set()

    for root in roots:
        try:
            normalized = os.path.normcase(
                os.path.realpath(os.path.expanduser(root))
            )
        except (OSError, ValueError):
            continue

        if normalized not in seen and os.path.isdir(normalized):
            seen.add(normalized)
            unique_roots.append(normalized)

    return unique_roots


def _search_filesystem_action(action: dict) -> str:
    """Search for a filename using only DESK-discovered roots."""
    name = action.get("name")

    if not isinstance(name, str) or not name.strip():
        raise ValueError("A filename is required for filesystem search.")

    name = name.strip()

    if len(name) > 255:
        raise ValueError("The filename search query is too long.")

    partial_match = action.get("partial_match", False)

    if not isinstance(partial_match, bool):
        raise ValueError("'partial_match' must be true or false.")

    roots = discover_search_roots()

    if not roots:
        raise RuntimeError("DESK could not discover any search roots.")

    # Crucially, roots are chosen by DESK—not accepted from the LLM.
    result = search_filesystem(
        name=name,
        roots=roots,
        partial_match=partial_match,
    )

    matches = result.get("matches", [])
    count = result.get("match_count", len(matches))

    if not matches:
        searched = ", ".join(result.get("searched_roots", roots))
        status = "Search completed" if result.get("complete", False) else (
            "Search finished with some locations unavailable"
        )
        return f"{status}. No matches found for '{name}'. Searched: {searched}"

    lines = [
        f"Found {count} match(es) for '{name}':"
    ]

    # Keep the chat response manageable if a common name matches many files.
    for match in matches[:20]:
        if isinstance(match, dict):
            path = match.get("path", "")
        else:
            path = str(match)

        if path:
            lines.append(f"- {path}")

    if count > 20:
        lines.append(f"- And {count - 20} more match(es).")

    if not result.get("complete", True):
        lines.append(
            "Note: some locations could not be fully searched."
        )

    return "\n".join(lines)
    

def _create_folder_action(action: dict) -> str:
    """Create a folder and any missing parent directories."""

    folder_path = action.get("path")

    if not isinstance(folder_path, str) or not folder_path.strip():
        raise ValueError("A folder path is required.")

    path = Path(folder_path.strip()).expanduser()

    if not path.is_absolute():
        raise ValueError(
            "Please provide an absolute folder path, "
            "or use a path beginning with ~/."
        )

    if path == path.parent:
        raise ValueError("The filesystem root cannot be used as a folder.")

    if path.exists():
        if path.is_dir():
            return f"Folder already exists: {path}"

        raise ValueError(
            f"Cannot create folder '{path}': a file already exists there."
        )

    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RuntimeError(
            f"Could not create folder '{path}': {exc}"
        ) from exc

    if not path.is_dir():
        raise RuntimeError(f"The folder could not be created: {path}")

    return f"Created folder: {path}"



def _create_file_action(action: dict) -> str:
    """Create a text file and any missing parent directories."""

    file_path = action.get("path")
    content = action.get("content")

    if not isinstance(file_path, str) or not file_path.strip():
        raise ValueError("A file path is required.")

    if not isinstance(content, str):
        raise ValueError("File content must be text.")

    # Expand paths such as ~/Desktop/project/main.py.
    path = Path(file_path.strip()).expanduser()

    if not path.is_absolute():
        raise ValueError(
            "Please provide an absolute file path, "
            "or use a path beginning with ~/."
        )

    if not path.name:
        raise ValueError("The path must include a filename.")

    try:
        # Create the project's parent folders if necessary.
        path.parent.mkdir(parents=True, exist_ok=True)

        # Exclusive creation: never overwrite an existing file.
        with path.open("x", encoding="utf-8", newline="") as file:
            file.write(content)

    except FileExistsError:
        raise ValueError(
            f"Cannot create '{path}': the file already exists. "
            "Choose another filename to avoid overwriting it."
        ) from None
    except OSError as exc:
        raise RuntimeError(
            f"Could not create '{path}': {exc}"
        ) from exc

    return f"Created file: {path}"


def execute_action(
    action: dict,
    chrome_profile: str | None = None,
) -> str:
    """Execute one supported action."""
    if not isinstance(action, dict):
        raise ValueError("Invalid action format.")

    action_name = action.get("action")

    if action_name == "open_url":
        return open_url(
            action.get("url", ""),
            chrome_profile=chrome_profile,
        )

    if action_name == "open_application":
        return open_application(action.get("application", ""))

    if action_name == "search_filesystem":
        return _search_filesystem_action(action)
      
    
    if action_name == "create_file":
        return _create_file_action(action)
        
    if action_name == "create_folder":
        return _create_folder_action(action)


    raise ValueError(f"Unknown agent action: {action_name}")

