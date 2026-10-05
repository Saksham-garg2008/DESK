"""
DESK Companion Protocol
"""

from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import QObject


class CompanionProtocol(QObject):
    """
    Transport-independent Companion API logic.

    The HTTP server should only translate requests into calls
    to this class.
    """

    VERSION = "0.1.0"

    def __init__(self):
        super().__init__()

    # ------------------------------------------------------------------
    # Basic information
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        return {
            "name": "DESK",
            "status": "online",
            "companion_version": self.VERSION,
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
        }

    # ------------------------------------------------------------------
    # DESK data
    # ------------------------------------------------------------------

    def get_agents(self) -> list:
        """
        Placeholder.

        Will later connect to DESK's real agent manager.
        """

        return []

    def get_tasks(self) -> list:
        """
        Placeholder.

        Will later connect to DESK's task system.
        """

        return []

    def get_workspace(self) -> dict:
        """
        Placeholder.

        Will later expose workspace/artifact metadata.
        """

        return {
            "available": True,
            "items": [],
        }

    # ------------------------------------------------------------------
    # Request dispatcher
    # ------------------------------------------------------------------

    def handle_request(
        self,
        action: str,
        payload: dict | None = None,
    ) -> dict:

        try:
            if action == "status":
                result = self.get_status()

            elif action == "agents":
                result = self.get_agents()

            elif action == "tasks":
                result = self.get_tasks()

            elif action == "workspace":
                result = self.get_workspace()

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
