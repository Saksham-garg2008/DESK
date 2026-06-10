"""
CodeInspectorPanel — Right-side resizable panel for viewing code artifacts.

Features:
- Filename + language badge
- Version dropdown (v1, v2, v3 with timestamps)
- Copy full file button
- Download file button
- Syntax-highlighted (monospace) code view
- Resizable via draggable splitter
- Close button collapses panel
"""
from pathlib import Path
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QComboBox, QFrame,
    QSizePolicy, QApplication, QFileDialog
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor

from core.artifact_manager import ArtifactManager

LANG_DISPLAY = {
    "python":     "Python",
    "py":         "Python",
    "javascript": "JavaScript",
    "js":         "JavaScript",
    "typescript": "TypeScript",
    "ts":         "TypeScript",
    "html":       "HTML",
    "css":        "CSS",
    "scss":       "SCSS",
    "sass":       "SASS",
    "less":       "LESS",
    "json":       "JSON",
    "yaml":       "YAML",
    "yml":        "YAML",
    "sql":        "SQL",
    "bash":       "Bash",
    "sh":         "Shell",
    "shell":      "Shell",
    "go":         "Go",
    "rust":       "Rust",
    "rs":         "Rust",
    "java":       "Java",
    "kotlin":     "Kotlin",
    "kt":         "Kotlin",
    "swift":      "Swift",
    "cpp":        "C++",
    "c":          "C",
    "cs":         "C#",
    "csharp":     "C#",
    "php":        "PHP",
    "ruby":       "Ruby",
    "rb":         "Ruby",
    "r":          "R",
    "jsx":        "React JSX",
    "tsx":        "React TSX",
    "vue":        "Vue",
    "svelte":     "Svelte",
    "markdown":   "Markdown",
    "md":         "Markdown",
    "toml":       "TOML",
    "xml":        "XML",
    "dockerfile": "Dockerfile",
    "makefile":   "Makefile",
}

LANG_COLORS = {
    "python":     "#4B8BBE",
    "py":         "#4B8BBE",
    "javascript": "#F7DF1E",
    "js":         "#F7DF1E",
    "typescript": "#3178C6",
    "ts":         "#3178C6",
    "html":       "#E44D26",
    "css":        "#264DE4",
    "scss":       "#CD6799",
    "json":       "#92A2BC",
    "yaml":       "#CB171E",
    "yml":        "#CB171E",
    "sql":        "#DAA520",
    "bash":       "#4EAA25",
    "sh":         "#4EAA25",
    "go":         "#00ADD8",
    "rust":       "#CE4B00",
    "rs":         "#CE4B00",
    "java":       "#ED8B00",
    "jsx":        "#61DAFB",
    "tsx":        "#61DAFB",
    "vue":        "#42B883",
    "svelte":     "#FF3E00",
}


