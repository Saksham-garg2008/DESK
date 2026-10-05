"""
DESK — Entry Point
"""

import sys
import os

sys.path.insert(
    0,
    os.path.dirname(__file__),
)

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QShortcut
from PySide6.QtGui import QKeySequence
from PySide6.QtCore import Qt

from ui.main_window import MainWindow
from core.paths import initialize_data_directory

from companion.server import CompanionServer
from companion.pairing_dialog import CompanionPairingDialog


def main():

    initialize_data_directory()

    app = QApplication(sys.argv)

    app.setApplicationName("DESK")
    app.setApplicationVersion("2.1.0")

    font = QFont(
        "SF Pro Display",
        13,
    )

    font.setStyleHint(
        QFont.SansSerif
    )

    app.setFont(font)

    # --------------------------------------------------------------
    # Companion server
    # --------------------------------------------------------------

    companion_server = CompanionServer(
        host="0.0.0.0",
        port=8765,
    )

    companion_server.start()

    # --------------------------------------------------------------
    # Main window
    # --------------------------------------------------------------

    window = MainWindow()

    window.show()

    # --------------------------------------------------------------
    # Temporary Companion pairing shortcut
    #
    # Ctrl + Shift + P
    # --------------------------------------------------------------

    pairing_shortcut = QShortcut(
        QKeySequence(
            "Ctrl+Shift+P"
        ),
        window,
    )

    def show_pairing():

        dialog = CompanionPairingDialog(
            companion_server,
            window,
        )

        dialog.exec()

    pairing_shortcut.activated.connect(
        show_pairing
    )

    # --------------------------------------------------------------
    # Shutdown
    # --------------------------------------------------------------

    app.aboutToQuit.connect(
        companion_server.stop
    )

    sys.exit(
        app.exec()
    )


if __name__ == "__main__":
    main()
