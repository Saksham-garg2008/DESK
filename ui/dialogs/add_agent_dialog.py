"""
New Agent Dialog — Two-step hire flow.
Step 1: Name + System Prompt + Color
Step 2: Provider + Model (the nudge to configure before chatting)
"""
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTextEdit, QPushButton, QWidget, QFileDialog, QFrame,
    QComboBox, QStackedWidget
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QColor

from core.config_loader import set_agent_config, load_models_config

BUCKET_DIR = Path(__file__).parent.parent.parent / "bucket"

AGENT_COLORS = [
    "#5B7FA6",  # Slate Blue
    "#7A6FA6",  # Soft Purple
    "#A67A6F",  # Terracotta
    "#6FA67A",  # Sage Green
    "#A6A06F",  # Warm Gold
    "#6FA0A6",  # Teal
    "#A66F7A",  # Dusty Rose
    "#7AA6A0",  # Seafoam
    "#1C1C1E",  # Batman Black
    "#4A4A6A",  # Deep Indigo
    "#6A4A4A",  # Deep Crimson
    "#4A6A4A",  # Forest
    "#8A7A5A",  # Bronze
    "#5A6A8A",  # Steel
    "#8A5A6A",  # Mauve
    "#5A8A7A",  # Emerald
]


class DropZone(QWidget):
    file_dropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(70)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        self.label = QLabel("Drop .md file here  ·  or click to browse")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("color: #4A4A5E; font-size: 12px;")
        layout.addWidget(self.label)

        self._base_style = """
            QWidget {
                border: 1px dashed #353540;
                border-radius: 10px;
                background-color: #1E1E24;
            }
        """
        self._hover_style = """
            QWidget {
                border: 1px dashed #5A5A7E;
                border-radius: 10px;
                background-color: #22222C;
            }
        """
        self.setStyleSheet(self._base_style)

    def mousePressEvent(self, event):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Agent .md file", str(Path.home()), "Markdown (*.md)"
        )
        if path:
            self.file_dropped.emit(path)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and urls[0].toLocalFile().endswith(".md"):
                event.acceptProposedAction()
                self.setStyleSheet(self._hover_style)

    def dragLeaveEvent(self, event):
        self.setStyleSheet(self._base_style)

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if path.endswith(".md"):
                self.file_dropped.emit(path)
        self.setStyleSheet(self._base_style)


