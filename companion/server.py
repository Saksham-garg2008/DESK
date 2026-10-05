"""
DESK Companion Server
"""

from __future__ import annotations
from companion.discovery import CompanionDiscovery
import json
from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer,
)
from threading import Thread

from companion.auth import CompanionAuth
from companion.protocol import CompanionProtocol


class CompanionRequestHandler(BaseHTTPRequestHandler):
    """
    HTTP interface for DESK Companion.
    """

    protocol: CompanionProtocol | None = None
    auth: CompanionAuth | None = None

    # --------------------------------------------------------------
    # Helpers
    # --------------------------------------------------------------

    def _send_json(
        self,
        data: dict,
        status: int = 200,
    ) -> None:

        body = json.dumps(data).encode("utf-8")

        self.send_response(status)

        self.send_header(
            "Content-Type",
            "application/json",
        )

        self.send_header(
            "Content-Length",
            str(len(body)),
        )

        self.send_header(
            "Access-Control-Allow-Origin",
            "*",
        )

        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, X-DESK-Device-ID, X-DESK-Token",
        )

        self.end_headers()

        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(
            self.headers.get(
                "Content-Length",
                "0",
            )
        )

        if length <= 0:
            return {}

        body = self.rfile.read(length)

        try:
            return json.loads(
                body.decode("utf-8")
            )
        except json.JSONDecodeError:
            return {}

    def _authenticate(self) -> bool:
        if self.auth is None:
            return False

        device_id = self.headers.get(
            "X-DESK-Device-ID"
        )

        token = self.headers.get(
            "X-DESK-Token"
        )

        if not device_id or not token:
            return False

        return self.auth.authenticate(
            device_id,
            token,
        )

    def _require_auth(self) -> bool:
        if self._authenticate():
            return True

        self._send_json(
            {
                "success": False,
                "error": "Authentication required",
            },
            status=401,
        )

        return False

    # --------------------------------------------------------------
    # GET
    # --------------------------------------------------------------

    def do_GET(self) -> None:

        path = self.path.split("?", 1)[0]

        if path == "/api/status":

            if not self._require_auth():
                return

            result = self.protocol.handle_request(
                "status"
            )

            self._send_json(result)
            return

        if path == "/api/agents":

            if not self._require_auth():
                return

            result = self.protocol.handle_request(
                "agents"
            )

            self._send_json(result)
            return

        if path == "/api/tasks":

            if not self._require_auth():
                return

            result = self.protocol.handle_request(
                "tasks"
            )

            self._send_json(result)
            return

        if path == "/api/workspace":

            if not self._require_auth():
                return

            result = self.protocol.handle_request(
                "workspace"
            )

            self._send_json(result)
            return

        if path == "/api/devices":

            if not self._require_auth():
                return

            self._send_json(
                {
                    "success": True,
                    "devices": self.auth.list_devices(),
                }
            )
            return

        self._send_json(
            {
                "success": False,
                "error": "Not found",
            },
            status=404,
        )

    # --------------------------------------------------------------
    # POST
    # --------------------------------------------------------------

    def do_POST(self) -> None:

        path = self.path.split("?", 1)[0]

        payload = self._read_json()

        # ----------------------------------------------------------
        # Pairing
        # ----------------------------------------------------------

        if path == "/api/pair":

            code = str(
                payload.get(
                    "code",
                    "",
                )
            )

            device_name = str(
                payload.get(
                    "device_name",
                    "Android Device",
                )
            )

            result = self.auth.pair_device(
                code,
                device_name,
            )

            if result is None:
                self._send_json(
                    {
                        "success": False,
                        "error": "Invalid or expired pairing code",
                    },
                    status=401,
                )

                return

            self._send_json(
                {
                    "success": True,
                    "device": result,
                }
            )

            return

        # ----------------------------------------------------------
        # Ping
        # ----------------------------------------------------------

        if path == "/api/ping":

            if not self._require_auth():
                return

            self._send_json(
                {
                    "success": True,
                    "message": (
                        "DESK Companion connection successful"
                    ),
                }
            )

            return

        # ----------------------------------------------------------
        # Unknown endpoint
        # ----------------------------------------------------------

        self._send_json(
            {
                "success": False,
                "error": "Not found",
            },
            status=404,
        )

    # --------------------------------------------------------------
    # OPTIONS
    # --------------------------------------------------------------

    def do_OPTIONS(self) -> None:

        self.send_response(204)

        self.send_header(
            "Access-Control-Allow-Origin",
            "*",
        )

        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, X-DESK-Device-ID, X-DESK-Token",
        )

        self.send_header(
            "Access-Control-Allow-Methods",
            "GET, POST, OPTIONS",
        )

        self.end_headers()

    def log_message(
        self,
        format: str,
        *args,
    ) -> None:
        """
        Keep DESK console clean.
        """
        return


class CompanionServer:
    """
    Background HTTP server for DESK Companion.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
    ):
        self.host = host
        self.port = port

        self.protocol = CompanionProtocol()
        self.auth = CompanionAuth()

        CompanionRequestHandler.protocol = self.protocol
        CompanionRequestHandler.auth = self.auth

        self._server = ThreadingHTTPServer(
            (self.host, self.port),
            CompanionRequestHandler,
        )
        self.discovery = CompanionDiscovery(port=self.port)


        self._thread: Thread | None = None

    # --------------------------------------------------------------
    # Lifecycle
    # --------------------------------------------------------------

    def start(self) -> None:

        if self._thread is not None:
            return

        self._thread = Thread(
            target=self._server.serve_forever,
            daemon=True,
        )

        self._thread.start()
        self.discovery.start()

    def stop(self) -> None:

        if self._thread is None:
            return

        self._server.shutdown()
        self._server.server_close()

        self._thread = None
        self.discovery.stop()

    @property
    def running(self) -> bool:
        return self._thread is not None

    # --------------------------------------------------------------
    # Pairing
    # --------------------------------------------------------------

    def create_pairing(self) -> dict:
        return self.auth.create_pairing()
