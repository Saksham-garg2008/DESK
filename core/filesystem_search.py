
"""Fresh, read-only filename search for DESK.

Each search performs a new filesystem enumeration across explicitly supplied
roots. It does not cache results, read file contents, or modify files.

Public API:
    search_filesystem(name, roots)
"""

import os
from datetime import datetime, timezone
from os import PathLike
from typing import Any, Iterable

from core.filesystem import iter_filesystem


def _normalize_roots(
    roots: Iterable[str | PathLike[str]],
) -> list[str]:
    """Normalize and deduplicate explicitly supplied roots."""

    if isinstance(roots, (str, bytes, os.PathLike)):
        raise ValueError(
            "Roots must be a collection of directory paths, not one path."
        )

    normalized: list[str] = []
    seen: set[str] = set()

    for root in roots:
        if not isinstance(root, (str, os.PathLike)):
            raise ValueError("Every root must be a valid filesystem path.")

        path = os.path.abspath(os.path.expanduser(os.fspath(root)))
        key = os.path.normcase(path)

        if key not in seen:
            seen.add(key)
            normalized.append(path)

    if not normalized:
        raise ValueError(
            "At least one search root must be supplied explicitly."
        )

    return normalized


def search_filesystem(
    name: str,
    roots: Iterable[str | PathLike[str]],
    *,
    partial_match: bool = False,
) -> dict[str, Any]:
    """Search for an entry by name across explicitly supplied roots.

    A fresh enumeration is performed on every call.

    Args:
        name: Filename or directory name to search for.
        roots: The roots DESK has selected for this search.
        partial_match: If True, match names containing the query.

    Returns:
        A dictionary containing matches, searched roots, errors,
        completion status, and the snapshot timestamp.

    Notes:
        - Matching is case-insensitive.
        - File contents are never read.
        - Symlink and junction traversal follows filesystem.py's policy.
        - A search with access errors is reported as incomplete.
    """

    if not isinstance(name, str) or not name.strip():
        raise ValueError("The search name must be a non-empty string.")

    query = name.strip().casefold()
    search_roots = _normalize_roots(roots)

    # This timestamp identifies when the requested snapshot began.
    snapshot_at = datetime.now(timezone.utc).isoformat()

    matches: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    seen_matches: set[str] = set()
    seen_errors: set[tuple[str, str]] = set()
    entries_scanned = 0

    # This is intentionally a fresh enumeration, not a cached result.
    for entry in iter_filesystem(roots=search_roots):
        entries_scanned += 1

        path = entry.get("path")
        entry_name = entry.get("name", "")

        if entry.get("error"):
            error_key = (path or "", entry["error"])

            if error_key not in seen_errors:
                seen_errors.add(error_key)
                errors.append({
                    "path": path or "",
                    "error": entry["error"],
                })

        candidate = entry_name.casefold()

        if partial_match:
            matched = query in candidate
        else:
            matched = query == candidate

        if not matched or not path:
            continue

        # The recursive enumerator may report a directory more than once.
        # Deduplicate matching paths so the search result remains clean.
        path_key = os.path.normcase(os.path.abspath(path))

        if path_key in seen_matches:
            continue

        seen_matches.add(path_key)

        matches.append({
            "name": entry_name,
            "path": path,
            "type": entry.get("type", "unknown"),
            "size_bytes": entry.get("size_bytes"),
        })

    matches.sort(
        key=lambda item: (
            item["name"].casefold(),
            item["path"].casefold(),
        )
    )

    return {
        "query": name.strip(),
        "match_mode": "partial" if partial_match else "exact",
        "snapshot_at": snapshot_at,
        "searched_roots": search_roots,
        "entries_scanned": entries_scanned,
        "matches": matches,
        "match_count": len(matches),
        "errors": errors,
        "complete": not errors,
    }

