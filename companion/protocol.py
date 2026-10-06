"""
DESK Companion Protocol

Transport-independent API logic for DESK Companion.

The HTTP server should only translate requests into calls to this class.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QObject

from core.artifact_manager import ArtifactManager
from core.config_loader import (
    get_agent_config,
    load_agents_config,
    load_models_config,
    set_agent_config,
)
from core.memory_manager import load_memory
from core.paths import (
    BUCKET_DIR,
    WORKSPACE_DIR,
)


class CompanionProtocol(QObject):
    """
    Transport-independent Companion API logic.

    This class reads and modifies DESK's existing data structures rather
    than maintaining a separate copy of DESK state.
    """

    VERSION = "0.1.0"

    def __init__(self):
        super().__init__()

    # ------------------------------------------------------------------
    # Basic information
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        """
        Return basic DESK/Companion connection information.
        """

        agents = self._load_agent_names()

        return {
            "name": "DESK",
            "status": "online",
            "companion_version": self.VERSION,
            "agent_count": len(agents),
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
        }

    # ------------------------------------------------------------------
    # Agents
    # ------------------------------------------------------------------

    def get_agents(self) -> list[dict]:
        """
        Return the agents currently configured in DESK.

        The Companion does not maintain its own agent list. It reads
        DESK's existing agents.json and bucket files.
        """

        config = load_agents_config()
        configured_agents = config.get("agents", {})

        if not isinstance(configured_agents, dict):
            configured_agents = {}

        agents = []

        for name, agent_config in configured_agents.items():
            if not isinstance(agent_config, dict):
                agent_config = {}

            agents.append(
                {
                    "name": name,
                    "color": agent_config.get(
                        "color",
                        "#5B7FA6",
                    ),
                    "backend": agent_config.get(
                        "backend",
                        "",
                    ),
                    "model": agent_config.get(
                        "model",
                        "",
                    ),
                    "response_length": agent_config.get(
                        "response_length",
                        "standard",
                    ),
                    "chrome_profile": agent_config.get(
                        "chrome_profile",
                        None,
                    ),
                }
            )

        return agents

    def get_agent(self, agent_name: str) -> dict | None:
        """
        Return a single agent configuration, including its system prompt.
        """

        config = get_agent_config(agent_name)

        if not config:
            return None

        system_prompt = config.get(
            "system_prompt",
            "",
        )

        # Fall back to the actual bucket file if necessary.
        if not system_prompt:
            md_path = BUCKET_DIR / f"{agent_name}.md"

            try:
                if md_path.is_file():
                    system_prompt = md_path.read_text(
                        encoding="utf-8"
                    )
            except (OSError, UnicodeDecodeError):
                system_prompt = ""

        return {
            "name": agent_name,
            "color": config.get(
                "color",
                "#5B7FA6",
            ),
            "backend": config.get(
                "backend",
                "",
            ),
            "model": config.get(
                "model",
                "",
            ),
            "response_length": config.get(
                "response_length",
                "standard",
            ),
            "chrome_profile": config.get(
                "chrome_profile",
                None,
            ),
            "system_prompt": system_prompt,
        }

    def create_agent(
        self,
        name: str,
        system_prompt: str,
        backend: str,
        model: str,
        color: str = "#5B7FA6",
        response_length: str = "standard",
        chrome_profile: str | None = None,
    ) -> dict:
        """
        Create an agent using the same persistent structures used by DESK.

        This mirrors the important persistence behaviour of
        NewAgentDialog._hire().
        """

        name = str(name).strip()
        system_prompt = str(system_prompt).strip()
        backend = str(backend).strip()
        model = str(model).strip()

        if not name:
            raise ValueError("Agent name is required")

        if not system_prompt:
            raise ValueError("System prompt is required")

        if not backend:
            raise ValueError("Backend is required")

        if not model:
            raise ValueError("Model is required")

        existing = get_agent_config(name)

        if existing:
            raise ValueError(
                f"Agent '{name}' already exists"
            )

        BUCKET_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        md_path = BUCKET_DIR / f"{name}.md"

        md_path.write_text(
            system_prompt,
            encoding="utf-8",
        )

        set_agent_config(
            name,
            {
                "color": color,
                "backend": backend,
                "model": model,
                "response_length": response_length,
                "system_prompt": system_prompt,
                "chrome_profile": chrome_profile,
            },
        )

        return self.get_agent(name) or {
            "name": name,
        }

    # ------------------------------------------------------------------
    # Memory
    # ------------------------------------------------------------------

    def get_memory(
        self,
        agent_name: str,
    ) -> dict:
        """
        Return the existing DESK memory for an agent.
        """

        if not get_agent_config(agent_name):
            raise ValueError(
                f"Agent '{agent_name}' does not exist"
            )

        return {
            "agent": agent_name,
            "content": load_memory(agent_name),
        }

    # ------------------------------------------------------------------
    # Workspace
    # ------------------------------------------------------------------

    def get_workspace(self) -> dict:
        """
        Return a lightweight view of DESK's workspace.

        V1 exposes metadata only. File contents can be added later
        without changing the overall Companion architecture.
        """

        WORKSPACE_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        items = []

        for path in sorted(
            WORKSPACE_DIR.rglob("*"),
            key=lambda p: str(p).lower(),
        ):
            if not path.is_file():
                continue

            try:
                relative = path.relative_to(
                    WORKSPACE_DIR
                )
            except ValueError:
                continue

            items.append(
                {
                    "name": path.name,
                    "path": str(relative),
                    "type": "file",
                    "size": path.stat().st_size,
                }
            )

        return {
            "available": True,
            "path": str(WORKSPACE_DIR),
            "items": items,
        }

    def get_workspace_file(
    self,
    relative_path: str,
) -> dict:
        """
        Return the contents of a text file inside DESK's workspace.

        The supplied path must remain inside WORKSPACE_DIR.
        """

        relative_path = str(relative_path).strip()

        if not relative_path:
            raise ValueError("File path is required")

        workspace_root = WORKSPACE_DIR.resolve()
        file_path = (workspace_root / relative_path).resolve()

        # Prevent ../ traversal and files outside the workspace.
        try:
            file_path.relative_to(workspace_root)
        except ValueError:
            raise ValueError("Invalid workspace path")

        if not file_path.is_file():
            raise ValueError("Workspace file not found")

        # Prevent accidentally sending enormous files to Android.
        MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 MB

        file_size = file_path.stat().st_size

        if file_size > MAX_FILE_SIZE:
            raise ValueError(
                "File is too large to open in Companion"
            )

        try:
            content = file_path.read_text(
                encoding="utf-8"
            )
        except UnicodeDecodeError:
            raise ValueError(
                "This file is not a UTF-8 text file"
            )

        return {
            "name": file_path.name,
            "path": str(
                file_path.relative_to(workspace_root)
            ),
            "content": content,
            "size": file_size,
            "type": "text",
        }

    # ------------------------------------------------------------------
    # Artifacts
    # ------------------------------------------------------------------

    def get_artifacts(
        self,
        agent_name: str,
    ) -> list[dict]:
        """
        Return artifact metadata for an agent.

        Actual artifact contents remain on DESK for now.
        """

        if not get_agent_config(agent_name):
            raise ValueError(
                f"Agent '{agent_name}' does not exist"
            )

        manager = ArtifactManager()

        artifacts = manager.get_agent_artifacts(
            agent_name
        )

        result = []

        for filename, artifact in artifacts.items():
            versions = artifact.get(
                "versions",
                [],
            )

            result.append(
                {
                    "filename": filename,
                    "type": artifact.get(
                        "type",
                        "code",
                    ),
                    "language": artifact.get(
                        "language",
                        "",
                    ),
                    "created": artifact.get(
                        "created"
                    ),
                    "current_version": artifact.get(
                        "current_version",
                        1,
                    ),
                    "version_count": len(
                        versions
                    ),
                }
            )

        return result

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    def get_tasks(self) -> list:
        """
        Tasks are intentionally not exposed in Companion V1.

        Keep this method so older callers do not break.
        """

        return []

    # ------------------------------------------------------------------
    # Models
    # ------------------------------------------------------------------

    def get_models(self) -> dict:
        """
        Return DESK's bundled model/provider configuration.

        This lets the Android client populate agent creation options
        without duplicating models.json.
        """

        return load_models_config()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_agent_names() -> list[str]:
        config = load_agents_config()
        agents = config.get("agents", {})

        if not isinstance(agents, dict):
            return []

        return list(agents.keys())

    # ------------------------------------------------------------------
    # Request dispatcher
    # ------------------------------------------------------------------

    def handle_request(
        self,
        action: str,
        payload: dict | None = None,
    ) -> dict:

        payload = payload or {}

        try:
            if action == "status":
                result = self.get_status()

            elif action == "agents":
                result = self.get_agents()

            elif action == "agent":
                agent_name = str(
                    payload.get("agent", "")
                ).strip()

                if not agent_name:
                    return {
                        "success": False,
                        "error": "Agent name is required",
                    }

                result = self.get_agent(
                    agent_name
                )

                if result is None:
                    return {
                        "success": False,
                        "error": "Agent not found",
                    }

            elif action == "create_agent":
                result = self.create_agent(
                    name=payload.get("name", ""),
                    system_prompt=payload.get(
                        "system_prompt",
                        "",
                    ),
                    backend=payload.get(
                        "backend",
                        "",
                    ),
                    model=payload.get(
                        "model",
                        "",
                    ),
                    color=payload.get(
                        "color",
                        "#5B7FA6",
                    ),
                    response_length=payload.get(
                        "response_length",
                        "standard",
                    ),
                    chrome_profile=payload.get(
                        "chrome_profile",
                        None,
                    ),
                )

            elif action == "memory":
                agent_name = str(
                    payload.get("agent", "")
                ).strip()

                if not agent_name:
                    return {
                        "success": False,
                        "error": "Agent name is required",
                    }

                result = self.get_memory(
                    agent_name
                )

            elif action == "workspace":
                result = self.get_workspace()

            elif action == "workspace_file":
                file_path = str(
                    payload.get("path", "")
                ).strip()

                if not file_path:
                    return {
                        "success": False,
                        "error": "File path is required",
                    }

                result = self.get_workspace_file(
                    file_path
                )

            elif action == "artifacts":
                agent_name = str(
                    payload.get("agent", "")
                ).strip()

                if not agent_name:
                    return {
                        "success": False,
                        "error": "Agent name is required",
                    }

                result = self.get_artifacts(
                    agent_name
                )

            elif action == "models":
                result = self.get_models()

            elif action == "tasks":
                result = self.get_tasks()

            else:
                return {
                    "success": False,
                    "error": "Unknown action",
                }

            return {
                "success": True,
                "data": result,
            }

        except Exception as exc:
            return {
                "success": False,
                "error": str(exc),
            }
