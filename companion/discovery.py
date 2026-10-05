"""
DESK Companion LAN Discovery
"""

from __future__ import annotations

import json
import socket
import threading


DISCOVERY_PORT = 8766
DISCOVERY_MESSAGE = b"DESK_DISCOVER"


class CompanionDiscovery:
    def __init__(self, port: int = 8765):
        self.port = port

        self._socket: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:

        if self._running:
            return

        self._running = True

        self._socket = socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM
        )

        self._socket.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1
        )

        self._socket.bind(
            ("0.0.0.0", DISCOVERY_PORT)
        )

        self._thread = threading.Thread(
            target=self._run,
            name="DESK-Companion-Discovery",
            daemon=True
        )

        self._thread.start()

    def stop(self) -> None:

        self._running = False

        if self._socket is not None:

            try:
                self._socket.close()
            except OSError:
                pass

            self._socket = None

        if (
            self._thread is not None
            and self._thread.is_alive()
        ):
            self._thread.join(timeout=1)

        self._thread = None

    def _run(self) -> None:

        while self._running:

            try:

                if self._socket is None:
                    break

                data, address = self._socket.recvfrom(4096)

                if data != DISCOVERY_MESSAGE:
                    continue

                response = json.dumps(
                    {
                        "type":
                            "DESK_COMPANION_DISCOVERY",
                        "version": 1,
                        "port": self.port,
                    }
                ).encode("utf-8")

                self._socket.sendto(
                    response,
                    address
                )

            except OSError:

                if self._running:
                    continue

                break

            except Exception:
                continue
