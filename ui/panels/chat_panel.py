"""
ChatPanel — Conversation area for one agent.

Fixes in this version:
1. File attachments saved as chip markers in history — never dumped as raw content in bubble.
2. Agent responses render Markdown (bold, italic, code, headers) via HTML conversion.
3. User messages always plain text — no markdown processing.
"""
import base64
import hashlib
import mimetypes
import re
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QLabel, QTextEdit, QPushButton, QSizePolicy,
    QFileDialog, QDialog
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QKeyEvent, QDragEnterEvent, QDropEvent, QPixmap

from core.inference_manager import InferenceManager
from core.compute_manager import ComputeManager, InferenceWorker
from core.config_loader import get_agent_config, get_app_setting
from core.history_manager import load_history, save_history, clear_history

BUCKET_DIR = Path(__file__).parent.parent.parent / "bucket"
SUPPORTED_IMAGES = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
SUPPORTED_DOCS   = {".pdf", ".txt", ".md", ".csv", ".json", ".py",
                    ".js", ".ts", ".html", ".css", ".yaml", ".toml", ".xml"}

IMAGES_DIR = Path(__file__).parent.parent.parent / "workspace" / "history" / "images"
_IMG_MARKER_PREFIX = "[[DESK_IMG:"
_IMG_MARKER_SUFFIX = "]]"

# Marker saved in history MD to represent a file attachment (not the contents)
_FILE_MARKER_PREFIX = "[[DESK_FILE:"
_FILE_MARKER_SUFFIX = "]]"


# ── Markdown → HTML ──────────────────────────────────────────────────────────

def markdown_to_html(text: str) -> str:
    """
    Convert common Markdown to HTML for agent message rendering.
    Handles: bold, italic, bold+italic, inline code, code blocks,
             headers (h1-h3), unordered lists, ordered lists, horizontal rules.
    """
    # Escape any existing HTML special chars first (except we add our own tags)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # ── Code blocks (``` ... ```) — must run before inline ────────────────
    def replace_code_block(m):
        lang = m.group(1) or ""
        code = m.group(2)
        return (
            f'<pre style="background:#1A1A22;border-radius:8px;padding:10px 14px;'
            f'margin:6px 0;font-family:monospace;font-size:12px;'
            f'color:#A8D8A8;overflow-x:auto;">'
            f'<code>{code}</code></pre>'
        )
    text = re.sub(r"```(\w*)\n?(.*?)```", replace_code_block, text, flags=re.DOTALL)

    # ── Inline code (`code`) ───────────────────────────────────────────────
    text = re.sub(
        r"`([^`]+)`",
        r'<code style="background:#222230;border-radius:4px;padding:1px 5px;'
        r'font-family:monospace;font-size:12px;color:#A8A8D8;">\1</code>',
        text
    )

    # ── Bold + Italic (***text*** or ___text___) ───────────────────────────
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"<b><i>\1</i></b>", text)
    text = re.sub(r"___(.+?)___",       r"<b><i>\1</i></b>", text)

    # ── Bold (**text** or __text__) ────────────────────────────────────────
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__(.+?)__",     r"<b>\1</b>", text)

    # ── Italic (*text* or _text_) — tight pattern, no false positives ────────
    # Must start/end with non-whitespace, no asterisk inside
    text = re.sub(r"(?<![\*\w])\*(?!\s)([^\*\n]+?)(?<!\s)\*(?![\*\w])", r"<i>\1</i>", text)
    text = re.sub(r"(?<![_\w])_(?!\s)([^_\n]+?)(?<!\s)_(?![_\w])",         r"<i>\1</i>", text)

    # ── Headers ────────────────────────────────────────────────────────────
    text = re.sub(r"^### (.+)$", r'<h3 style="margin:8px 0 4px;font-size:13px;color:#D0D0E8;">\1</h3>', text, flags=re.MULTILINE)
    text = re.sub(r"^## (.+)$",  r'<h2 style="margin:10px 0 4px;font-size:14px;color:#D8D8F0;">\1</h2>', text, flags=re.MULTILINE)
    text = re.sub(r"^# (.+)$",   r'<h1 style="margin:12px 0 6px;font-size:16px;color:#E0E0FF;">\1</h1>', text, flags=re.MULTILINE)

    # ── Horizontal rule ────────────────────────────────────────────────────
    text = re.sub(r"^---+$", r'<hr style="border:none;border-top:1px solid #2A2A38;margin:10px 0;">', text, flags=re.MULTILINE)

    # ── Unordered lists (lines starting with - or *) ───────────────────────
    def replace_ul(m):
        items = re.findall(r"^[-*] (.+)$", m.group(0), re.MULTILINE)
        lis = "".join(f"<li style='margin:2px 0;'>{i}</li>" for i in items)
        return f'<ul style="margin:4px 0;padding-left:20px;">{lis}</ul>'
    text = re.sub(r"(^[-*] .+$\n?)+", replace_ul, text, flags=re.MULTILINE)

    # ── Ordered lists (lines starting with 1. 2. etc) ─────────────────────
    def replace_ol(m):
        items = re.findall(r"^\d+\. (.+)$", m.group(0), re.MULTILINE)
        lis = "".join(f"<li style='margin:2px 0;'>{i}</li>" for i in items)
        return f'<ol style="margin:4px 0;padding-left:20px;">{lis}</ol>'
    text = re.sub(r"(^\d+\. .+$\n?)+", replace_ol, text, flags=re.MULTILINE)

    # ── Newlines → <br> (skip lines that already have block-level tags) ────
    lines = text.split("\n")
    result = []
    block_tags = ("<pre", "<h1", "<h2", "<h3", "<ul", "<ol", "<hr", "<li")
    for line in lines:
        stripped = line.strip()
        if any(stripped.startswith(t) for t in block_tags) or stripped == "":
            result.append(line)
        else:
            result.append(line + "<br>")

    return "\n".join(result)


