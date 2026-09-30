"""
DESK — Entry Point
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from ui.main_window import MainWindow
from core.paths import initialize_data_directory


def main():
    initialize_data_directory()
    app = QApplication(sys.argv)
    app.setApplicationName("DESK")
    app.setApplicationVersion("2.1.0")
    # AA_UseHighDpiPixmaps is deprecated and auto-enabled in Qt6 — removed

    font = QFont("SF Pro Display", 13)
    font.setStyleHint(QFont.SansSerif)
    app.setFont(font)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
