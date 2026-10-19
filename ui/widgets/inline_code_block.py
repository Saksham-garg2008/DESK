
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QPlainTextEdit,
    QApplication,
    QSizePolicy,
)
from PySide6.QtCore import Qt, QTimer


class InlineCodeBlock(QWidget):
    """
    Displays an inline-code snippet in a separate, scrollable block.

    Features:
    - Independent horizontal and vertical scrollbars
    - One-click copy action
    - Language label
    - Read-only code content
    """

    def __init__(self, code: str, lang: str = "", parent=None):
        super().__init__(parent)

        self._code = code
        self._build_ui(lang)

    def _build_ui(self, lang: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(0)

        # Main container
        container = QWidget(self)
        container.setObjectName("inline_code_container")
        container.setStyleSheet("""
            QWidget#inline_code_container {
                background: #1A1A22;
                border: 1px solid #252530;
                border-radius: 8px;
            }
        """)

        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # Header
        header = QWidget(container)
        header.setObjectName("inline_code_header")
        header.setFixedHeight(32)
        header.setStyleSheet("""
            QWidget#inline_code_header {
                background: #16161E;
                border: none;
                border-bottom: 1px solid #252530;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
        """)

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 0, 8, 0)
        header_layout.setSpacing(8)

        language_label = QLabel(lang.upper() if lang else "CODE")
        language_label.setStyleSheet("""
            background: transparent;
            border: none;
            color: #686880;
            font-family: monospace;
            font-size: 9px;
            font-weight: 700;
        """)
        header_layout.addWidget(language_label)
        header_layout.addStretch()

        self.copy_btn = QPushButton("Copy")
        self.copy_btn.setCursor(Qt.PointingHandCursor)
        self.copy_btn.setFixedHeight(22)
        self.copy_btn.setStyleSheet("""
            QPushButton {
                background: #22222E;
                border: 1px solid #2E2E3A;
                border-radius: 4px;
                padding: 0 8px;
                color: #A0A0B8;
                font-size: 10px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #2A2A3A;
                color: #D0D0E8;
            }
        """)
        self.copy_btn.clicked.connect(self._copy)
        header_layout.addWidget(self.copy_btn)

        container_layout.addWidget(header)

        # Read-only code editor.
        # No line wrapping means long lines use the horizontal scrollbar.
        self.code_edit = QPlainTextEdit()
        self.code_edit.setObjectName("inline_code_content")
        self.code_edit.setPlainText(self._code)
        self.code_edit.setReadOnly(True)
        self.code_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.code_edit.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.code_edit.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.code_edit.setMinimumHeight(48)
        self.code_edit.setMaximumHeight(220)
        self.code_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self.code_edit.setStyleSheet("""
            QPlainTextEdit#inline_code_content {
                background: #1A1A22;
                border: none;
                border-bottom-left-radius: 8px;
                border-bottom-right-radius: 8px;
                padding: 8px 10px;
                color: #A8D8A8;
                selection-background-color: #34344A;
                selection-color: #E0E0F0;
                font-family: "JetBrains Mono", "Fira Code",
                             "Cascadia Code", "Consolas", monospace;
                font-size: 12px;
            }

            QPlainTextEdit QScrollBar:vertical {
                background: #1A1A22;
                width: 9px;
                margin: 2px;
                border: none;
            }
            QPlainTextEdit QScrollBar::handle:vertical {
                background: #414154;
                min-height: 20px;
                border-radius: 4px;
            }
            QPlainTextEdit QScrollBar::handle:vertical:hover {
                background: #606078;
            }
            QPlainTextEdit QScrollBar::add-line:vertical,
            QPlainTextEdit QScrollBar::sub-line:vertical {
                height: 0;
            }

            QPlainTextEdit QScrollBar:horizontal {
                background: #1A1A22;
                height: 9px;
                margin: 2px;
                border: none;
            }
            QPlainTextEdit QScrollBar::handle:horizontal {
                background: #414154;
                min-width: 20px;
                border-radius: 4px;
            }
            QPlainTextEdit QScrollBar::handle:horizontal:hover {
                background: #606078;
            }
            QPlainTextEdit QScrollBar::add-line:horizontal,
            QPlainTextEdit QScrollBar::sub-line:horizontal {
                width: 0;
            }
        """)

        container_layout.addWidget(self.code_edit)
        layout.addWidget(container)

        self.setMaximumWidth(660)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

    def _copy(self):
        QApplication.clipboard().setText(self._code)

        self.copy_btn.setText("Copied!")
        self.copy_btn.setEnabled(False)

        QTimer.singleShot(1200, self._restore_copy_button)

    def _restore_copy_button(self):
        self.copy_btn.setText("Copy")
        self.copy_btn.setEnabled(True)