class CodeInspectorPanel(QWidget):
    """
    Resizable right-side panel showing a code artifact.
    Emitted closed signal when user closes it.
    """
    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("code_inspector")
        self.setMinimumWidth(280)
        self.setMaximumWidth(900)

        self._agent_name: str = ""
        self._filename: str = ""
        self._current_version: int = 1
        self._artifact: dict = {}

        self._build_ui()
        self.hide()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header bar ────────────────────────────────────────────────────
        header = QWidget()
        header.setObjectName("inspector_header")
        header.setFixedHeight(48)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 0, 12, 0)
        header_layout.setSpacing(8)

        # File icon + name
        self.file_icon = QLabel("📄")
        self.file_icon.setStyleSheet("font-size: 14px;")
        header_layout.addWidget(self.file_icon)

        self.filename_label = QLabel("—")
        self.filename_label.setStyleSheet(
            "font-size: 13px; font-weight: 700; color: #E2E2E8; letter-spacing: -0.2px;"
        )
        header_layout.addWidget(self.filename_label)

        # Language badge
        self.lang_badge = QLabel("")
        self.lang_badge.setStyleSheet(
            "font-size: 10px; font-weight: 700; color: #4B8BBE; "
            "background: #1A2A38; border-radius: 4px; padding: 2px 7px; letter-spacing: 0.5px;"
        )
        header_layout.addWidget(self.lang_badge)
        header_layout.addStretch()

        # Close button
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #404050;
                font-size: 13px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background: #2A2A36;
                color: #A0A0B0;
            }
        """)
        close_btn.clicked.connect(self._close)
        header_layout.addWidget(close_btn)

        layout.addWidget(header)

        # ── Divider ────────────────────────────────────────────────────────
        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setStyleSheet("background: #222228; max-height: 1px;")
        layout.addWidget(div)

        # ── Controls bar ──────────────────────────────────────────────────
        controls = QWidget()
        controls.setObjectName("inspector_controls")
        controls.setFixedHeight(44)
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(14, 0, 14, 0)
        controls_layout.setSpacing(8)

        # Version label
        ver_lbl = QLabel("VERSION")
        ver_lbl.setStyleSheet(
            "font-size: 9px; font-weight: 700; color: #383848; letter-spacing: 1px;"
        )
        controls_layout.addWidget(ver_lbl)

        # Version dropdown
        self.version_combo = QComboBox()
        self.version_combo.setFixedWidth(130)
        self.version_combo.setStyleSheet("""
            QComboBox {
                background: #1E1E26;
                border: 1px solid #2E2E3A;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                color: #A0A0B8;
                min-width: 120px;
            }
            QComboBox:hover { border-color: #3A3A50; }
            QComboBox QAbstractItemView {
                background: #1E1E26;
                border: 1px solid #2E2E3A;
                border-radius: 6px;
                selection-background-color: #2A2A40;
                color: #B0B0C8;
                padding: 4px;
            }
        """)
        self.version_combo.currentIndexChanged.connect(self._on_version_change)
        controls_layout.addWidget(self.version_combo)

        controls_layout.addStretch()

        # Copy button
        self.copy_btn = QPushButton("Copy")
        self.copy_btn.setObjectName("inspector_btn")
        self.copy_btn.setFixedWidth(60)
        self.copy_btn.clicked.connect(self._copy_code)
        controls_layout.addWidget(self.copy_btn)

        # Download button
        self.dl_btn = QPushButton("Download")
        self.dl_btn.setObjectName("inspector_btn")
        self.dl_btn.setFixedWidth(80)
        self.dl_btn.clicked.connect(self._download_code)
        controls_layout.addWidget(self.dl_btn)

        layout.addWidget(controls)

        # ── Divider ────────────────────────────────────────────────────────
        div2 = QFrame()
        div2.setFrameShape(QFrame.HLine)
        div2.setStyleSheet("background: #1E1E24; max-height: 1px;")
        layout.addWidget(div2)

        # ── Code view ─────────────────────────────────────────────────────
        self.code_scroll = QScrollArea()
        self.code_scroll.setObjectName("inspector_scroll")
        self.code_scroll.setWidgetResizable(True)
        self.code_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.code_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.code_scroll.setStyleSheet("""
            QScrollArea {
                background: #12121A;
                border: none;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 5px;
            }
            QScrollBar::handle:vertical {
                background: #2E2E3A;
                border-radius: 2px;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar:horizontal {
                background: transparent;
                height: 5px;
            }
            QScrollBar::handle:horizontal {
                background: #2E2E3A;
                border-radius: 2px;
                min-width: 20px;
            }
            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal { width: 0; }
        """)

        code_container = QWidget()
        code_container.setStyleSheet("background: #12121A;")
        code_layout = QVBoxLayout(code_container)
        code_layout.setContentsMargins(20, 20, 20, 20)

        self.code_label = QLabel()
        self.code_label.setWordWrap(False)
        self.code_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.code_label.setStyleSheet("""
            font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code',
                         'Consolas', 'Monaco', 'Menlo', monospace;
            font-size: 12px;
            color: #C8D8C8;
            line-height: 1.7;
            background: transparent;
        """)
        self.code_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        code_layout.addWidget(self.code_label)
        code_layout.addStretch()

        self.code_scroll.setWidget(code_container)
        layout.addWidget(self.code_scroll, 1)

        # ── Bottom bar (line count etc) ────────────────────────────────────
        footer = QWidget()
        footer.setObjectName("inspector_footer")
        footer.setFixedHeight(28)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 0, 16, 0)

        self.line_count_label = QLabel("")
        self.line_count_label.setStyleSheet(
            "font-size: 10px; color: #2E2E3E; font-family: monospace;"
        )
        footer_layout.addWidget(self.line_count_label)
        footer_layout.addStretch()

        self.saved_label = QLabel("")
        self.saved_label.setStyleSheet("font-size: 10px; color: #2E2E3E;")
        footer_layout.addWidget(self.saved_label)

        layout.addWidget(footer)

    # ── Public API ─────────────────────────────────────────────────────────

    def load_artifact(self, agent_name: str, filename: str):
        """Load an artifact into the inspector."""
        self._agent_name = agent_name
        self._filename = filename
        am = ArtifactManager()
        artifact = am.get_artifact(agent_name, filename)
        if not artifact:
            return

        self._artifact = artifact
        self._current_version = artifact["current_version"]

        # Update header
        self.filename_label.setText(filename)
        lang = artifact.get("language", "")
        lang_display = LANG_DISPLAY.get(lang, lang.upper() if lang else "TEXT")
        lang_color = LANG_COLORS.get(lang, "#7A7A9A")
        self.lang_badge.setText(lang_display)
        self.lang_badge.setStyleSheet(
            f"font-size: 10px; font-weight: 700; color: {lang_color}; "
            f"background: #1E1E28; border-radius: 4px; padding: 2px 7px; letter-spacing: 0.5px;"
        )

        # Populate version dropdown
        self.version_combo.blockSignals(True)
        self.version_combo.clear()
        versions = artifact.get("versions", [])
        current_idx = 0
        for i, ver in enumerate(versions):
            v_num = ver["v"]
            ts = ver.get("timestamp", "")
            try:
                dt = datetime.fromisoformat(ts)
                ts_str = dt.strftime("%b %d, %H:%M")
            except Exception:
                ts_str = ts[:16] if ts else ""
            label = f"v{v_num}  ·  {ts_str}"
            self.version_combo.addItem(label, v_num)
            if v_num == self._current_version:
                current_idx = i

        self.version_combo.setCurrentIndex(current_idx)
        self.version_combo.blockSignals(False)

        # Load code content
        self._load_version_content(self._current_version)
        self.show()

    def refresh_current(self):
        """Reload artifact data (call after new version is saved)."""
        if self._agent_name and self._filename:
            self.load_artifact(self._agent_name, self._filename)

    # ── Internal ───────────────────────────────────────────────────────────

    def _on_version_change(self, idx: int):
        v_num = self.version_combo.currentData()
        if v_num:
            self._current_version = v_num
            self._load_version_content(v_num)

    def _load_version_content(self, version: int):
        am = ArtifactManager()
        content = am.get_version_content(self._agent_name, self._filename, version)

        # Show as plain text (monospace)
        self.code_label.setTextFormat(Qt.PlainText)
        self.code_label.setText(content)

        # Footer stats
        lines = content.count("\n") + 1 if content else 0
        chars = len(content)
        self.line_count_label.setText(f"{lines} lines  ·  {chars} chars")

        # Saved timestamp
        for ver in self._artifact.get("versions", []):
            if ver["v"] == version:
                ts = ver.get("timestamp", "")
                try:
                    dt = datetime.fromisoformat(ts)
                    self.saved_label.setText(dt.strftime("Saved %b %d at %H:%M"))
                except Exception:
                    self.saved_label.setText("")
                break

    def _copy_code(self):
        am = ArtifactManager()
        content = am.get_version_content(
            self._agent_name, self._filename, self._current_version
        )
        QApplication.clipboard().setText(content)

        # Brief visual feedback
        self.copy_btn.setText("Copied!")
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1500, lambda: self.copy_btn.setText("Copy"))

    def _download_code(self):
        am = ArtifactManager()
        content = am.get_version_content(
            self._agent_name, self._filename, self._current_version
        )
        default_path = str(Path.home() / self._filename)
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save File", default_path, "All Files (*)"
        )
        if save_path:
            Path(save_path).write_text(content, encoding="utf-8")

    def _close(self):
        self.hide()
        self.closed.emit()
