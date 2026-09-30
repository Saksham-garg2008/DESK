"""
DESK Paths
----------

Separates application resources from persistent user data.

IMPORTANT:
- Bundled/read-only resources live with the application.
- User data NEVER lives inside the PyInstaller bundle.
- User data survives application restarts, executable replacement,
  upgrades, and normal installation-folder changes.

Supported platforms:
- Windows
- Linux
- macOS
- Other Unix-like systems fall back to ~/.local/share/DESK
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


APP_NAME = "DESK"
DATA_VERSION = 1


# ---------------------------------------------------------------------------
# Application / resource directory
# ---------------------------------------------------------------------------
#
# This is where bundled files such as:
#   config/models.json
#   ui/styles/theme.qss
# live.
#
# NEVER use this directory for user-generated/writable data.
#

if getattr(sys, "frozen", False):
    # PyInstaller --onefile extracts bundled resources here temporarily.
    RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
else:
    # Normal source checkout.
    RESOURCE_DIR = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Persistent user-data directory
# ---------------------------------------------------------------------------

def _default_data_dir() -> Path:
    """
    Return the OS-appropriate persistent DESK data directory.

    Windows:
        %APPDATA%/DESK

    macOS:
        ~/Library/Application Support/DESK

    Linux / Unix:
        $XDG_DATA_HOME/DESK
        or ~/.local/share/DESK
    """

    # Optional developer override.
    # Useful for testing and portable/dev environments.
    override = os.environ.get("DESK_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()

    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / APP_NAME

        # Extremely unusual fallback.
        return Path.home() / "AppData" / "Roaming" / APP_NAME

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME

    # Linux and other Unix-like systems.
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home).expanduser() / APP_NAME

    return Path.home() / ".local" / "share" / APP_NAME


DATA_DIR = _default_data_dir()

# Persistent user directories.
CONFIG_DIR = DATA_DIR / "config"
BUCKET_DIR = DATA_DIR / "bucket"
WORKSPACE_DIR = DATA_DIR / "workspace"

HISTORY_DIR = WORKSPACE_DIR / "history"
MEMORY_DIR = WORKSPACE_DIR / "memory"
IMAGES_DIR = HISTORY_DIR / "images"


# ---------------------------------------------------------------------------
# Resource paths
# ---------------------------------------------------------------------------

RESOURCE_CONFIG_DIR = RESOURCE_DIR / "config"
RESOURCE_BUCKET_DIR = RESOURCE_DIR / "bucket"
RESOURCE_WORKSPACE_DIR = RESOURCE_DIR / "workspace"
RESOURCE_STYLES_DIR = RESOURCE_DIR / "ui" / "styles"


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

def initialize_data_directory() -> None:
    """
    Create DESK's persistent directory structure.

    This function is safe to call every time DESK starts.
    """

    for directory in (
        DATA_DIR,
        CONFIG_DIR,
        BUCKET_DIR,
        WORKSPACE_DIR,
        HISTORY_DIR,
        MEMORY_DIR,
        IMAGES_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    _initialize_data_version()
    _migrate_legacy_data()


def _initialize_data_version() -> None:
    """
    Keep a tiny version marker for future data migrations.

    This is deliberately separate from DESK's application version.
    """

    version_file = DATA_DIR / "data_version"

    if not version_file.exists():
        version_file.write_text(
            str(DATA_VERSION),
            encoding="utf-8",
        )
        return

    try:
        current_version = int(
            version_file.read_text(encoding="utf-8").strip()
        )
    except (ValueError, OSError):
        current_version = 0

    if current_version < DATA_VERSION:
        _migrate_data_version(current_version, DATA_VERSION)

        version_file.write_text(
            str(DATA_VERSION),
            encoding="utf-8",
        )


def _migrate_data_version(old_version: int, new_version: int) -> None:
    """
    Future data-schema migrations belong here.

    NEVER delete user data during an automatic migration.

    Example future:
        if old_version < 2:
            ...
    """

    # DATA_VERSION == 1 currently has no schema migration.
    pass


# ---------------------------------------------------------------------------
# Legacy migration
# ---------------------------------------------------------------------------

def _migrate_legacy_data() -> None:
    """
    Safely migrate data from older DESK layouts.

    Older source builds stored writable data beside the source code:

        config/
        bucket/
        workspace/

    We copy user data into the new persistent directory ONLY when the
    destination does not already contain that data.

    Existing persistent user data is NEVER overwritten.
    """

    # Do not attempt to migrate the persistent directory into itself.
    legacy_root = RESOURCE_DIR

    # In a PyInstaller build, RESOURCE_DIR points into _MEIPASS.
    # Those files are bundled defaults, not reliable old user data.
    #
    # Therefore legacy migration is only appropriate for non-frozen
    # source/dev installations.
    if getattr(sys, "frozen", False):
        return

    legacy_config = legacy_root / "config"
    legacy_bucket = legacy_root / "bucket"
    legacy_workspace = legacy_root / "workspace"

    _copy_missing_tree(
        legacy_config,
        CONFIG_DIR,
        skip_names={"models.json"},
    )

    _copy_missing_tree(
        legacy_bucket,
        BUCKET_DIR,
    )

    _copy_missing_tree(
        legacy_workspace,
        WORKSPACE_DIR,
    )


def _copy_missing_tree(
    source: Path,
    destination: Path,
    skip_names: set[str] | None = None,
) -> None:
    """
    Copy files/directories only when the destination does not already
    contain them.

    Existing user data always wins.
    """

    if not source.exists() or not source.is_dir():
        return

    skip_names = skip_names or set()

    destination.mkdir(parents=True, exist_ok=True)

    for item in source.iterdir():
        if item.name in skip_names:
            continue

        target = destination / item.name

        # NEVER overwrite existing user data.
        if target.exists():
            continue

        try:
            if item.is_dir():
                shutil.copytree(item, target)
            else:
                shutil.copy2(item, target)
        except OSError:
            # Migration is best-effort.
            # Failure must never destroy or overwrite existing data.
            pass


# ---------------------------------------------------------------------------
# Safe writes
# ---------------------------------------------------------------------------

def atomic_write_text(
    path: Path,
    content: str,
    encoding: str = "utf-8",
) -> None:
    """
    Atomically replace a text file.

    This protects against corruption if DESK crashes or loses power
    while writing.

    The file is written completely first and then replaced.
    """

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    temp_path = path.with_name(path.name + ".tmp")

    try:
        temp_path.write_text(content, encoding=encoding)
        os.replace(temp_path, path)
    finally:
        # Clean up an abandoned temp file if something failed.
        try:
            if temp_path.exists():
                temp_path.unlink()
        except OSError:
            pass


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """
    Atomically replace a binary file.
    """

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    temp_path = path.with_name(path.name + ".tmp")

    try:
        temp_path.write_bytes(data)
        os.replace(temp_path, path)
    finally:
        try:
            if temp_path.exists():
                temp_path.unlink()
        except OSError:
            pass


def get_user_data_location() -> Path:
    """
    Public helper for Settings/About/diagnostics.
    """
    return DATA_DIR
