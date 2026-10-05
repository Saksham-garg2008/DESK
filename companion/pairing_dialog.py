"""
DESK Companion Pairing Dialog
"""

from __future__ import annotations

import json
import socket

import qrcode

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
)


def get_local_ip() -> str:
    """
    Try to determine the computer's LAN IP address.
    """

    sock = socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM,
    )

    try:
        sock.connect(
            ("8.8.8.8", 80)
        )

        return sock.getsockname()[0]

    except OSError:
        return "127.0.0.1"

    finally:
        sock.close()


class CompanionPairingDialog(QDialog):
    """
    Displays the DESK Companion QR pairing code.
    """

    def __init__(
        self,
        server,
        parent=None,
    ):
        super().__init__(parent)

        self.server = server

        self.setWindowTitle(
            "Connect DESK Companion"
        )

        self.setModal(True)

        self._build_ui()

    def _build_ui(self) -> None:

        layout = QVBoxLayout(self)

        title = QLabel(
            "Connect DESK to your phone"
        )

        title.setAlignment(
            Qt.AlignCenter
        )

        title.setStyleSheet(
            """
            QLabel {
                font-size: 20px;
                font-weight: 600;
            }
            """
        )

        layout.addWidget(title)

        description = QLabel(
            "Open the DESK Companion app and scan this QR code."
        )

        description.setAlignment(
            Qt.AlignCenter
        )

        description.setWordWrap(True)

        layout.addWidget(description)

        ip = get_local_ip()

        pairing = self.server.create_pairing()

        payload = {
            "type": "DESK_COMPANION_PAIR",
            "version": 1,
            "host": ip,
            "port": self.server.port,
            "code": pairing["code"],
        }

        qr_data = json.dumps(
            payload,
            separators=(",", ":"),
        )

        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=4,
        )

        qr.add_data(qr_data)
        qr.make(fit=True)

        image = qr.make_image(
            fill_color="black",
            back_color="white",
        ).convert("RGB")

        width, height = image.size

        qimage = QImage(
            image.tobytes(),
            width,
            height,
            width * 3,
            QImage.Format_RGB888,
        )

        pixmap = QPixmap.fromImage(
            qimage.copy()
        )

        qr_label = QLabel()

        qr_label.setPixmap(
            pixmap.scaled(
                360,
                360,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )

        qr_label.setAlignment(
            Qt.AlignCenter
        )

        layout.addWidget(qr_label)

        info = QLabel(
            f"Network: {ip}:{self.server.port}\n"
            f"Code expires in {pairing['expires_in'] // 60} minutes"
        )

        info.setAlignment(
            Qt.AlignCenter
        )

        layout.addWidget(info)

        self.resize(
            430,
            500,
        )
