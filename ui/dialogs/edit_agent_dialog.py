"""
EditAgentDialog — Right-click an agent strip to edit everything.
Name, system prompt, color, backend, model.
"""
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTextEdit, QPushButton, QWidget, QComboBox, QFrame
)
from PySide6.QtCore import Qt, Signal

from core.config_loader import (
    get_agent_config, set_agent_config, load_models_config,
    delete_agent_config
)

BUCKET_DIR = Path(__file__).parent.parent.parent / "bucket"

AGENT_COLORS = [
    "#5B7FA6", "#7A6FA6", "#A67A6F", "#6FA67A",
    "#A6A06F", "#6FA0A6", "#A66F7A", "#7AA6A0",
    "#1C1C1E", "#4A4A6A", "#6A4A4A", "#4A6A4A",
    "#8A7A5A", "#5A6A8A", "#8A5A6A", "#5A8A7A",
]


class EditAgentDialog(QDialog):
    agent_updated = Signal(str, str, str)  # old_name, new_name, color

    def __init__(self, agent_name: str, parent=None):
        super().__init__(parent)
        self.original_name = agent_name
        self.setWindowTitle(f"Edit {agent_name}")
        self.setMinimumWidth(480)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)

        self.models_config = load_models_config()
        cfg = get_agent_config(agent_name)
        self.selected_color = cfg.get("color", AGENT_COLORS[0])
        self._current_backend = cfg.get("backend", "ollama")
        self._current_model   = cfg.get("model", "")

        md_path = BUCKET_DIR / f"{agent_name}.md"
        self._current_prompt = md_path.read_text(encoding="utf-8") if md_path.exists() else ""

        self._build_ui(cfg)

    def _build_ui(self, cfg: dict):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(18)

        # Title row
        title_row = QHBoxLayout()
        title = QLabel(f"Edit Agent")
        title.setObjectName("dialog_title")
        title_row.addWidget(title)
        title_row.addStretch()

        # Colored dot showing current color
        self.dot_preview = QWidget()
        self.dot_preview.setFixedSize(14, 14)
        self.dot_preview.setStyleSheet(
            f"background-color:{self.selected_color};border-radius:7px;"
        )
        title_row.addWidget(self.dot_preview)
        layout.addLayout(title_row)

        # ── Name ──────────────────────────────────────────────────────
        layout.addWidget(self._lbl("AGENT NAME"))
        self.name_input = QLineEdit(self.original_name)
        layout.addWidget(self.name_input)

        # ── System Prompt ──────────────────────────────────────────────
        layout.addWidget(self._lbl("SYSTEM PROMPT"))
        self.prompt_input = QTextEdit()
        self.prompt_input.setPlainText(self._current_prompt)
        self.prompt_input.setMinimumHeight(100)
        self.prompt_input.setMaximumHeight(160)
        layout.addWidget(self.prompt_input)

        # ── Color ──────────────────────────────────────────────────────
        layout.addWidget(self._lbl("TAB COLOR"))
        self.color_swatches = []
        swatch_row = QHBoxLayout()
        swatch_row.setSpacing(8)
        swatch_row.setContentsMargins(0, 0, 0, 0)
        for color in AGENT_COLORS:
            btn = QPushButton()
            btn.setFixedSize(22, 22)
            btn.setStyleSheet(self._swatch_style(color, color == self.selected_color))
            btn.clicked.connect(lambda _, c=color: self._pick_color(c))
            swatch_row.addWidget(btn)
            self.color_swatches.append((btn, color))
        swatch_row.addStretch()
        layout.addLayout(swatch_row)

        # ── Provider & Model ───────────────────────────────────────────
        div = QFrame()
        div.setObjectName("divider")
        div.setFrameShape(QFrame.HLine)
        layout.addWidget(div)

        layout.addWidget(self._lbl("PROVIDER"))
        self.backend_combo = QComboBox()
        backends = self.models_config.get("backends", {})
        current_backend_idx = 0
        for i, (key, info) in enumerate(backends.items()):
            self.backend_combo.addItem(info["label"], key)
            if key == self._current_backend:
                current_backend_idx = i
        self.backend_combo.setCurrentIndex(current_backend_idx)
        self.backend_combo.currentIndexChanged.connect(self._on_backend_change)
        layout.addWidget(self.backend_combo)

        layout.addWidget(self._lbl("MODEL"))
        self.model_combo = QComboBox()
        self._populate_models(self._current_backend, self._current_model)
        layout.addWidget(self.model_combo)

        self.custom_model = QLineEdit()
        self.custom_model.setPlaceholderText("Enter model name e.g. gpt-4o-mini")
        self.custom_model.setVisible(self._current_model == "custom")
        layout.addWidget(self.custom_model)

        self.model_combo.currentIndexChanged.connect(
            lambda _: self.custom_model.setVisible(
                self.model_combo.currentData() == "custom"
            )
        )

        # ── Buttons ────────────────────────────────────────────────────
        layout.addSpacing(4)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("dialog_secondary")
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("Save Changes")
        save_btn.setObjectName("dialog_primary")
        save_btn.clicked.connect(self._save)

        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _on_backend_change(self, _=None):
        backend = self.backend_combo.currentData()
        self._populate_models(backend, "")

    def _populate_models(self, backend: str, current_model: str):
        self.model_combo.clear()
        models = self.models_config.get("backends", {}).get(backend, {}).get("models", [])
        selected_idx = 0
        for i, m in enumerate(models):
            self.model_combo.addItem(m["label"], m["id"])
            if m["id"] == current_model:
                selected_idx = i
        self.model_combo.setCurrentIndex(selected_idx)

    def _pick_color(self, color: str):
        self.selected_color = color
        self.dot_preview.setStyleSheet(
            f"background-color:{color};border-radius:7px;"
        )
        for btn, c in self.color_swatches:
            btn.setStyleSheet(self._swatch_style(c, c == color))

    def _save(self):
        new_name   = self.name_input.text().strip()
        new_prompt = self.prompt_input.toPlainText().strip()

        if not new_name:
            self.name_input.setStyleSheet(
                self.name_input.styleSheet() + "border:1px solid #7A3A3E;"
            )
            return

        backend = self.backend_combo.currentData()
        model   = self.model_combo.currentData()
        if model == "custom":
            model = self.custom_model.text().strip() or self._current_model

        # If name changed: rename .md file, migrate config
        old_md = BUCKET_DIR / f"{self.original_name}.md"
        new_md = BUCKET_DIR / f"{new_name}.md"

        if self.original_name != new_name:
            # Rename bucket file
            if old_md.exists():
                old_md.rename(new_md)
            # Migrate history file
            from core.history_manager import _agent_path
            old_hist = _agent_path(self.original_name)
            if old_hist.exists():
                old_hist.rename(_agent_path(new_name))
            # Delete old config entry
            delete_agent_config(self.original_name)
        else:
            # Just overwrite the .md
            new_md.write_text(new_prompt, encoding="utf-8")

        # Write new .md content (covers rename case too)
        new_md.write_text(new_prompt, encoding="utf-8")

        # Save updated config
        existing = get_agent_config(self.original_name) or {}
        set_agent_config(new_name, {
            **existing,
            "color":           self.selected_color,
            "backend":         backend,
            "model":           model,
            "system_prompt":   new_prompt,
            "response_length": existing.get("response_length", "standard"),
        })

        self.agent_updated.emit(self.original_name, new_name, self.selected_color)
        self.accept()

    def _lbl(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("dialog_label")
        return lbl

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