# ── Confirm Dialog ───────────────────────────────────────────────────────────

class ConfirmDialog(QDialog):
    def __init__(self, title: str, message: str, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setFixedWidth(340)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        t = QLabel(title)
        t.setStyleSheet("font-size: 14px; font-weight: 700; color: #E2E2E2;")
        layout.addWidget(t)

        m = QLabel(message)
        m.setWordWrap(True)
        m.setStyleSheet("font-size: 12px; color: #7A7A7E;")
        layout.addWidget(m)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        cancel = QPushButton("Cancel")
        cancel.setObjectName("dialog_secondary")
        cancel.clicked.connect(self.reject)

        confirm = QPushButton("Clear History")
        confirm.setStyleSheet("""
            QPushButton {
                background-color: #5A2A2E;
                border: 1px solid #7A3A3E;
                border-radius: 8px;
                padding: 8px 18px;
                color: #E28A8E;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #6A3A3E; }
        """)
        confirm.clicked.connect(self.accept)

        btn_row.addStretch()
        btn_row.addWidget(cancel)
        btn_row.addWidget(confirm)
        layout.addLayout(btn_row)


# ── Attachment Chip ───────────────────────────────────────────────────────────

class AttachmentChip(QWidget):
    removed = Signal(int)

    def __init__(self, name: str, idx: int, is_image: bool = False,
                 pixmap: QPixmap = None, parent=None):
        super().__init__(parent)
        self.idx = idx
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        if is_image and pixmap:
            thumb = QLabel()
            thumb.setPixmap(pixmap.scaled(22, 22, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            layout.addWidget(thumb)
        else:
            layout.addWidget(QLabel("📄"))

        lbl = QLabel(name[:24] + "…" if len(name) > 24 else name)
        lbl.setStyleSheet("font-size: 11px; color: #C8C8CE;")
        layout.addWidget(lbl)

        x = QPushButton("×")
        x.setFixedSize(16, 16)
        x.setStyleSheet(
            "background:transparent;color:#5A5A6E;font-size:14px;border:none;"
        )
        x.clicked.connect(lambda: self.removed.emit(self.idx))
        layout.addWidget(x)

        self.setStyleSheet(
            "QWidget{background-color:#2A2A30;border-radius:8px;border:1px solid #3A3A3E;}"
        )
        self.setFixedHeight(34)


# ── File chip shown INSIDE a message bubble (non-removable, display only) ────

def make_file_chip_label(filename: str) -> QLabel:
    lbl = QLabel(f"📄  {filename}")
    lbl.setStyleSheet(
        "background:#222230;border-radius:7px;padding:5px 12px;"
        "font-size:11px;color:#8A8AAE;border:1px solid #2E2E40;"
    )
    lbl.setFixedHeight(30)
    return lbl


# ── Message Widget ────────────────────────────────────────────────────────────

class MessageWidget(QWidget):
    """
    Renders one message bubble.
    - is_user=True  → plain text, dark bubble, right-aligned.
    - is_user=False → Markdown rendered as HTML, left-aligned.
    - file_chips    → list of filenames shown as chips (above the text bubble).
    """
    def __init__(self, text: str, is_user: bool,
                 agent_color: str = "#5B7FA6",
                 attachments: list = None,
                 file_chips: list[str] = None,
                 parent=None):
        super().__init__(parent)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(16, 4, 16, 4)
        outer.setSpacing(0)

        col = QVBoxLayout()
        col.setSpacing(6)

        # ── Attachments: images rendered inline, docs as chips ────────────
        if attachments:
            for att in attachments:
                if att.get("type") == "image":
                    pix = QPixmap()
                    pix.loadFromData(base64.b64decode(att["data"]))
                    img_lbl = QLabel()
                    img_lbl.setPixmap(
                        pix.scaled(260, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    )
                    img_lbl.setStyleSheet("border-radius: 8px;")
                    col.addWidget(img_lbl)
                else:
                    col.addWidget(make_file_chip_label(att.get("name", "file")))

        # ── File chips from history reload (just filenames, not contents) ──
        if file_chips:
            for fname in file_chips:
                col.addWidget(make_file_chip_label(fname))

        # ── Text label ───────────────────────────────────────────────────
        self.label = QLabel()
        self.label.setWordWrap(True)
        self.label.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse
        )
        self.label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self._is_user = is_user
        self._raw_text = ""

        if is_user:
            # Plain text only for user — never process markdown
            self.label.setTextFormat(Qt.PlainText)
            self.label.setText(text)
            self.label.setStyleSheet("""
                background-color: #2C2C34;
                border-radius: 14px;
                padding: 10px 16px;
                color: #E2E2E2;
                font-size: 13px;
            """)
            self.label.setMaximumWidth(520)
            col.addWidget(self.label)
            outer.addStretch(1)
            outer.addLayout(col)
        else:
            # Agent: rich text with markdown rendering
            self.label.setTextFormat(Qt.RichText)
            self.label.setOpenExternalLinks(True)
            self._raw_text = text
            if text:
                self.label.setText(markdown_to_html(text))
            self.label.setStyleSheet("""
                padding: 10px 4px;
                color: #C8C8CE;
                font-size: 13px;
                line-height: 1.7;
            """)
            self.label.setMaximumWidth(680)
            col.addWidget(self.label)
            outer.addLayout(col)
            outer.addStretch(1)

    def append_text(self, chunk: str):
        """Called during streaming — accumulates raw text, re-renders HTML."""
        self._raw_text += chunk
        if self._is_user:
            self.label.setText(self._raw_text)
        else:
            self.label.setText(markdown_to_html(self._raw_text))

    def get_raw_text(self) -> str:
        return self._raw_text if not self._is_user else self.label.text()


# ── Smart Input ───────────────────────────────────────────────────────────────

class SmartInput(QTextEdit):
    send_triggered = Signal()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Return and not (event.modifiers() & Qt.ShiftModifier):
            self.send_triggered.emit()
        else:
            super().keyPressEvent(event)


# ── Chat Panel ────────────────────────────────────────────────────────────────

class ChatPanel(QWidget):
    def __init__(self, agent_name: str, agent_color: str, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.agent_name  = agent_name
        self.agent_color = agent_color
        self.messages:   list[dict] = []
        self._pending_attachments: list[dict] = []
        self._attachment_chips:   list[AttachmentChip] = []
        self._current_response_widget: MessageWidget | None = None
        self._active_worker = None
        self._build_ui()
        self._load_history()

    # ── UI ────────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_header())

        self.scroll = QScrollArea()
        self.scroll.setObjectName("chat_scroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.msg_container = QWidget()
        self.msg_container.setObjectName("chat_messages")
        self.msg_layout = QVBoxLayout(self.msg_container)
        self.msg_layout.setSpacing(8)
        self.msg_layout.setContentsMargins(0, 12, 0, 12)
        self.msg_layout.addStretch()

        self.scroll.setWidget(self.msg_container)
        layout.addWidget(self.scroll, 1)
        layout.addWidget(self._build_input_area())

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("topbar")
        header.setFixedHeight(44)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 0, 20, 0)

        dot = QWidget()
        dot.setFixedSize(8, 8)
        dot.setStyleSheet(f"background-color:{self.agent_color};border-radius:4px;")
        hl.addWidget(dot)

        name_lbl = QLabel(self.agent_name)
        name_lbl.setStyleSheet(
            "color:#E2E2E2;font-size:13px;font-weight:600;padding-left:8px;"
        )
        hl.addWidget(name_lbl)
        hl.addStretch()

        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("topbar_btn")
        clear_btn.clicked.connect(self._confirm_clear)
        hl.addWidget(clear_btn)
        return header

    def _build_input_area(self) -> QWidget:
        wrapper = QWidget()
        wrapper.setObjectName("input_area")
        vl = QVBoxLayout(wrapper)
        vl.setContentsMargins(14, 10, 14, 12)
        vl.setSpacing(8)

        self.attach_strip = QWidget()
        self.attach_strip_layout = QHBoxLayout(self.attach_strip)
        self.attach_strip_layout.setContentsMargins(0, 0, 0, 0)
        self.attach_strip_layout.setSpacing(6)
        self.attach_strip_layout.addStretch()
        self.attach_strip.setVisible(False)
        vl.addWidget(self.attach_strip)

        row = QHBoxLayout()
        row.setSpacing(8)

        self.attach_btn = QPushButton("📎")
        self.attach_btn.setToolTip("Attach file or image")
        self.attach_btn.setFixedSize(40, 40)
        self.attach_btn.setCursor(Qt.PointingHandCursor)
        self.attach_btn.setStyleSheet("""
            QPushButton {
                background-color: #252528;
                border: 1px solid #383838;
                border-radius: 10px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #2E2E36;
                border-color: #5A5A6A;
            }
            QPushButton:pressed { background-color: #1E1E24; }
        """)
        self.attach_btn.clicked.connect(self._open_file_picker)
        row.addWidget(self.attach_btn)

        self.input = SmartInput()
        self.input.setObjectName("chat_input")
        self.input.setPlaceholderText(
            f"Message {self.agent_name}…  (Shift+Enter for new line)"
        )
        self.input.setMinimumHeight(44)
        self.input.setMaximumHeight(120)
        self.input.send_triggered.connect(self._send)
        row.addWidget(self.input)

        self.send_btn = QPushButton("Send")
        self.send_btn.setObjectName("send_btn")
        self.send_btn.setFixedWidth(68)
        self.send_btn.clicked.connect(self._send)
        row.addWidget(self.send_btn)

        vl.addLayout(row)
        return wrapper

    # ── Drag & Drop ───────────────────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path:
                self._attach_file(Path(path))

    # ── Attachments ───────────────────────────────────────────────────────

    def _open_file_picker(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Attach Files", str(Path.home()),
            "Images & Docs (*.png *.jpg *.jpeg *.gif *.webp *.pdf "
            "*.txt *.md *.csv *.json *.py *.js *.ts *.html *.css "
            "*.yaml *.toml *.xml);;All Files (*)"
        )
        for p in paths:
            self._attach_file(Path(p))

    def _attach_file(self, path: Path):
        suffix = path.suffix.lower()
        name   = path.name

        if suffix in SUPPORTED_IMAGES:
            raw  = path.read_bytes()
            b64  = base64.b64encode(raw).decode()
            mime = mimetypes.guess_type(str(path))[0] or "image/png"
            att  = {"type": "image", "name": name, "data": b64, "mime": mime}
        else:
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                content = f"[Could not read: {name}]"
            att = {"type": "doc", "name": name, "content": content}

        idx = len(self._pending_attachments)
        self._pending_attachments.append(att)

        pixmap = None
        if att["type"] == "image":
            pixmap = QPixmap()
            pixmap.loadFromData(base64.b64decode(att["data"]))

        chip = AttachmentChip(name, idx, att["type"] == "image", pixmap)
        chip.removed.connect(self._remove_attachment)
        self._attachment_chips.append(chip)
        self.attach_strip_layout.insertWidget(
            self.attach_strip_layout.count() - 1, chip
        )
        self.attach_strip.setVisible(True)

    def _remove_attachment(self, idx: int):
        if 0 <= idx < len(self._pending_attachments):
            self._pending_attachments.pop(idx)
        chip = self._attachment_chips.pop(idx)
        self.attach_strip_layout.removeWidget(chip)
        chip.deleteLater()
        for i, c in enumerate(self._attachment_chips):
            c.idx = i
        if not self._pending_attachments:
            self.attach_strip.setVisible(False)

    # ── Send ──────────────────────────────────────────────────────────────

    def _send(self):
        text        = self.input.toPlainText().strip()
        attachments = list(self._pending_attachments)
        if not text and not attachments:
            return

        self.input.clear()
        self._pending_attachments.clear()
        for chip in self._attachment_chips:
            chip.deleteLater()
        self._attachment_chips.clear()
        self.attach_strip.setVisible(False)

        # Render bubble (real attachments shown as chips/images)
        self._add_message(text, is_user=True, attachments=attachments)

        # Build API message content
        if attachments:
            parts = []
            for att in attachments:
                if att["type"] == "image":
                    parts.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{att['mime']};base64,{att['data']}"}
                    })
                else:
                    parts.append({
                        "type": "text",
                        "text": f"[File: {att['name']}]\n{att.get('content', '')}"
                    })
            if text:
                parts.append({"type": "text", "text": text})
            self.messages.append({"role": "user", "content": parts})
        else:
            self.messages.append({"role": "user", "content": text})

        # Streaming agent response
        agent_widget = MessageWidget("", is_user=False, agent_color=self.agent_color)
        self.msg_layout.insertWidget(self.msg_layout.count() - 1, agent_widget)
        self._current_response_widget = agent_widget
        self._scroll_to_bottom()

        config = get_agent_config(self.agent_name)
        backend         = config.get("backend", "ollama")
        model           = config.get("model", "llama3.2:3b")
        response_length = config.get(
            "response_length", get_app_setting("response_length", "standard")
        )
        system_prompt = ""
        md_path = BUCKET_DIR / f"{self.agent_name}.md"
        if md_path.exists():
            system_prompt = md_path.read_text(encoding="utf-8")

        inference = InferenceManager()
        worker    = InferenceWorker(
            inference.chat, backend, model, system_prompt,
            list(self.messages), response_length,
        )
        self._active_worker = worker
        worker.signals.chunk.connect(self._on_chunk)
        worker.signals.finished.connect(self._on_done)
        worker.signals.error.connect(self._on_error)
        self.send_btn.setEnabled(False)
        ComputeManager().run(worker)

    # ── Streaming ─────────────────────────────────────────────────────────

    def _on_chunk(self, chunk: str):
        if self._current_response_widget:
            self._current_response_widget.append_text(chunk)
            self._scroll_to_bottom()

    def _on_done(self):
        self.send_btn.setEnabled(True)
        if self._current_response_widget:
            raw = self._current_response_widget.get_raw_text()
            self.messages.append({"role": "assistant", "content": raw})
        self._current_response_widget = None
        self._active_worker = None
        self._save_history()

    def _on_error(self, err: str):
        self.send_btn.setEnabled(True)
        if self._current_response_widget:
            self._current_response_widget.append_text(f"\n[Error: {err}]")
        self._active_worker = None

    # ── History ───────────────────────────────────────────────────────────

    def _load_history(self):
        """
        Restore messages from disk.
        String content → render normally.
        Messages with file markers → render chip labels, not raw text.
        """
        stored = load_history(self.agent_name)
        self.messages = []
        for msg in stored:
            content = msg.get("content", "")
            role    = msg.get("role", "user")
            is_user = role == "user"

            if isinstance(content, str):
                # Check if this message contains file/image markers
                file_chips, clean_text, img_atts = _extract_file_markers(content)
                if file_chips or img_atts:
                    self._add_message(
                        clean_text, is_user=is_user,
                        file_chips=file_chips,
                        attachments=img_atts if img_atts else None,
                    )
                else:
                    self._add_message(content, is_user=is_user)

            self.messages.append(msg)

    def _save_history(self):
        """
        Persist messages to disk.
        Multi-part messages (with attachments): save text parts normally,
        but replace file content with a named marker so reload shows a chip,
        not the raw file dump.
        """
        saveable = []
        for msg in self.messages:
            content = msg.get("content", "")
            role    = msg.get("role", "user")

            if isinstance(content, str):
                saveable.append({"role": role, "content": content})
            else:
                # Multi-part: extract text and file names separately
                text_parts = []
                file_names = []
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    pt = part.get("type", "")
                    if pt == "text":
                        raw = part.get("text", "")
                        # Strip the "[File: name]\ncontent" injected for API
                        # — we only save the marker, not the full file dump
                        if raw.startswith("[File: "):
                            first_line = raw.split("\n", 1)[0]
                            # Extract filename from "[File: name.txt]"
                            fname = first_line[7:].rstrip("]")
                            file_names.append(fname)
                        else:
                            text_parts.append(raw)
                    elif pt == "image_url":
                        # Save image as a file in workspace/history/images/
                        url_val = part.get("image_url", {}).get("url", "")
                        if url_val.startswith("data:"):
                            try:
                                header, b64data = url_val.split(",", 1)
                                mime = header.split(":")[1].split(";")[0]
                                ext  = mime.split("/")[-1].replace("jpeg", "jpg")
                                # Stable filename based on content hash
                                img_hash = hashlib.md5(b64data[:64].encode()).hexdigest()[:12]
                                img_name = f"{img_hash}.{ext}"
                                IMAGES_DIR.mkdir(parents=True, exist_ok=True)
                                img_path = IMAGES_DIR / img_name
                                if not img_path.exists():
                                    img_path.write_bytes(base64.b64decode(b64data))
                                file_names.append(
                                    f"{_IMG_MARKER_PREFIX}{img_name}{_IMG_MARKER_SUFFIX}"
                                )
                            except Exception:
                                pass

                # Build saved string: file markers + image markers + user text
                parts_out = []
                for fname in file_names:
                    # Skip entries that are already full IMG markers
                    if fname.startswith(_IMG_MARKER_PREFIX):
                        parts_out.append(fname)  # already formatted correctly
                    else:
                        parts_out.append(
                            f"{_FILE_MARKER_PREFIX}{fname}{_FILE_MARKER_SUFFIX}"
                        )
                if text_parts:
                    parts_out.append(" ".join(text_parts))

                saved_content = "\n".join(parts_out).strip()
                if saved_content:
                    saveable.append({"role": role, "content": saved_content})

        save_history(self.agent_name, saveable)

    # ── Clear ─────────────────────────────────────────────────────────────

    def _confirm_clear(self):
        dlg = ConfirmDialog(
            "Clear Chat History",
            f"This will permanently delete your conversation with "
            f"{self.agent_name}. This cannot be undone.",
            parent=self
        )
        if dlg.exec() == QDialog.Accepted:
            self._clear_chat()

    def _clear_chat(self):
        self.messages.clear()
        clear_history(self.agent_name)
        while self.msg_layout.count() > 1:
            item = self.msg_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    # ── Helpers ───────────────────────────────────────────────────────────

    def _add_message(self, text: str, is_user: bool,
                     attachments: list = None,
                     file_chips: list[str] = None):
        w = MessageWidget(
            text, is_user=is_user,
            agent_color=self.agent_color,
            attachments=attachments,
            file_chips=file_chips,
        )
        self.msg_layout.insertWidget(self.msg_layout.count() - 1, w)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        QTimer.singleShot(50, lambda: self.scroll.verticalScrollBar().setValue(
            self.scroll.verticalScrollBar().maximum()
        ))


# ── Marker helpers ────────────────────────────────────────────────────────────

def _extract_file_markers(text: str) -> tuple[list[str], str, list[dict]]:
    """
    Extract markers from a saved history string.
    [[DESK_FILE:filename]]  → doc chip label
    [[DESK_IMG:imgfile]]    → image loaded from workspace/history/images/
    Returns (doc_filenames, clean_text, image_dicts).
    """
    # Doc file chips
    file_pat = re.compile(r"\[\[DESK_FILE:(.+?)\]\]")
    filenames = file_pat.findall(text)
    text = file_pat.sub("", text)

    # Image markers — load from file
    img_pat = re.compile(r"\[\[DESK_IMG:(.+?)\]\]")
    images = []
    for m in img_pat.finditer(text):
        img_name = m.group(1)
        img_path = IMAGES_DIR / img_name
        if img_path.exists():
            try:
                raw    = img_path.read_bytes()
                b64    = base64.b64encode(raw).decode()
                ext    = img_path.suffix.lstrip(".")
                mime   = f"image/{'jpeg' if ext == 'jpg' else ext}"
                images.append({
                    "type": "image", "name": img_name,
                    "mime": mime,    "data": b64,
                })
            except Exception:
                pass
    text = img_pat.sub("", text)

    return filenames, text.strip(), images
