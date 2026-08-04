"""
MemoryPanel — View and edit each agent's distilled long-term memory.

Same shape as the Workspace panel: agent list on the left, content on the
right. Unlike the Workspace/Code Inspector panels (which show generated
artifacts), this panel shows workspace/memory/<agent>.md — the condensed
"what this agent has learned" file that gets auto-updated by the Memory
Agent after every few exchanges (see chat_panel.py + memory_manager.py).

Two actions on the right side:
- Save    — plain file write. No LLM call. User edits are final, at their
            own risk (this is the "you have access to his brain, edit at
            your own risk" model).
- Regenerate — forces a fresh distillation pass right now, using the
            agent's full recent history, overwriting the current memory
            file. This is a real LLM call and can take a moment on local
            models, so the button disables itself and shows progress
            while running.
"""
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QTextEdit, QSplitter, QFrame,
    QSizePolicy, QComboBox, QLineEdit
)
from PySide6.QtCore import Qt, Signal

from core.config_loader import (
    load_agents_config, get_agent_config, load_models_config,
    get_memory_agent_config, set_memory_agent_config,
)
from core.history_manager import load_history
from core.compute_manager import ComputeManager, InferenceWorker
from core.inference_manager import InferenceManager
from core.memory_manager import (
    load_memory, save_memory, memory_exists, blank_memory,
    build_distillation_prompt, clean_distillation_output,
)


class MemoryAgentListItem(QWidget):
    """One row in the left-hand agent list — color dot + name + a small
    dot indicating whether memory exists yet for that agent."""

    def __init__(self, name: str, color: str, has_memory: bool, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)

        dot = QWidget()
        dot.setFixedSize(8, 8)
        dot.setStyleSheet(f"background-color:{color}; border-radius:4px;")
        layout.addWidget(dot)

        name_lbl = QLabel(name)
        name_lbl.setStyleSheet("font-size:13px; font-weight:600; color:#D8D8DE;")
        layout.addWidget(name_lbl)
        layout.addStretch()

        status = QLabel("●" if has_memory else "○")
        status.setStyleSheet(
            f"font-size:9px; color:{'#6ABF7A' if has_memory else '#3A3A3E'};"
        )
        status.setToolTip("Has memory" if has_memory else "No memory yet")
        layout.addWidget(status)


