"""
Settings Panel — Compute mode, response length, per-agent model config.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QFrame, QComboBox,
    QLineEdit, QSizePolicy
)
from PySide6.QtCore import Qt, Signal

from core.config_loader import (
    get_app_setting, set_app_setting,
    load_agents_config, set_agent_config,
    load_models_config
)
from core.compute_manager import ComputeManager


RESPONSE_LENGTHS = [
    ("concise",  "Concise",  "1-3 sentences. Direct."),
    ("standard", "Standard", "Balanced. Not too long."),
    ("detailed", "Detailed", "Thorough with examples."),
    ("full",     "Full",     "Exhaustive. Leave nothing out."),
]


class SettingsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self.models_config = load_models_config()
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("chat_scroll")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(32)

        # Title
        title = QLabel("Settings")
        title.setObjectName("panel_title")
        layout.addWidget(title)

        layout.addWidget(self._divider())

        # ── Compute Mode ──────────────────────────────────────────
        layout.addWidget(self._section("COMPUTE MODE"))

        compute_desc = QLabel(
            "High: Multiple agents run in parallel (recommended for 8GB+ RAM)\n"
            "Low: One agent at a time — conserves memory (recommended for 4GB RAM)"
        )
        compute_desc.setStyleSheet("color: #5A5A5E; font-size: 12px; line-height: 1.5;")
        compute_desc.setWordWrap(True)
        layout.addWidget(compute_desc)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(10)
        current_mode = get_app_setting("compute_mode", "high")

        self.high_btn = QPushButton("⚡  High Performance")
        self.high_btn.setObjectName("compute_high" if current_mode == "high" else "compute_low")
        self.high_btn.clicked.connect(lambda: self._set_compute("high"))

        self.low_btn = QPushButton("🔋  Low Power")
        self.low_btn.setObjectName("compute_low" if current_mode == "high" else "compute_high")
        self.low_btn.clicked.connect(lambda: self._set_compute("low"))

        mode_row.addWidget(self.high_btn)
        mode_row.addWidget(self.low_btn)
        mode_row.addStretch()
        layout.addLayout(mode_row)

        layout.addWidget(self._divider())

        # ── Response Length ────────────────────────────────────────
        layout.addWidget(self._section("DEFAULT RESPONSE LENGTH"))

        current_length = get_app_setting("response_length", "standard")
        length_row = QHBoxLayout()
        length_row.setSpacing(8)
        self.length_btns = {}

        for key, label, desc in RESPONSE_LENGTHS:
            col = QVBoxLayout()
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(key == current_length)
            btn.setStyleSheet(self._length_style(key == current_length))
            btn.clicked.connect(lambda checked, k=key, b=btn: self._set_length(k))
            self.length_btns[key] = btn

            sub = QLabel(desc)
            sub.setStyleSheet("color: #4A4A4E; font-size: 11px;")
            sub.setAlignment(Qt.AlignCenter)
            sub.setWordWrap(True)
            sub.setMaximumWidth(110)

            col.addWidget(btn)
            col.addWidget(sub)
            length_row.addLayout(col)

        length_row.addStretch()
        layout.addLayout(length_row)

        layout.addWidget(self._divider())

        # ── Per-Agent Config ───────────────────────────────────────
        layout.addWidget(self._section("AGENT CONFIGURATION"))

        self.agents_container = QVBoxLayout()
        self.agents_container.setSpacing(12)
        self._populate_agents()
        layout.addLayout(self.agents_container)

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _populate_agents(self):
        # Clear existing
        while self.agents_container.count():
            item = self.agents_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        agents_cfg = load_agents_config()
        agents = agents_cfg.get("agents", {})

        if not agents:
            empty = QLabel("No agents hired yet. Create one with Ctrl+N.")
            empty.setStyleSheet("color: #3A3A3E; font-size: 12px;")
            self.agents_container.addWidget(empty)
            return

        for name, cfg in agents.items():
            row = self._agent_config_row(name, cfg)
            self.agents_container.addWidget(row)

    def _agent_config_row(self, name: str, cfg: dict) -> QWidget:
        card = QWidget()
        card.setStyleSheet("""
            QWidget {
                background-color: #222226;
                border-radius: 10px;
            }
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # Agent name header
        color = cfg.get("color", "#5B7FA6")
        name_row = QHBoxLayout()
        dot = QWidget()
        dot.setFixedSize(8, 8)
        dot.setStyleSheet(f"background-color: {color}; border-radius: 4px;")
        name_label = QLabel(name)
        name_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #E2E2E2; padding-left: 8px;")

        name_row.addWidget(dot)
        name_row.addWidget(name_label)
        name_row.addStretch()
        layout.addLayout(name_row)

        # Backend + Model dropdowns
        dropdowns_row = QHBoxLayout()
        dropdowns_row.setSpacing(10)

        backend_combo = QComboBox()
        backends = list(self.models_config.get("backends", {}).keys())
        for b in backends:
            label = self.models_config["backends"][b]["label"]
            backend_combo.addItem(label, b)

        current_backend = cfg.get("backend", "ollama")
        idx = backends.index(current_backend) if current_backend in backends else 0
        backend_combo.setCurrentIndex(idx)

        model_combo = QComboBox()
        self._populate_models(model_combo, current_backend, cfg.get("model", ""))

        backend_combo.currentIndexChanged.connect(
            lambda i, mc=model_combo, bc=backend_combo: self._on_backend_change(bc, mc)
        )

        save_btn = QPushButton("Save")
        save_btn.setObjectName("key_save_btn")
        save_btn.clicked.connect(
            lambda checked, n=name, bc=backend_combo, mc=model_combo, c=cfg:
            self._save_agent_config(n, bc, mc, c)
        )

        dropdowns_row.addWidget(QLabel("Backend:"))
        dropdowns_row.addWidget(backend_combo, 1)
        dropdowns_row.addWidget(QLabel("Model:"))
        dropdowns_row.addWidget(model_combo, 2)
        dropdowns_row.addWidget(save_btn)
        layout.addLayout(dropdowns_row)

        # Custom model input (shown only when "custom" is selected)
        self.custom_model_input = QLineEdit()
        self.custom_model_input.setPlaceholderText("Enter model name...")
        self.custom_model_input.setVisible(False)
        layout.addWidget(self.custom_model_input)

        model_combo.currentIndexChanged.connect(
            lambda i, mc=model_combo: self.custom_model_input.setVisible(
                mc.currentData() == "custom"
            )
        )

        return card

    def _populate_models(self, combo: QComboBox, backend: str, current_model: str):
        combo.clear()
        models = self.models_config.get("backends", {}).get(backend, {}).get("models", [])
        for m in models:
            combo.addItem(m["label"], m["id"])
        if current_model:
            for i in range(combo.count()):
                if combo.itemData(i) == current_model:
                    combo.setCurrentIndex(i)
                    break

    def _on_backend_change(self, backend_combo: QComboBox, model_combo: QComboBox):
        backend = backend_combo.currentData()
        self._populate_models(model_combo, backend, "")

    def _save_agent_config(self, name: str, backend_combo: QComboBox,
                           model_combo: QComboBox, existing_cfg: dict):
        backend = backend_combo.currentData()
        model = model_combo.currentData()
        if model == "custom" and self.custom_model_input.text().strip():
            model = self.custom_model_input.text().strip()

        updated = {**existing_cfg, "backend": backend, "model": model}
        set_agent_config(name, updated)

    def _set_compute(self, mode: str):
        ComputeManager().set_mode(mode)
        if mode == "high":
            self.high_btn.setObjectName("compute_high")
            self.low_btn.setObjectName("compute_low")
        else:
            self.high_btn.setObjectName("compute_low")
            self.low_btn.setObjectName("compute_high")
        self.high_btn.style().unpolish(self.high_btn)
        self.high_btn.style().polish(self.high_btn)
        self.low_btn.style().unpolish(self.low_btn)
        self.low_btn.style().polish(self.low_btn)

    def _set_length(self, key: str):
        set_app_setting("response_length", key)
        for k, btn in self.length_btns.items():
            btn.setStyleSheet(self._length_style(k == key))

    def _length_style(self, active: bool) -> str:
        if active:
            return """
                QPushButton {
                    background-color: #2A2A4A;
                    border: 1px solid #3A3A6A;
                    border-radius: 6px;
                    padding: 8px 16px;
                    color: #9A9ACE;
                    font-size: 12px;
                    font-weight: 600;
                }
            """
        return """
            QPushButton {
                background-color: #222226;
                border: 1px solid #2A2A2E;
                border-radius: 6px;
                padding: 8px 16px;
                color: #5A5A5E;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #2A2A2E;
                color: #8A8A8E;
            }
        """

    def _section(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("section_label")
        return label

    def _divider(self) -> QFrame:
        f = QFrame()
        f.setObjectName("divider")
        f.setFrameShape(QFrame.HLine)
        return f

    def refresh(self):
        self._populate_agents()
