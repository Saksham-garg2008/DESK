
"""Read-only filesystem discovery and listing for DESK.

This module lists filesystem entries and their paths. It does not read file
contents, index files, or modify the filesystem.

Public API:
    discover_roots()
    list_directory(path)
    iter_filesystem(roots=None)
    inspect_filesystem()
"""

import ctypes
import os
import platform
import stat
from pathlib import Path
from typing import Any, Iterator


def discover_roots() -> list[str]:
    """Discover filesystem roots using operating-system interfaces.

    Windows: discover available logical drives.
    Linux/macOS and other POSIX systems: start at the filesystem root.
    Mounted filesystems beneath a root are encountered during traversal.
    """
    if os.name == "nt":
        return _windows_roots()

    # POSIX filesystems expose their hierarchy through the root directory.
    return [os.path.abspath(os.sep)]


def _windows_roots() -> list[str]:
    """Discover available Windows logical drives without assuming drive letters."""
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetLogicalDrives.restype = ctypes.c_uint32
        drive_mask = kernel32.GetLogicalDrives()

        if not drive_mask:
            return []

        roots = []

        for index in range(26):
            if drive_mask & (1 << index):
                drive = f"{chr(ord('A') + index)}:\\"
                roots.append(drive)

        return roots

    except (AttributeError, OSError):
        return []


def _absolute_path(path: str | os.PathLike[str]) -> str:
    """Expand the home shortcut and return an absolute path."""
    return os.path.abspath(os.path.expanduser(os.fspath(path)))


def _entry_type(mode: int) -> str:
    """Describe an entry using its filesystem metadata."""
    if stat.S_ISDIR(mode):
        return "directory"
    if stat.S_ISREG(mode):
        return "file"
    if stat.S_ISLNK(mode):
        return "symlink"
    if stat.S_ISSOCK(mode):
        return "socket"
    if stat.S_ISFIFO(mode):
        return "fifo"
    if stat.S_ISCHR(mode):
        return "character_device"
    if stat.S_ISBLK(mode):
        return "block_device"
    return "other"


def _record(
    path: str,
    metadata: os.stat_result | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Build a listing record without opening or reading file contents."""
    absolute = _absolute_path(path)
    name = os.path.basename(os.path.normpath(absolute))

    if absolute == os.path.abspath(os.sep):
        name = os.sep

    result: dict[str, Any] = {
        "name": name,
        "path": absolute,
        "type": "unknown",
        "size_bytes": None,
    }

    if error is not None:
        result["error"] = error
        return result

    if metadata is not None:
        result["type"] = _entry_type(metadata.st_mode)

        if stat.S_ISREG(metadata.st_mode):
            result["size_bytes"] = metadata.st_size

    return result


def list_directory(
    path: str | os.PathLike[str],
) -> dict[str, Any]:
    """List every entry directly inside a directory.

    Relative paths are resolved against the current working directory.
    Symlinks are listed but never followed to determine entry type or size.
    """
    directory = _absolute_path(path)
    entries: list[dict[str, Any]] = []

    try:
        with os.scandir(directory) as iterator:
            for entry in iterator:
                entry_path = os.path.join(directory, entry.name)

                try:
                    metadata = entry.stat(follow_symlinks=False)
                    entries.append(_record(entry_path, metadata))
                except OSError as exc:
                    # Preserve the entry even when its metadata is unavailable.
                    entries.append(_record(entry_path, error=str(exc)))

        entries.sort(key=lambda item: (item["name"].casefold(), item["name"]))

        return {
            "path": directory,
            "entries": entries,
            "count": len(entries),
            "error": None,
        }

    except OSError as exc:
        return {
            "path": directory,
            "entries": entries,
            "count": 0,
            "error": str(exc),
        }


def _is_link_or_junction(entry: os.DirEntry[str]) -> bool:
    """Identify links that must not be traversed."""
    try:
        if entry.is_symlink():
            return True

        # Available on newer Python versions on Windows.
        is_junction = getattr(entry, "is_junction", None)
        if is_junction is not None and is_junction():
            return True

    except OSError:
        return True

    return False


def iter_filesystem(
    roots: list[str] | None = None,
) -> Iterator[dict[str, Any]]:
    """Recursively enumerate filesystem entries without reading file contents.

    Entries are yielded one at a time to keep memory use low.

    If roots is omitted, filesystem roots are discovered automatically.
    Directory symlinks and junctions are listed but not traversed.
    Errors are yielded as records so one inaccessible location does not stop
    the rest of the traversal.
    """
    starting_roots = discover_roots() if roots is None else roots
    pending = list(reversed([_absolute_path(root) for root in starting_roots]))
    visited_directories: set[tuple[int, int]] = set()

    while pending:
        current = pending.pop()

        try:
            metadata = os.stat(current, follow_symlinks=False)

            if stat.S_ISLNK(metadata.st_mode):
                yield _record(current, metadata)
                continue

            if not stat.S_ISDIR(metadata.st_mode):
                yield _record(current, metadata)
                continue

            # Device and inode identity helps avoid revisiting the same directory.
            identity = (metadata.st_dev, metadata.st_ino)
            if identity in visited_directories:
                continue

            visited_directories.add(identity)
            yield _record(current, metadata)

            try:
                with os.scandir(current) as iterator:
                    child_directories: list[str] = []

                    for entry in iterator:
                        entry_path = entry.path

                        try:
                            child_metadata = entry.stat(follow_symlinks=False)
                            yield _record(entry_path, child_metadata)

                            if (
                                stat.S_ISDIR(child_metadata.st_mode)
                                and not _is_link_or_junction(entry)
                            ):
                                child_directories.append(entry_path)

                        except OSError as exc:
                            yield _record(entry_path, error=str(exc))

                    # Reverse sorting makes traversal order stable with a stack.
                    child_directories.sort(
                        key=lambda value: (
                            os.path.basename(value).casefold(),
                            os.path.basename(value),
                        ),
                        reverse=True,
                    )
                    pending.extend(child_directories)

            except OSError as exc:
                yield _record(current, error=str(exc))

        except OSError as exc:
            yield _record(current, error=str(exc))


def inspect_filesystem() -> dict[str, Any]:
    """Return basic filesystem discovery information, not a recursive listing."""
    return {
        "platform": platform.system(),
        "home": str(Path.home()),
        "roots": discover_roots(),
    }