class MemoryPanel(QWidget):
    """
    Top-level Memory panel. Constructed once by main_window.py (same
    pattern as WorkspacePanel) and refreshed whenever agents change.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self.models_config = load_models_config()
        self._current_agent: str | None = None
        self._regen_worker = None
        self._regen_buffer = ""
        self._build_ui()
        self.refresh()

    # ── UI ────────────────────────────────────────────────────────────────

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = self._build_header()
        outer.addWidget(header)

        outer.addWidget(self._build_memory_agent_picker())

        div = QFrame()
        div.setObjectName("divider")
        div.setFrameShape(QFrame.HLine)
        outer.addWidget(div)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("QSplitter::handle { background-color: #222228; }")

        # ── Left: agent list ────────────────────────────────────────────
        left = QWidget()
        left.setMinimumWidth(220)
        left.setMaximumWidth(280)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        list_title = QLabel("AGENTS")
        list_title.setObjectName("section_label")
        list_title.setContentsMargins(16, 16, 16, 8)
        left_layout.addWidget(list_title)

        self.agent_list = QListWidget()
        self.agent_list.setObjectName("chat_scroll")
        self.agent_list.setStyleSheet("""
            QListWidget { background: transparent; border: none; }
            QListWidget::item { border-bottom: 1px solid #1E1E24; }
            QListWidget::item:selected { background-color: #222230; }
            QListWidget::item:hover { background-color: #1C1C22; }
        """)
        self.agent_list.itemClicked.connect(self._on_agent_selected)
        left_layout.addWidget(self.agent_list, 1)

        splitter.addWidget(left)

        # ── Right: memory content ──────────────────────────────────────
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(24, 20, 24, 20)
        right_layout.setSpacing(12)

        self.content_header_row = QHBoxLayout()
        self.content_title = QLabel("Select an agent")
        self.content_title.setStyleSheet(
            "font-size:16px; font-weight:700; color:#E2E2E2;"
        )
        self.content_header_row.addWidget(self.content_title)
        self.content_header_row.addStretch()

        self.regenerate_btn = QPushButton("↻  Regenerate")
        self.regenerate_btn.setObjectName("key_save_btn")
        self.regenerate_btn.setToolTip(
            "Force a fresh memory update now, using recent conversation history."
        )
        self.regenerate_btn.clicked.connect(self._on_regenerate)
        self.regenerate_btn.setEnabled(False)
        self.content_header_row.addWidget(self.regenerate_btn)

        self.save_btn = QPushButton("Save")
        self.save_btn.setObjectName("dialog_primary")
        self.save_btn.clicked.connect(self._on_save)
        self.save_btn.setEnabled(False)
        self.content_header_row.addWidget(self.save_btn)

        right_layout.addLayout(self.content_header_row)

        self.updated_lbl = QLabel("")
        self.updated_lbl.setStyleSheet("font-size:11px; color:#4A4A4E;")
        right_layout.addWidget(self.updated_lbl)

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("font-size:11px; color:#6ABF7A;")
        self.status_lbl.setVisible(False)
        right_layout.addWidget(self.status_lbl)

        self.editor = QTextEdit()
        self.editor.setPlaceholderText(
            "Select an agent on the left to view or edit their memory."
        )
        self.editor.setEnabled(False)
        self.editor.setStyleSheet("""
            QTextEdit {
                background-color: #1A1A1F;
                border: 1px solid #26262E;
                border-radius: 10px;
                padding: 16px;
                font-family: "SF Mono", Menlo, monospace;
                font-size: 12px;
                color: #D0D0D8;
                line-height: 1.6;
            }
            QTextEdit:focus { border-color: #3A3A48; }
        """)
        right_layout.addWidget(self.editor, 1)

        hint = QLabel(
            "Memory updates automatically after every few exchanges. "
            "You can edit it directly here — changes are saved as plain text, no AI involved."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("font-size:11px; color:#3A3A3E;")
        right_layout.addWidget(hint)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        outer.addWidget(splitter, 1)

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("topbar")
        header.setFixedHeight(44)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 0, 20, 0)

        title = QLabel("🧠  Agent Memory")
        title.setStyleSheet("font-size:13px; font-weight:600; color:#E2E2E2;")
        hl.addWidget(title)
        hl.addStretch()
        return header

    def _build_memory_agent_picker(self) -> QWidget:
        """
        The global Memory Agent backend/model picker — the lightweight
        model used to distill every agent's memory in the background.
        Lives at the top of this panel so it's visible the moment the
        panel opens, no separate popover needed.
        """
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(8)

        desc = QLabel(
            "The lightweight model that writes every agent's memory in the "
            "background. Keep this small — it's janitorial work, not a "
            "personality. Falls back to each agent's own model if unset."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size:11px; color:#5A5A5E; line-height:1.5;")
        layout.addWidget(desc)

        row = QHBoxLayout()
        row.setSpacing(10)

        mem_cfg = get_memory_agent_config()

        self.memory_backend_combo = QComboBox()
        backends = list(self.models_config.get("backends", {}).keys())
        for b in backends:
            label = self.models_config["backends"][b]["label"]
            self.memory_backend_combo.addItem(label, b)

        current_backend = mem_cfg.get("backend", "ollama")
        idx = backends.index(current_backend) if current_backend in backends else 0
        self.memory_backend_combo.setCurrentIndex(idx)

        self.memory_model_combo = QComboBox()
        self._populate_memory_models(current_backend, mem_cfg.get("model", ""))

        self.memory_backend_combo.currentIndexChanged.connect(
            lambda i: self._populate_memory_models(
                self.memory_backend_combo.currentData(), ""
            )
        )

        save_btn = QPushButton("Save")
        save_btn.setObjectName("key_save_btn")
        save_btn.clicked.connect(self._save_memory_agent)

        row.addWidget(QLabel("Backend:"))
        row.addWidget(self.memory_backend_combo, 1)
        row.addWidget(QLabel("Model:"))
        row.addWidget(self.memory_model_combo, 2)
        row.addWidget(save_btn)
        layout.addLayout(row)

        self.memory_custom_input = QLineEdit()
        self.memory_custom_input.setPlaceholderText("Enter model name...")
        self.memory_custom_input.setVisible(self.memory_model_combo.currentData() == "custom")
        layout.addWidget(self.memory_custom_input)

        self.memory_model_combo.currentIndexChanged.connect(
            lambda i: self.memory_custom_input.setVisible(
                self.memory_model_combo.currentData() == "custom"
            )
        )

        self.memory_agent_saved_lbl = QLabel("")
        self.memory_agent_saved_lbl.setStyleSheet("font-size:11px; color:#6ABF7A;")
        self.memory_agent_saved_lbl.setVisible(False)
        layout.addWidget(self.memory_agent_saved_lbl)

        return wrapper

    def _populate_memory_models(self, backend: str, current_model: str):
        self.memory_model_combo.clear()
        models = self.models_config.get("backends", {}).get(backend, {}).get("models", [])
        for m in models:
            self.memory_model_combo.addItem(m["label"], m["id"])
        if current_model:
            for i in range(self.memory_model_combo.count()):
                if self.memory_model_combo.itemData(i) == current_model:
                    self.memory_model_combo.setCurrentIndex(i)
                    break

    def _save_memory_agent(self):
        backend = self.memory_backend_combo.currentData()
        model = self.memory_model_combo.currentData()
        if model == "custom" and self.memory_custom_input.text().strip():
            model = self.memory_custom_input.text().strip()
        set_memory_agent_config(backend, model)
        self.memory_agent_saved_lbl.setText(f"✓ Saved — memory updates now use {model}")
        self.memory_agent_saved_lbl.setVisible(True)

    # ── Populate ─────────────────────────────────────────────────────────

    def refresh(self):
        """
        Rebuild the agent list from config. Safe to call any time agents
        are added/removed/renamed (same refresh contract as other panels
        — never touches data, only rebuilds UI from what's on disk).
        """
        self.agent_list.clear()
        agents_cfg = load_agents_config().get("agents", {})

        for name, cfg in agents_cfg.items():
            color = cfg.get("color", "#5B7FA6")
            has_mem = memory_exists(name)

            item = QListWidgetItem()
            item.setData(Qt.UserRole, name)
            item.setSizeHint(MemoryAgentListItem(name, color, has_mem).sizeHint())
            self.agent_list.addItem(item)
            self.agent_list.setItemWidget(item, MemoryAgentListItem(name, color, has_mem))

        # Keep showing the currently selected agent's content if it still
        # exists; otherwise reset to the empty state.
        if self._current_agent and self._current_agent in agents_cfg:
            self._load_agent_memory(self._current_agent)
        elif agents_cfg:
            pass  # leave unselected — don't force-select on refresh
        else:
            self._clear_content()

    # ── Selection ────────────────────────────────────────────────────────

    def _on_agent_selected(self, item: QListWidgetItem):
        name = item.data(Qt.UserRole)
        if name:
            self._load_agent_memory(name)

    def _load_agent_memory(self, agent_name: str):
        self._current_agent = agent_name
        self.content_title.setText(agent_name)
        self.editor.setEnabled(True)
        self.save_btn.setEnabled(True)
        self.regenerate_btn.setEnabled(True)
        self.status_lbl.setVisible(False)

        raw = load_memory(agent_name)
        if not raw.strip():
            raw = blank_memory(agent_name)
        self.editor.setPlainText(raw)

        updated = _extract_updated_timestamp(raw)
        self.updated_lbl.setText(f"Last updated: {updated}" if updated else "Not yet updated")

    def _clear_content(self):
        self._current_agent = None
        self.content_title.setText("Select an agent")
        self.editor.clear()
        self.editor.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.regenerate_btn.setEnabled(False)
        self.updated_lbl.setText("")
        self.status_lbl.setVisible(False)

    # ── Save (plain write, no LLM) ──────────────────────────────────────

    def _on_save(self):
        if not self._current_agent:
            return
        content = self.editor.toPlainText()
        save_memory(self._current_agent, content)
        self._show_status("✓ Saved")
        self.refresh()

    # ── Regenerate (forces a real distillation call) ────────────────────

    def _on_regenerate(self):
        if not self._current_agent or self._regen_worker is not None:
            return

        agent_name = self._current_agent
        history = load_history(agent_name)
        if not history:
            self._show_status("No conversation history to summarize yet.", error=True)
            return

        recent = _flatten_recent(history, limit=20)
        existing_memory = load_memory(agent_name)
        system_prompt, user_prompt = build_distillation_prompt(
            agent_name, existing_memory, recent
        )

        mem_cfg = get_memory_agent_config()
        backend = mem_cfg.get("backend") or ""
        model = mem_cfg.get("model") or ""
        if not backend or not model:
            agent_cfg = get_agent_config(agent_name)
            backend = agent_cfg.get("backend", "ollama")
            model = agent_cfg.get("model", "llama3.2:3b")

        inference = InferenceManager()
        worker = InferenceWorker(
            inference.chat, backend, model, system_prompt,
            [{"role": "user", "content": user_prompt}],
            "standard",
        )
        self._regen_worker = worker
        self._regen_buffer = ""

        self.regenerate_btn.setEnabled(False)
        self.regenerate_btn.setText("↻  Working…")
        self._show_status(f"Regenerating using {model}…")

        worker.signals.chunk.connect(self._on_regen_chunk)
        worker.signals.finished.connect(self._on_regen_done)
        worker.signals.error.connect(self._on_regen_error)
        ComputeManager().run(worker)

    def _on_regen_chunk(self, chunk: str):
        self._regen_buffer += chunk

    def _on_regen_done(self):
        agent_name = self._current_agent
        try:
            cleaned = clean_distillation_output(self._regen_buffer, agent_name or "")
            if agent_name:
                save_memory(agent_name, cleaned)
                if agent_name == self._current_agent:
                    self._load_agent_memory(agent_name)
            self._show_status("✓ Memory regenerated")
        except Exception:
            self._show_status("Regeneration failed — memory unchanged.", error=True)
        finally:
            self._regen_worker = None
            self._regen_buffer = ""
            self.regenerate_btn.setEnabled(True)
            self.regenerate_btn.setText("↻  Regenerate")
            self.refresh()

    def _on_regen_error(self, err: str):
        self._regen_worker = None
        self._regen_buffer = ""
        self.regenerate_btn.setEnabled(True)
        self.regenerate_btn.setText("↻  Regenerate")
        self._show_status("Regeneration failed — memory unchanged.", error=True)

    # ── Helpers ──────────────────────────────────────────────────────────

    def _show_status(self, text: str, error: bool = False):
        self.status_lbl.setText(text)
        self.status_lbl.setStyleSheet(
            f"font-size:11px; color:{'#C06060' if error else '#6ABF7A'};"
        )
        self.status_lbl.setVisible(True)


# ── Module helpers ───────────────────────────────────────────────────────

def _flatten_recent(history: list[dict], limit: int = 20) -> list[dict]:
    """Take the last `limit` messages from history_manager's format and
    flatten to plain role/content dicts (history is already plain-text
    strings by the time it's persisted, so this is mostly a slice)."""
    out = []
    for msg in history[-limit:]:
        content = msg.get("content", "")
        role = msg.get("role", "user")
        if isinstance(content, str) and content.strip():
            out.append({"role": role, "content": content})
    return out


def _extract_updated_timestamp(raw_memory: str) -> str:
    for line in raw_memory.splitlines():
        line = line.strip()
        if line.startswith("<!-- updated:"):
            return line.replace("<!-- updated:", "").replace("-->", "").strip()
    return ""