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

Storage format:
{
  "agents": {
    "Coder": {
      "index.html": {
        "type": "code",
        "language": "html",
        "created": "ISO timestamp",
        "versions": [
          {"v": 1, "content": "...", "timestamp": "ISO"},
          {"v": 2, "content": "...", "timestamp": "ISO"},
          {"v": 3, "content": "...", "timestamp": "ISO"}
        ],
        "current_version": 3
      }
    }
  }
}
"""
from __future__ import annotations
import json
import re
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional

CONFIG_DIR = Path(__file__).parent.parent / "config"
ARTIFACTS_FILE = CONFIG_DIR / "artifacts.json"

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
    Manages artifacts for all agents.
    Singleton — one instance per app session.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._data = cls._instance._load()
        return cls._instance

    # ── Persistence ────────────────────────────────────────────────────────

    def _load(self) -> dict:
        if ARTIFACTS_FILE.exists():
            try:
                return json.loads(ARTIFACTS_FILE.read_text(encoding="utf-8"))
            except Exception:
                return {"agents": {}}
        return {"agents": {}}

    def _save(self):
        CONFIG_DIR.mkdir(exist_ok=True)
        ARTIFACTS_FILE.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    def reload(self):
        """Reload from disk (called after external edits)."""
        self._data = self._load()

    # ── Core artifact operations ───────────────────────────────────────────

    def get_agent_artifacts(self, agent_name: str) -> dict:
        """Return all artifacts for an agent. Keys are filenames."""
        return self._data["agents"].get(agent_name, {})

    def get_artifact(self, agent_name: str, filename: str) -> Optional[dict]:
        """Get a single artifact dict."""
        return self._data["agents"].get(agent_name, {}).get(filename)

    def get_current_content(self, agent_name: str, filename: str) -> str:
        """Get the current version's content."""
        artifact = self.get_artifact(agent_name, filename)
        if not artifact:
            return ""
        v = artifact["current_version"]
        for ver in artifact["versions"]:
            if ver["v"] == v:
                return ver["content"]
        return ""

    def get_version_content(self, agent_name: str, filename: str, version: int) -> str:
        """Get content of a specific version."""
        artifact = self.get_artifact(agent_name, filename)
        if not artifact:
            return ""
        for ver in artifact["versions"]:
            if ver["v"] == version:
                return ver["content"]
        return ""

    def save_artifact(
        self,
        agent_name: str,
        filename: str,
        content: str,
        language: str,
    ) -> tuple[bool, int]:
        """
        Save or update an artifact.
        Returns (is_new_version, version_number).

        Rules:
        - New filename → create v1
        - Same filename, same content → no change, return current version
        - Same filename, different content → new version (keep last 3)
        """
        if "agents" not in self._data:
            self._data["agents"] = {}
        if agent_name not in self._data["agents"]:
            self._data["agents"][agent_name] = {}

        agent_artifacts = self._data["agents"][agent_name]
        now = datetime.now().isoformat()

        if filename not in agent_artifacts:
            # New artifact — v1
            agent_artifacts[filename] = {
                "type": "code",
                "language": language,
                "created": now,
                "versions": [
                    {"v": 1, "content": content, "timestamp": now}
                ],
                "current_version": 1,
            }
            self._save()
            return True, 1

        # Existing artifact
        artifact = agent_artifacts[filename]
        current_v = artifact["current_version"]
        current_content = self.get_current_content(agent_name, filename)

        # Content hash comparison
        if _hash(content) == _hash(current_content):
            return False, current_v  # No change

        # New version
        new_v = current_v + 1
        artifact["versions"].append(
            {"v": new_v, "content": content, "timestamp": now}
        )
        # Keep only last MAX_VERSIONS
        if len(artifact["versions"]) > MAX_VERSIONS:
            artifact["versions"] = artifact["versions"][-MAX_VERSIONS:]

        artifact["current_version"] = new_v
        artifact["language"] = language  # Update language if changed

        self._save()
        return True, new_v

    def delete_agent_artifacts(self, agent_name: str):
        """Delete ALL artifacts for an agent. Called on Fire."""
        if "agents" in self._data and agent_name in self._data["agents"]:
            del self._data["agents"][agent_name]
            self._save()

    def clear_agent_artifacts(self, agent_name: str):
        """Clear artifacts for an agent. Called on Clear Chat."""
        if "agents" in self._data and agent_name in self._data["agents"]:
            self._data["agents"][agent_name] = {}
            self._save()

    def artifact_count(self, agent_name: str) -> int:
        return len(self._data["agents"].get(agent_name, {}))

    def all_agents_with_artifacts(self) -> list[str]:
        return list(self._data.get("agents", {}).keys())

    # ── Code block parsing ─────────────────────────────────────────────────

    def parse_and_save_artifacts(
        self,
        agent_name: str,
        response_text: str,
    ) -> list[tuple[str, int]]:
        """
        Parse a complete agent response for code blocks.
        Saves each detected artifact.
        Returns list of (filename, version) for each artifact found.
        """
        results = []
        blocks = _extract_code_blocks(response_text)

        for language, code_content, context_before in blocks:
            if not code_content.strip():
                continue

            filename = _infer_filename(language, code_content, context_before)
            if not filename:
                continue

            ext = LANG_TO_EXT.get(language.lower(), language.lower() or "txt")
            # Ensure filename has correct extension
            if "." not in filename:
                filename = f"{filename}.{ext}"

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
