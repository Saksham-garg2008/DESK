"""
ArtifactManager — Manages all agent artifacts (code files).

Responsibilities:
- Parse agent responses for code blocks + filenames
- Store artifacts with versioning (max 3 versions per file)
- Persist to config/artifacts.json
- Delete artifacts when agent is fired or chat is cleared

Version logic:
- Same filename + different content → new version (keep last 3)
- Same filename + same content → no duplicate
- New filename → v1

"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.paths import ARTIFACTS_DIR, atomic_write_text

MAX_VERSIONS = 3


# Language → extension map
LANG_TO_EXT: dict[str, str] = {
    "python":     "py",
    "py":         "py",
    "javascript": "js",
    "js":         "js",
    "typescript": "ts",
    "ts":         "ts",
    "html":       "html",
    "css":        "css",
    "json":       "json",
    "yaml":       "yaml",
    "yml":        "yml",
    "sql":        "sql",
    "bash":       "sh",
    "sh":         "sh",
    "shell":      "sh",
    "rust":       "rs",
    "go":         "go",
    "java":       "java",
    "c":          "c",
    "cpp":        "cpp",
    "c++":        "cpp",
    "csharp":     "cs",
    "cs":         "cs",
    "php":        "php",
    "ruby":       "rb",
    "swift":      "swift",
    "kotlin":     "kt",
    "r":          "r",
    "toml":       "toml",
    "xml":        "xml",
    "markdown":   "md",
    "md":         "md",
    "jsx":        "jsx",
    "tsx":        "tsx",
    "vue":        "vue",
    "svelte":     "svelte",
    "scss":       "scss",
    "sass":       "sass",
    "less":       "less",
    "dockerfile": "dockerfile",
    "makefile":   "makefile",
    "nginx":      "conf",
    "env":        "env",
    "plaintext":  "txt",
    "text":       "txt",
    "txt":        "txt",
}

# Common filenames agents use — regex patterns
KNOWN_FILENAMES = re.compile(
    r'\b([\w\-]+\.(py|js|ts|jsx|tsx|html|css|scss|sass|json|yaml|yml|'
    r'sql|sh|bash|go|rs|java|c|cpp|cs|php|rb|swift|kt|vue|svelte|'
    r'toml|xml|md|txt|env|dockerfile|makefile|conf|r|less))\b',
    re.IGNORECASE
)



class ArtifactManager:
    """
    Filesystem-backed artifact manager.

    Storage:
        Artifacts/
            AgentName/
                ArtifactName/
                    metadata.json
                    v1.py
                    v2.py

    Public metadata retains the previous shape so existing consumers
    can continue reading versions and their content.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._data = {"agents": {}}
            cls._instance.reload()
        return cls._instance

    # ── Safe paths ─────────────────────────────────────────────────────

    @staticmethod
    def _safe_component(value: str) -> str:
        """Turn a user/model-provided name into one safe path component."""
        value = str(value).strip()
        value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value)
        value = value.strip(" .")
        return value or "Untitled"

    def _agent_dir(self, agent_name: str) -> Path:
        return ARTIFACTS_DIR / self._safe_component(agent_name)

    def _artifact_dir(self, agent_name: str, filename: str) -> Path:
        # Use the filename stem for the directory; the extension belongs
        # to each version file. This keeps paths readable.
        safe_name = Path(self._safe_component(filename)).name
        stem = Path(safe_name).stem or "artifact"
        return self._agent_dir(agent_name) / stem

    @staticmethod
    def _metadata_path(artifact_dir: Path) -> Path:
        return artifact_dir / "metadata.json"

    @staticmethod
    def _version_path(artifact_dir: Path, version: int, extension: str) -> Path:
        extension = re.sub(r"[^A-Za-z0-9_-]", "", extension) or "txt"
        return artifact_dir / f"v{version}.{extension}"

    # ── Persistence and indexing ───────────────────────────────────────

    def _load(self) -> dict:
        data = {"agents": {}}

        if not ARTIFACTS_DIR.exists():
            return data

        for agent_dir in ARTIFACTS_DIR.iterdir():
            if not agent_dir.is_dir():
                continue

            agent_name = agent_dir.name
            data["agents"][agent_name] = {}

            for artifact_dir in agent_dir.iterdir():
                if not artifact_dir.is_dir():
                    continue

                metadata_path = self._metadata_path(artifact_dir)
                try:
                    metadata = json.loads(
                        metadata_path.read_text(encoding="utf-8")
                    )
                except (OSError, json.JSONDecodeError):
                    continue

                filename = metadata.get("filename")
                if not filename:
                    continue

                extension = metadata.get("extension", "txt")
                versions = []

                for version_info in metadata.get("versions", []):
                    version_number = version_info.get("v")
                    if not isinstance(version_number, int):
                        continue

                    version_path = self._version_path(
                        artifact_dir, version_number, extension
                    )
                    try:
                        content = version_path.read_text(encoding="utf-8")
                    except OSError:
                        # Do not expose metadata for a version whose file
                        # is missing or unreadable.
                        continue

                    versions.append({
                        "v": version_number,
                        "content": content,
                        "timestamp": version_info.get("timestamp", ""),
                    })

                if not versions:
                    continue

                current_version = metadata.get("current_version")
                available = {item["v"] for item in versions}
                if current_version not in available:
                    current_version = max(available)

                data["agents"][agent_name][filename] = {
                    "type": metadata.get("type", "code"),
                    "language": metadata.get("language", ""),
                    "created": metadata.get("created", ""),
                    "versions": sorted(versions, key=lambda item: item["v"]),
                    "current_version": current_version,
                    "_artifact_dir": str(artifact_dir),
                    "_extension": extension,
                }

        return data

    def _save_metadata(self, agent_name: str, filename: str) -> None:
        artifact = self._data["agents"][agent_name][filename]
        artifact_dir = Path(artifact["_artifact_dir"])

        metadata = {
            "filename": filename,
            "type": artifact.get("type", "code"),
            "language": artifact.get("language", ""),
            "extension": artifact.get("_extension", "txt"),
            "created": artifact.get("created", ""),
            "current_version": artifact["current_version"],
            "versions": [
                {"v": item["v"], "timestamp": item["timestamp"]}
                for item in artifact["versions"]
            ],
        }

        atomic_write_text(
            self._metadata_path(artifact_dir),
            json.dumps(metadata, indent=2, ensure_ascii=False),
        )

    def reload(self):
        """Reload artifact metadata and version contents from disk."""
        self._data = self._load()

    # ── Core artifact operations ───────────────────────────────────────

    def get_agent_artifacts(self, agent_name: str) -> dict:
        return self._data["agents"].get(agent_name, {})

    def get_artifact(self, agent_name: str, filename: str) -> Optional[dict]:
        return self._data["agents"].get(agent_name, {}).get(filename)

    def get_current_content(self, agent_name: str, filename: str) -> str:
        artifact = self.get_artifact(agent_name, filename)
        if not artifact:
            return ""

        current = artifact["current_version"]
        for version in artifact["versions"]:
            if version["v"] == current:
                return version["content"]
        return ""

    def get_version_content(
        self, agent_name: str, filename: str, version: int
    ) -> str:
        artifact = self.get_artifact(agent_name, filename)
        if not artifact:
            return ""

        for item in artifact["versions"]:
            if item["v"] == version:
                return item["content"]
        return ""

    def save_artifact(
        self,
        agent_name: str,
        filename: str,
        content: str,
        language: str,
    ) -> tuple[bool, int]:
        """
        Save an artifact or create a new version.

        Returns (is_new_version, version_number).
        Identical content does not create a duplicate version.
        Only the latest MAX_VERSIONS are retained.
        """
        agent_name = self._safe_component(agent_name)
        filename = Path(self._safe_component(filename)).name
        language = (language or "").strip().lower()

        if not filename:
            raise ValueError("Artifact filename cannot be empty.")

        agent_artifacts = self._data["agents"].setdefault(agent_name, {})
        now = datetime.now().astimezone().isoformat()

        artifact = agent_artifacts.get(filename)

        if artifact:
            current_version = artifact["current_version"]
            current_content = self.get_current_content(agent_name, filename)

            if _hash(content) == _hash(current_content):
                return False, current_version

            new_version = current_version + 1
            artifact_dir = Path(artifact["_artifact_dir"])
            extension = artifact["_extension"]

            version_path = self._version_path(
                artifact_dir, new_version, extension
            )
            atomic_write_text(version_path, content)

            artifact["versions"].append({
                "v": new_version,
                "content": content,
                "timestamp": now,
            })

            # Remove old version files and metadata entries.
            artifact["versions"] = sorted(
                artifact["versions"], key=lambda item: item["v"]
            )
            while len(artifact["versions"]) > MAX_VERSIONS:
                oldest = artifact["versions"].pop(0)
                old_path = self._version_path(
                    artifact_dir, oldest["v"], extension
                )
                try:
                    old_path.unlink(missing_ok=True)
                except OSError:
                    pass

            artifact["current_version"] = new_version
            artifact["language"] = language
            self._save_metadata(agent_name, filename)
            return True, new_version

        # Create a new artifact directory.
        artifact_dir = self._artifact_dir(agent_name, filename)

        # Avoid silently reusing a directory if two names collapse to
        # the same sanitized path.
        if artifact_dir.exists():
            base = artifact_dir.name
            suffix = hashlib.sha256(filename.encode("utf-8")).hexdigest()[:8]
            artifact_dir = artifact_dir.with_name(f"{base}-{suffix}")

        extension = Path(filename).suffix.lstrip(".")
        if not extension:
            extension = LANG_TO_EXT.get(language, "txt")
            filename = f"{filename}.{extension}"
            artifact_dir = self._artifact_dir(agent_name, filename)

        artifact_dir.mkdir(parents=True, exist_ok=True)

        version_path = self._version_path(artifact_dir, 1, extension)
        atomic_write_text(version_path, content)

        agent_artifacts[filename] = {
            "type": "code",
            "language": language,
            "created": now,
            "versions": [{
                "v": 1,
                "content": content,
                "timestamp": now,
            }],
            "current_version": 1,
            "_artifact_dir": str(artifact_dir),
            "_extension": extension,
        }

        self._save_metadata(agent_name, filename)
        return True, 1

    def delete_agent_artifacts(self, agent_name: str):
        """Delete every artifact belonging to an agent."""
        agent_key = self._safe_component(agent_name)
        agent_dir = self._agent_dir(agent_key)

        if agent_dir.exists():
            shutil.rmtree(agent_dir)

        self._data["agents"].pop(agent_key, None)

    def clear_agent_artifacts(self, agent_name: str):
        """Delete all artifacts for an agent when its chat is cleared."""
        self.delete_agent_artifacts(agent_name)

    def artifact_count(self, agent_name: str) -> int:
        return len(self.get_agent_artifacts(agent_name))

    def all_agents_with_artifacts(self) -> list[str]:
        return [
            name for name, artifacts in self._data["agents"].items()
            if artifacts
        ]

    # ── Code block parsing ─────────────────────────────────────────────

    def parse_and_save_artifacts(
        self,
        agent_name: str,
        response_text: str,
    ) -> list[tuple[str, int]]:
        """Save detected code artifacts and return (filename, version)."""
        results = []

        for language, code_content, context_before in _extract_code_blocks(
            response_text
        ):
            if not code_content.strip():
                continue

            filename = _infer_filename(
                language, code_content, context_before
            )
            if not filename:
                continue

            if "." not in filename:
                extension = LANG_TO_EXT.get(language.lower(), "txt")
                filename = f"{filename}.{extension}"

            is_new, version = self.save_artifact(
                agent_name, filename, code_content, language.lower()
            )
            if is_new:
                results.append((filename, version))

        return results


