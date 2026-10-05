"""
DESK Companion Authentication
"""

from __future__ import annotations

import hashlib
import json
import secrets
import time
from pathlib import Path

from core.paths import DATA_DIR, atomic_write_text


class CompanionAuth:
    """
    Handles Companion pairing and device authentication.

    Pairing codes are temporary and single-use.

    Device credentials are persistent and stored in DESK's
    persistent application-data directory.
    """

    PAIRING_CODE_LIFETIME = 300  # 5 minutes

    def __init__(self):
        self._devices_path = DATA_DIR / "companion" / "devices.json"

        self._pairing_code: str | None = None
        self._pairing_expires_at: float = 0.0

        self._devices: dict[str, dict] = {}

        self._load_devices()

    # ------------------------------------------------------------------
    # Pairing
    # ------------------------------------------------------------------

    def create_pairing(self) -> dict:
        """
        Create a new temporary pairing session.

        Returns the pairing code and expiry timestamp.
        """

        code = f"{secrets.randbelow(1_000_000):06d}"

        self._pairing_code = code
        self._pairing_expires_at = (
            time.time() + self.PAIRING_CODE_LIFETIME
        )

        return {
            "code": code,
            "expires_at": self._pairing_expires_at,
            "expires_in": self.PAIRING_CODE_LIFETIME,
        }

    def get_pairing_code(self) -> str | None:
        """
        Return the currently active pairing code.

        This is intended for the desktop UI.
        """

        if not self._pairing_is_active():
            return None

        return self._pairing_code

    def pairing_active(self) -> bool:
        return self._pairing_is_active()

    def pair_device(self, code: str, device_name: str) -> dict | None:
        """
        Consume a valid pairing code and create a persistent device.

        Returns device credentials once.
        """

        if not self._pairing_is_active():
            return None

        if not secrets.compare_digest(
            str(code),
            str(self._pairing_code),
        ):
            return None

        # Pairing codes are single-use.
        self._pairing_code = None
        self._pairing_expires_at = 0.0

        device_id = secrets.token_urlsafe(16)
        token = secrets.token_urlsafe(32)

        self._devices[device_id] = {
            "device_name": device_name or "Android Device",
            "token_hash": self._hash_token(token),
            "created_at": time.time(),
            "last_seen": None,
        }

        self._save_devices()

        return {
            "device_id": device_id,
            "token": token,
        }

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def authenticate(
        self,
        device_id: str,
        token: str,
    ) -> bool:
        """
        Authenticate an already-paired device.
        """

        device = self._devices.get(device_id)

        if not device:
            return False

        token_hash = self._hash_token(token)

        if not secrets.compare_digest(
            token_hash,
            device["token_hash"],
        ):
            return False

        device["last_seen"] = time.time()
        self._save_devices()

        return True

    # ------------------------------------------------------------------
    # Device management
    # ------------------------------------------------------------------

    def list_devices(self) -> list[dict]:
        """
        Return safe device information.

        Never returns credentials.
        """

        devices = []

        for device_id, device in self._devices.items():
            devices.append(
                {
                    "device_id": device_id,
                    "device_name": device.get(
                        "device_name",
                        "Unknown Device",
                    ),
                    "created_at": device.get("created_at"),
                    "last_seen": device.get("last_seen"),
                }
            )

        return devices

    def revoke_device(self, device_id: str) -> bool:
        """
        Permanently revoke a paired device.
        """

        if device_id not in self._devices:
            return False

        del self._devices[device_id]
        self._save_devices()

        return True

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_devices(self) -> None:
        if not self._devices_path.exists():
            return

        try:
            data = json.loads(
                self._devices_path.read_text(
                    encoding="utf-8"
                )
            )

            if isinstance(data, dict):
                self._devices = data

        except (OSError, json.JSONDecodeError):
            self._devices = {}

    def _save_devices(self) -> None:
        self._devices_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        atomic_write_text(
            self._devices_path,
            json.dumps(
                self._devices,
                indent=2,
            ),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _pairing_is_active(self) -> bool:
        return (
            self._pairing_code is not None
            and time.time() < self._pairing_expires_at
        )

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(
            token.encode("utf-8")
        ).hexdigest()