class NewAgentDialog(QDialog):
    agent_created = Signal(str, str)  # name, color

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Agent")
        self.setMinimumWidth(480)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.selected_color = AGENT_COLORS[0]
        self.models_config = load_models_config()
        self._agent_name = ""
        self._system_prompt = ""
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Progress indicator
        self.progress_bar = self._build_progress()
        root.addWidget(self.progress_bar)

        # Stacked pages
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_step1())
        self.stack.addWidget(self._build_step2())
        root.addWidget(self.stack)

    def _build_progress(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(3)
        bar.setStyleSheet("background-color: #222226;")

        self.progress_fill = QWidget(bar)
        self.progress_fill.setFixedHeight(3)
        self.progress_fill.setStyleSheet("background-color: #5B7FA6; border-radius: 1px;")
        self.progress_fill.setFixedWidth(0)

        return bar

    def _set_progress(self, step: int):
        total = 2
        width = int((step / total) * self.progress_bar.width())
        self.progress_fill.setFixedWidth(width)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Keep progress fill correct on resize
        current_step = self.stack.currentIndex() + 1
        self._set_progress(current_step)

    # ── Step 1: Identity ─────────────────────────────────────────────────

    def _build_step1(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(18)

        # Header
        header_row = QHBoxLayout()
        step_pill = QLabel("STEP 1 OF 2")
        step_pill.setStyleSheet(
            "font-size: 10px; font-weight: 700; color: #4A4A5E; letter-spacing: 1px;"
        )
        header_row.addWidget(step_pill)
        header_row.addStretch()
        layout.addLayout(header_row)

        title = QLabel("Identity")
        title.setObjectName("dialog_title")
        sub = QLabel("Name your agent and define their purpose.")
        sub.setStyleSheet("font-size: 12px; color: #4A4A5E;")
        layout.addWidget(title)
        layout.addWidget(sub)

        # Drop zone
        drop = DropZone()
        drop.file_dropped.connect(self._load_md_file)
        layout.addWidget(drop)

        # OR divider
        or_row = QHBoxLayout()
        for side in [QFrame(), QFrame()]:
            side.setFrameShape(QFrame.HLine)
            side.setStyleSheet("color: #2A2A2E; margin-top: 6px;")
        left_line = QFrame()
        left_line.setFrameShape(QFrame.HLine)
        left_line.setStyleSheet("background-color: #2A2A2E; max-height:1px;")
        or_lbl = QLabel("or write manually")
        or_lbl.setStyleSheet("color: #333338; font-size: 11px; padding: 0 12px;")
        or_lbl.setAlignment(Qt.AlignCenter)
        right_line = QFrame()
        right_line.setFrameShape(QFrame.HLine)
        right_line.setStyleSheet("background-color: #2A2A2E; max-height:1px;")
        or_row.addWidget(left_line)
        or_row.addWidget(or_lbl)
        or_row.addWidget(right_line)
        layout.addLayout(or_row)

        # Name
        layout.addWidget(self._field_label("AGENT NAME"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Alfred, Coder, Strategist…")
        layout.addWidget(self.name_input)

        # Prompt
        layout.addWidget(self._field_label("SYSTEM PROMPT"))
        self.prompt_input = QTextEdit()
        self.prompt_input.setPlaceholderText(
            "You are Alfred, a loyal and resourceful assistant…"
        )
        self.prompt_input.setMinimumHeight(90)
        self.prompt_input.setMaximumHeight(130)
        layout.addWidget(self.prompt_input)

        # Color
        layout.addWidget(self._field_label("TAB COLOR"))
        self.color_swatches = []
        swatch_row = QHBoxLayout()
        swatch_row.setSpacing(8)
        swatch_row.setContentsMargins(0, 0, 0, 0)
        for i, color in enumerate(AGENT_COLORS):
            btn = QPushButton()
            btn.setFixedSize(22, 22)
            btn.setStyleSheet(self._swatch_style(color, i == 0))
            btn.clicked.connect(lambda _, c=color: self._pick_color(c))
            swatch_row.addWidget(btn)
            self.color_swatches.append((btn, color))
        swatch_row.addStretch()
        layout.addLayout(swatch_row)

        # Next button
        layout.addSpacing(4)
        next_btn = QPushButton("Next: Choose Model  →")
        next_btn.setObjectName("dialog_primary")
        next_btn.clicked.connect(self._go_step2)
        layout.addWidget(next_btn, alignment=Qt.AlignRight)

        return page

    # ── Step 2: Provider & Model ──────────────────────────────────────────

    def _build_step2(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(18)

        # Header
        header_row = QHBoxLayout()
        step_pill = QLabel("STEP 2 OF 2")
        step_pill.setStyleSheet(
            "font-size: 10px; font-weight: 700; color: #4A4A5E; letter-spacing: 1px;"
        )
        back_btn = QPushButton("← Back")
        back_btn.setObjectName("dialog_secondary")
        back_btn.setFixedHeight(28)
        back_btn.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        header_row.addWidget(step_pill)
        header_row.addStretch()
        header_row.addWidget(back_btn)
        layout.addLayout(header_row)

        title = QLabel("Intelligence")
        title.setObjectName("dialog_title")
        sub = QLabel("Choose the AI brain powering this agent.")
        sub.setStyleSheet("font-size: 12px; color: #4A4A5E;")
        layout.addWidget(title)
        layout.addWidget(sub)

        # Preview of agent being created
        self.agent_preview = QWidget()
        self.agent_preview.setFixedHeight(44)
        self.agent_preview.setStyleSheet(
            "background-color: #1E1E24; border-radius: 10px; border: 1px solid #2A2A30;"
        )
        prev_layout = QHBoxLayout(self.agent_preview)
        prev_layout.setContentsMargins(14, 0, 14, 0)
        self.preview_dot = QWidget()
        self.preview_dot.setFixedSize(10, 10)
        self.preview_dot.setStyleSheet(
            f"background-color:{self.selected_color};border-radius:5px;"
        )
        self.preview_name = QLabel("—")
        self.preview_name.setStyleSheet(
            "font-size:13px; font-weight:600; color:#E2E2E2; padding-left:8px;"
        )
        prev_layout.addWidget(self.preview_dot)
        prev_layout.addWidget(self.preview_name)
        prev_layout.addStretch()
        layout.addWidget(self.agent_preview)

        # Backend
        layout.addWidget(self._field_label("PROVIDER"))
        self.backend_combo = QComboBox()
        backends = self.models_config.get("backends", {})
        for key, info in backends.items():
            self.backend_combo.addItem(info["label"], key)
        self.backend_combo.currentIndexChanged.connect(self._on_backend_change)
        layout.addWidget(self.backend_combo)

        # Model
        layout.addWidget(self._field_label("MODEL"))
        self.model_combo = QComboBox()
        layout.addWidget(self.model_combo)

        # Custom model input
        self.custom_model = QLineEdit()
        self.custom_model.setPlaceholderText("Enter model name e.g. gpt-4o-mini")
        self.custom_model.setVisible(False)
        layout.addWidget(self.custom_model)

        self.model_combo.currentIndexChanged.connect(
            lambda _: self.custom_model.setVisible(
                self.model_combo.currentData() == "custom"
            )
        )

        # Populate initial models
        self._on_backend_change(0)

        # Free tier note
        self.free_note = QLabel("💡 Models marked (FREE) have no cost but may have rate limits.")
        self.free_note.setStyleSheet("font-size: 11px; color: #4A6A4A;")
        self.free_note.setWordWrap(True)
        layout.addWidget(self.free_note)

        layout.addStretch()

        # Hire button
        hire_btn = QPushButton("Hire Agent ✓")
        hire_btn.setObjectName("dialog_primary")
        hire_btn.clicked.connect(self._hire)
        layout.addWidget(hire_btn, alignment=Qt.AlignRight)

        return page

    def _on_backend_change(self, _=None):
        backend = self.backend_combo.currentData()
        self.model_combo.clear()
        models = self.models_config.get("backends", {}).get(backend, {}).get("models", [])
        for m in models:
            self.model_combo.addItem(m["label"], m["id"])

    def _go_step2(self):
        name = self.name_input.text().strip()
        prompt = self.prompt_input.toPlainText().strip()

        if not name:
            self.name_input.setStyleSheet(
                self.name_input.styleSheet() + "border: 1px solid #7A3A3E;"
            )
            return
        if not prompt:
            self.prompt_input.setStyleSheet(
                self.prompt_input.styleSheet() + "border: 1px solid #7A3A3E;"
            )
            return

        self._agent_name = name
        self._system_prompt = prompt

        # Update preview
        self.preview_name.setText(name)
        self.preview_dot.setStyleSheet(
            f"background-color:{self.selected_color};border-radius:5px;"
        )

        self.stack.setCurrentIndex(1)
        self._set_progress(2)

    def _hire(self):
        backend = self.backend_combo.currentData()
        model = self.model_combo.currentData()
        if model == "custom":
            model = self.custom_model.text().strip() or "llama3.2:3b"

        md_path = BUCKET_DIR / f"{self._agent_name}.md"
        BUCKET_DIR.mkdir(exist_ok=True)
        md_path.write_text(self._system_prompt, encoding="utf-8")

        set_agent_config(self._agent_name, {
            "color": self.selected_color,
            "backend": backend,
            "model": model,
            "response_length": "standard",
            "system_prompt": self._system_prompt,
        })

        self.agent_created.emit(self._agent_name, self.selected_color)
        self.accept()

    def _load_md_file(self, path: str):
        p = Path(path)
        self.name_input.setText(p.stem)
        self.prompt_input.setPlainText(p.read_text(encoding="utf-8"))

    def _pick_color(self, color: str):
        self.selected_color = color
        for btn, c in self.color_swatches:
            btn.setStyleSheet(self._swatch_style(c, c == color))

    def _swatch_style(self, color: str, selected: bool) -> str:
        border = "#FFFFFF" if selected else "transparent"
        return f"""
            QPushButton {{
                background-color: {color};
                border-radius: 11px;
                border: 2px solid {border};
            }}
            QPushButton:hover {{ border: 2px solid rgba(255,255,255,0.5); }}
        """

    def _field_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("dialog_label")
        return lbl