# ── Private helpers ────────────────────────────────────────────────────────

def _hash(content: str) -> str:
    return hashlib.md5(content.strip().encode()).hexdigest()


def _extract_code_blocks(text: str) -> list[tuple[str, str, str]]:
    """
    Extract all fenced code blocks from text.
    Returns list of (language, code_content, context_before).
    Context_before = up to 200 chars before the block (for filename hints).
    """
    pattern = re.compile(
        r'(?s)```(\w*)\n(.*?)```',
        re.DOTALL
    )
    results = []
    for m in pattern.finditer(text):
        lang = m.group(1).strip().lower()
        code = m.group(2)
        start = max(0, m.start() - 300)
        context = text[start:m.start()]
        results.append((lang, code, context))
    return results


def _infer_filename(language: str, code: str, context: str) -> Optional[str]:
    """
    Try to determine the filename from:
    1. Context text before code block (agent often says "Here's `index.html`:")
    2. First comment line inside the code block
    3. Language + common naming conventions (index.html, main.py, etc.)
    """
    # 1. Look for explicit filename in context (last 300 chars before block)
    matches = KNOWN_FILENAMES.findall(context)
    if matches:
        # Take the LAST match — agent usually mentions filename right before the block
        return matches[-1][0]

    # 2. Look for filename in first 3 lines of code (comments)
    code_lines = code.strip().splitlines()[:5]
    for line in code_lines:
        line = line.strip()
        # Python/JS comment: # filename.py or // filename.js
        comment_match = re.match(
            r'^[#//]+\s*([\w\-]+\.\w+)\s*$', line
        )
        if comment_match:
            return comment_match.group(1)
        # Also check for "filename: xyz.py" style
        label_match = re.match(
            r'^[#//\-*]+\s*(?:file(?:name)?|path):\s*([\w\-./]+\.\w+)',
            line, re.IGNORECASE
        )
        if label_match:
            return label_match.group(1)

    # 3. Heuristic based on language
    ext = LANG_TO_EXT.get(language.lower(), "")
    if not ext:
        return None

    heuristics = {
        "html":   "index.html",
        "css":    "styles.css",
        "scss":   "styles.scss",
        "js":     "script.js",
        "jsx":    "App.jsx",
        "tsx":    "App.tsx",
        "ts":     "index.ts",
        "py":     "main.py",
        "sh":     "run.sh",
        "sql":    "query.sql",
        "json":   "config.json",
        "yaml":   "config.yaml",
        "yml":    "config.yml",
        "toml":   "config.toml",
        "md":     "README.md",
        "go":     "main.go",
        "rs":     "main.rs",
        "java":   "Main.java",
        "kt":     "Main.kt",
        "swift":  "main.swift",
        "php":    "index.php",
        "rb":     "main.rb",
        "r":      "analysis.r",
        "vue":    "App.vue",
        "svelte": "App.svelte",
    }
    return heuristics.get(ext, f"code.{ext}")
