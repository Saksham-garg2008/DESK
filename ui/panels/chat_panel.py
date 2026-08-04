"""
ChatPanel — Conversation area for one agent.

V2 additions:
- Parse agent responses for code blocks → create artifacts
- Show artifact chips (📄 filename [vN]) in chat after agent message
- Artifact chips are clickable → opens code inspector
- Clear chat also clears artifacts
- Emits artifacts_changed signal so workspace panel can refresh
"""
import base64
import hashlib
import mimetypes
import re
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QLabel, QTextEdit, QPushButton, QSizePolicy,
    QFileDialog, QDialog, QApplication
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QKeyEvent, QDragEnterEvent, QDropEvent, QPixmap

from core.inference_manager import InferenceManager
from core.compute_manager import ComputeManager, InferenceWorker
from core.config_loader import get_agent_config, get_app_setting
from core.history_manager import load_history, save_history, clear_history
from core.artifact_manager import ArtifactManager
from core.config_loader import get_memory_agent_config
from core.memory_manager import (
    load_memory, save_memory, build_distillation_prompt,
    clean_distillation_output, DISTILL_EVERY_N_EXCHANGES,
)

BUCKET_DIR = Path(__file__).parent.parent.parent / "bucket"
SUPPORTED_IMAGES = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
SUPPORTED_DOCS   = {".pdf", ".txt", ".md", ".csv", ".json", ".py",
                    ".js", ".ts", ".html", ".css", ".yaml", ".toml", ".xml"}

IMAGES_DIR = Path(__file__).parent.parent.parent / "workspace" / "history" / "images"
_IMG_MARKER_PREFIX = "[[DESK_IMG:"
_IMG_MARKER_SUFFIX = "]]"
_FILE_MARKER_PREFIX = "[[DESK_FILE:"
_FILE_MARKER_SUFFIX = "]]"


# ── Markdown → HTML ──────────────────────────────────────────────────────────

# Sentinel used to split text around inline code blocks
_CODE_SENTINEL = "\x00DESK_CODE_BLOCK\x00"

def strip_artifact_code_blocks(text: str, artifact_filenames: set[str]) -> str:
    """
    Remove fenced code blocks that became artifacts from display text.
    Non-artifact blocks are left intact (they get rendered as inline code widgets).
    Also cleans up orphaned blank lines left by removal.
    """
    CODE_RE = re.compile(r"```(\w*)\n?(.*?)```", re.DOTALL)

    def maybe_strip(m):
        lang = m.group(1).strip().lower()
        code = m.group(2)
        # Check if this block's content matches any artifact we just saved
        from core.artifact_manager import _hash
        for fname in artifact_filenames:
            # We compare hash of code content to what was saved
            # Use the sentinel so the caller knows to insert a chip here
            pass
        # Simple approach: mark artifact blocks for removal
        # We'll replace them with a unique sentinel the caller replaces with chips
        return _CODE_SENTINEL

    # We need to know which blocks are artifacts — match by content hash
    from core.artifact_manager import ArtifactManager, _hash
    # Can't easily do this per-block in a sub — do it manually
    result = []
    last_end = 0
    for m in CODE_RE.finditer(text):
        code_content = m.group(2)
        is_artifact = False
        for fname in artifact_filenames:
            # We'll do a loose check: if content hash matches any stored artifact version
            is_artifact = True  # We trust the caller — all detected artifacts passed in
            break
        result.append(text[last_end:m.start()])
        if not is_artifact:
            result.append(m.group(0))  # keep non-artifact blocks
        # artifact blocks → omit (chip inserted separately)
        last_end = m.end()
    result.append(text[last_end:])
    stripped = "".join(result)

    # Clean up excess blank lines (max 2 consecutive)
    stripped = re.sub(r"\n{3,}", "\n\n", stripped).strip()
    return stripped


def split_text_and_code_blocks(text: str) -> list[dict]:
    """
    Split raw agent text into segments:
    - {"type": "text", "content": "..."}       — prose/markdown
    - {"type": "code", "lang": "py", "content": "..."}  — fenced code block

    Used for non-artifact code blocks that we render inline with a copy button.
    """
    CODE_RE = re.compile(r"```(\w*)\n?(.*?)```", re.DOTALL)
    segments = []
    last_end = 0
    for m in CODE_RE.finditer(text):
        before = text[last_end:m.start()].strip()
        if before:
            segments.append({"type": "text", "content": before})
        lang = m.group(1).strip().lower()
        code = m.group(2)
        if code.strip():
            segments.append({"type": "code", "lang": lang, "content": code})
        last_end = m.end()
    after = text[last_end:].strip()
    if after:
        segments.append({"type": "text", "content": after})
    return segments


def markdown_to_html(text: str) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

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
    text = re.sub(
        r"`([^`]+)`",
        r'<code style="background:#222230;border-radius:4px;padding:1px 5px;'
        r'font-family:monospace;font-size:12px;color:#A8A8D8;">\1</code>',
        text
    )
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"<b><i>\1</i></b>", text)
    text = re.sub(r"___(.+?)___",       r"<b><i>\1</i></b>", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__(.+?)__",     r"<b>\1</b>", text)
    text = re.sub(r"(?<![\*\w])\*(?!\s)([^\*\n]+?)(?<!\s)\*(?![\*\w])", r"<i>\1</i>", text)
    text = re.sub(r"(?<![_\w])_(?!\s)([^_\n]+?)(?<!\s)_(?![_\w])",       r"<i>\1</i>", text)
    text = re.sub(r"^### (.+)$", r'<h3 style="margin:8px 0 4px;font-size:13px;color:#D0D0E8;">\1</h3>', text, flags=re.MULTILINE)
    text = re.sub(r"^## (.+)$",  r'<h2 style="margin:10px 0 4px;font-size:14px;color:#D8D8F0;">\1</h2>', text, flags=re.MULTILINE)
    text = re.sub(r"^# (.+)$",   r'<h1 style="margin:12px 0 6px;font-size:16px;color:#E0E0FF;">\1</h1>', text, flags=re.MULTILINE)
    text = re.sub(r"^---+$", r'<hr style="border:none;border-top:1px solid #2A2A38;margin:10px 0;">', text, flags=re.MULTILINE)

    def replace_ul(m):
        items = re.findall(r"^[-*] (.+)$", m.group(0), re.MULTILINE)
        lis = "".join(f"<li style='margin:2px 0;'>{i}</li>" for i in items)
        return f'<ul style="margin:4px 0;padding-left:20px;">{lis}</ul>'
    text = re.sub(r"(^[-*] .+$\n?)+", replace_ul, text, flags=re.MULTILINE)

    def replace_ol(m):
        items = re.findall(r"^\d+\. (.+)$", m.group(0), re.MULTILINE)
        lis = "".join(f"<li style='margin:2px 0;'>{i}</li>" for i in items)
        return f'<ol style="margin:4px 0;padding-left:20px;">{lis}</ol>'
    text = re.sub(r"(^\d+\. .+$\n?)+", replace_ol, text, flags=re.MULTILINE)

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


# ── Confirm Dialog ────────────────────────────────────────────────────────────

class ConfirmDialog(QDialog):
    def __init__(self, title: str, message: str, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setFixedWidth(360)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        t = QLabel(title)
        t.setStyleSheet("font-size: 14px; font-weight: 700; color: #E2E2E2;")
        layout.addWidget(t)

        m = QLabel(message)
        m.setWordWrap(True)
        m.setStyleSheet("font-size: 12px; color: #7A7A7E; line-height: 1.6;")
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
        x.setStyleSheet("background:transparent;color:#5A5A6E;font-size:14px;border:none;")
        x.clicked.connect(lambda: self.removed.emit(self.idx))
        layout.addWidget(x)
        self.setStyleSheet("QWidget{background-color:#2A2A30;border-radius:8px;border:1px solid #3A3A3E;}")
        self.setFixedHeight(34)


def make_file_chip_label(filename: str) -> QLabel:
    lbl = QLabel(f"📄  {filename}")
    lbl.setStyleSheet(
        "background:#222230;border-radius:7px;padding:5px 12px;"
        "font-size:11px;color:#8A8AAE;border:1px solid #2E2E40;"
    )
    lbl.setFixedHeight(30)
    return lbl


# ── Artifact Chip (clickable, shown after agent message) ──────────────────────

class ArtifactChip(QWidget):
    """Clickable chip shown in chat after agent creates/updates an artifact."""
    open_requested = Signal(str, str)  # agent_name, filename

    def __init__(self, agent_name: str, filename: str, version: int, parent=None):
        super().__init__(parent)
        self.agent_name = agent_name
        self.filename = filename
        self.version = version
        self.setCursor(Qt.PointingHandCursor)
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(8)

        icon = QLabel("📄")
        icon.setStyleSheet("font-size: 13px;")
        layout.addWidget(icon)

        name_lbl = QLabel(self.filename)
        name_lbl.setStyleSheet(
            "font-size: 12px; color: #A0A0C0; font-weight: 600;"
        )
        layout.addWidget(name_lbl)

        ver_lbl = QLabel(f"v{self.version}")
        ver_lbl.setStyleSheet(
            "font-size: 10px; color: #505070; background: #1E1E2C; "
            "border-radius: 4px; padding: 2px 6px; font-weight: 600;"
        )
        layout.addWidget(ver_lbl)

        open_lbl = QLabel("↗")
        open_lbl.setStyleSheet("font-size: 11px; color: #404060;")
        layout.addWidget(open_lbl)

        self.setStyleSheet("""
            QWidget {
                background: #1E1E2C;
                border-radius: 8px;
                border: 1px solid #2E2E40;
            }
            QWidget:hover {
                background: #252538;
                border-color: #3E3E58;
            }
        """)
        self.setFixedHeight(36)
        self.setMaximumWidth(280)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.open_requested.emit(self.agent_name, self.filename)


def _code_matches_any_artifact(
    code: str, agent_name: str, artifact_filenames: set[str]
) -> bool:
    """
    Returns True if this code block's content matches any saved artifact
    version for this agent. Used to decide suppress vs. show inline.
    """
    if not artifact_filenames:
        return False
    from core.artifact_manager import ArtifactManager, _hash
    am = ArtifactManager()
    code_hash = _hash(code)
    for fname in artifact_filenames:
        artifact = am.get_artifact(agent_name, fname)
        if not artifact:
            continue
        for ver in artifact.get("versions", []):
            if _hash(ver.get("content", "")) == code_hash:
                return True
    return False


# ── Inline Code Block (non-artifact, shown in chat with copy button) ──────────

class InlineCodeBlock(QWidget):
    """
    Renders a small code block in chat with a one-click copy button.
    Used only for code blocks that did NOT become artifacts
    (e.g. short snippets, command examples, concept illustrations).
    """
    def __init__(self, code: str, lang: str = "", parent=None):
        super().__init__(parent)
        self._code = code
        self._build_ui(lang)

    def _build_ui(self, lang: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(0)

        # Container
        container = QWidget()
        container.setStyleSheet("""
            QWidget {
                background: #1A1A22;
                border-radius: 8px;
                border: 1px solid #252530;
            }
        """)
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # Top bar: lang label + copy button
        top_bar = QWidget()
        top_bar.setStyleSheet(
            "background: #16161E; border-radius: 8px 8px 0 0; border-bottom: 1px solid #252530;"
        )
        top_bar.setFixedHeight(30)
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(12, 0, 8, 0)
        top_layout.setSpacing(0)

        lang_lbl = QLabel(lang.upper() if lang else "CODE")
        lang_lbl.setStyleSheet(
            "font-size: 9px; font-weight: 700; color: #383850; "
            "letter-spacing: 1px; font-family: monospace;"
        )
        top_layout.addWidget(lang_lbl)
        top_layout.addStretch()

        self.copy_btn = QPushButton("Copy")
        self.copy_btn.setFixedHeight(22)
        self.copy_btn.setStyleSheet("""
            QPushButton {
                background: #22222E;
                border: 1px solid #2E2E3A;
                border-radius: 4px;
                padding: 0 8px;
                font-size: 10px;
                font-weight: 600;
                color: #505068;
            }
            QPushButton:hover {
                background: #2A2A3A;
                color: #8080A0;
            }
        """)
        self.copy_btn.clicked.connect(self._copy)
        top_layout.addWidget(self.copy_btn)

        container_layout.addWidget(top_bar)

        # Code content
        code_lbl = QLabel(self._code)
        code_lbl.setTextFormat(Qt.PlainText)
        code_lbl.setWordWrap(False)
        code_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        code_lbl.setStyleSheet("""
            font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code',
                         'Consolas', 'Monaco', 'Menlo', monospace;
            font-size: 12px;
            color: #A8D8A8;
            padding: 10px 14px;
            background: transparent;
            line-height: 1.6;
        """)
        container_layout.addWidget(code_lbl)

        layout.addWidget(container)
        self.setMaximumWidth(660)

    def _copy(self):
        QApplication.clipboard().setText(self._code)
        self.copy_btn.setText("Copied!")
        QTimer.singleShot(1500, lambda: self.copy_btn.setText("Copy"))


# ── Message Widget ────────────────────────────────────────────────────────────

class MessageWidget(QWidget):
    artifact_open_requested = Signal(str, str)  # agent_name, filename

    def __init__(self, text: str, is_user: bool,
                 agent_color: str = "#5B7FA6",
                 attachments: list = None,
                 file_chips: list[str] = None,
                 artifact_chips: list[tuple] = None,  # (agent_name, filename, version)
                 agent_name: str = "",
                 parent=None):
        super().__init__(parent)
        self._is_user = is_user
        self._raw_text = ""
        self._agent_name = agent_name
        self._artifact_chips_data = artifact_chips or []

        outer = QHBoxLayout(self)
        outer.setContentsMargins(16, 4, 16, 4)
        outer.setSpacing(0)

        col = QVBoxLayout()
        col.setSpacing(6)

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

        if file_chips:
            for fname in file_chips:
                col.addWidget(make_file_chip_label(fname))

        self.label = QLabel()
        self.label.setWordWrap(True)
        self.label.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse
        )
        self.label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        if is_user:
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
            # Agent message — label used during streaming only.
            # After streaming, _finalize_display() rebuilds with segments.
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

            # Container for finalized segmented content (replaces label after streaming)
            self._segments_container = QWidget()
            self._segments_container.setVisible(False)
            self._segments_layout = QVBoxLayout(self._segments_container)
            self._segments_layout.setContentsMargins(0, 0, 0, 0)
            self._segments_layout.setSpacing(6)
            col.addWidget(self._segments_container)

            # Artifact chips row
            self._chips_container = QWidget()
            self._chips_layout = QHBoxLayout(self._chips_container)
            self._chips_layout.setContentsMargins(0, 4, 0, 0)
            self._chips_layout.setSpacing(6)
            self._chips_layout.addStretch()
            self._chips_container.setVisible(False)
            col.addWidget(self._chips_container)

            # Show chips if provided at construction time (history reload)
            if self._artifact_chips_data:
                self._show_artifact_chips(self._artifact_chips_data)

            outer.addLayout(col)
            outer.addStretch(1)

        # Store col ref for finalize
        self._col = col

    def append_text(self, chunk: str):
        """During streaming — accumulate raw text, render full markdown."""
        self._raw_text += chunk
        if self._is_user:
            self.label.setText(self._raw_text)
        else:
            self.label.setText(markdown_to_html(self._raw_text))

    def get_raw_text(self) -> str:
        return self._raw_text if not self._is_user else self.label.text()

    def finalize_display(self, artifact_filenames: set[str], artifact_chips: list[tuple]):
        """
        Called once streaming is done.
        - Strips artifact code blocks from display text
        - Renders remaining text + any non-artifact code blocks as inline widgets
        - Shows artifact chips
        """
        if self._is_user:
            return

        raw = self._raw_text

        # Build segments: split text around ALL code blocks
        CODE_RE = re.compile(r"```(\w*)\n?(.*?)```", re.DOTALL)
        segments = []
        last_end = 0

        for m in CODE_RE.finditer(raw):
            before = raw[last_end:m.start()].strip()
            if before:
                segments.append({"type": "text", "content": before})

            lang = m.group(1).strip().lower()
            code = m.group(2)

            # Determine if this block is an artifact
            is_artifact = _code_matches_any_artifact(
                code, self._agent_name, artifact_filenames
            )

            if is_artifact:
                segments.append({"type": "artifact_placeholder"})
            else:
                # Non-artifact: show inline with copy button
                if code.strip():
                    segments.append({"type": "code", "lang": lang, "content": code})

            last_end = m.end()

        after = raw[last_end:].strip()
        if after:
            segments.append({"type": "text", "content": after})

        # Hide streaming label
        self.label.setVisible(False)

        # Build segmented display
        artifact_chip_iter = iter(artifact_chips)
        for seg in segments:
            if seg["type"] == "text":
                txt = seg["content"]
                if not txt:
                    continue
                lbl = QLabel()
                lbl.setWordWrap(True)
                lbl.setTextInteractionFlags(
                    Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse
                )
                lbl.setTextFormat(Qt.RichText)
                lbl.setOpenExternalLinks(True)
                lbl.setText(markdown_to_html(txt))
                lbl.setStyleSheet("""
                    padding: 2px 4px;
                    color: #C8C8CE;
                    font-size: 13px;
                    line-height: 1.7;
                """)
                lbl.setMaximumWidth(680)
                self._segments_layout.addWidget(lbl)

            elif seg["type"] == "code":
                block = InlineCodeBlock(seg["content"], seg["lang"])
                self._segments_layout.addWidget(block)

            elif seg["type"] == "artifact_placeholder":
                # Insert the next artifact chip inline
                try:
                    agent_name, filename, version = next(artifact_chip_iter)
                    chip = ArtifactChip(agent_name, filename, version)
                    chip.open_requested.connect(self.artifact_open_requested)
                    chip_row = QWidget()
                    chip_row_layout = QHBoxLayout(chip_row)
                    chip_row_layout.setContentsMargins(0, 0, 0, 0)
                    chip_row_layout.setSpacing(0)
                    chip_row_layout.addWidget(chip)
                    chip_row_layout.addStretch()
                    self._segments_layout.addWidget(chip_row)
                except StopIteration:
                    pass

        self._segments_container.setVisible(True)

        # Any remaining chips not placed inline go in the chips row
        remaining = list(artifact_chip_iter)
        if remaining:
            self._show_artifact_chips(remaining)

    def show_artifact_chips(self, chips: list[tuple]):
        """Fallback — add artifact chips to the chips row."""
        if not self._is_user:
            self._show_artifact_chips(chips)

    def _show_artifact_chips(self, chips: list[tuple]):
        if not chips:
            return
        while self._chips_layout.count() > 1:
            item = self._chips_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for agent_name, filename, version in chips:
            chip = ArtifactChip(agent_name, filename, version)
            chip.open_requested.connect(self.artifact_open_requested)
            self._chips_layout.insertWidget(self._chips_layout.count() - 1, chip)
        self._chips_container.setVisible(True)


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
    artifacts_changed = Signal(str)  # agent_name — workspace panel should refresh
    artifact_open_requested = Signal(str, str)  # agent_name, filename

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
        # ── Memory distillation state ───────────────────────────────
        self._exchanges_since_distill = 0
        self._memory_worker = None
        self._memory_buffer = ""
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

        self._add_message(text, is_user=True, attachments=attachments)

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

        agent_widget = MessageWidget(
            "", is_user=False, agent_color=self.agent_color,
            agent_name=self.agent_name
        )
        agent_widget.artifact_open_requested.connect(self.artifact_open_requested)
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

        # ── Inject long-term memory, if any exists yet ──────────────
        agent_memory = load_memory(self.agent_name)
        if agent_memory:
            system_prompt = (
                f"{system_prompt}\n\n"
                f"--- What you remember from past conversations ---\n"
                f"{agent_memory}\n"
                f"--- end memory ---"
            ).strip()

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

            # ── Parse artifacts from response ──────────────────────────
            am = ArtifactManager()
            created = am.parse_and_save_artifacts(self.agent_name, raw)

            # Build chip tuples and filename set
            chips = [(self.agent_name, fname, ver) for fname, ver in created]
            artifact_filenames = {fname for fname, _ in created}

            # Finalize display: suppress artifact code blocks,
            # show inline copy-button for non-artifact blocks, place chips
            self._current_response_widget.finalize_display(
                artifact_filenames, chips
            )

            if created:
                self.artifacts_changed.emit(self.agent_name)

        self._current_response_widget = None
        self._active_worker = None
        self._save_history()

        # ── Memory distillation trigger ─────────────────────────────
        self._exchanges_since_distill += 1
        if self._exchanges_since_distill >= DISTILL_EVERY_N_EXCHANGES:
            self._trigger_memory_distillation()
            self._exchanges_since_distill = 0

    def _on_error(self, err: str):
        self.send_btn.setEnabled(True)
        if self._current_response_widget:
            self._current_response_widget.append_text(f"\n[Error: {err}]")
        self._active_worker = None

    # ── Memory Distillation ──────────────────────────────────────────────

    def _trigger_memory_distillation(self):
        """
        Fires a separate, non-blocking background call that reads recent
        exchanges + existing memory, and produces an updated memory file.
        Uses the global Memory Agent config; falls back to this agent's
        own backend/model if the Memory Agent has never been configured.

        Isolated from the main chat worker entirely — a slow or failing
        memory model must never block or affect the chat itself.
        """
        if self._memory_worker is not None:
            return  # already running, don't overlap

        recent = self._recent_plain_exchanges(limit=8)
        if not recent:
            return

        existing_memory = load_memory(self.agent_name)
        system_prompt, user_prompt = build_distillation_prompt(
            self.agent_name, existing_memory, recent
        )

        mem_cfg = get_memory_agent_config()
        backend = mem_cfg.get("backend") or ""
        model = mem_cfg.get("model") or ""
        if not backend or not model:
            # Fall back to this agent's own backend/model
            agent_cfg = get_agent_config(self.agent_name)
            backend = agent_cfg.get("backend", "ollama")
            model = agent_cfg.get("model", "llama3.2:3b")

        inference = InferenceManager()
        worker = InferenceWorker(
            inference.chat, backend, model, system_prompt,
            [{"role": "user", "content": user_prompt}],
            "standard",
        )
        self._memory_worker = worker
        self._memory_buffer = ""
        worker.signals.chunk.connect(self._on_memory_chunk)
        worker.signals.finished.connect(self._on_memory_done)
        worker.signals.error.connect(self._on_memory_error)
        ComputeManager().run(worker)

    def _on_memory_chunk(self, chunk: str):
        self._memory_buffer += chunk

    def _on_memory_done(self):
        try:
            cleaned = clean_distillation_output(self._memory_buffer, self.agent_name)
            save_memory(self.agent_name, cleaned)
        except Exception:
            # Silent failure — chat is never affected by a bad memory update
            pass
        finally:
            self._memory_worker = None
            self._memory_buffer = ""

    def _on_memory_error(self, err: str):
        # Silent failure — memory just doesn't update this round
        self._memory_worker = None
        self._memory_buffer = ""

    def flush_memory(self):
        """
        Force a memory distillation pass right now, regardless of the
        exchange counter. Call this on agent-switch-away or app close so
        short-but-important conversations aren't lost.
        """
        if self._exchanges_since_distill > 0:
            self._trigger_memory_distillation()
            self._exchanges_since_distill = 0

    def _recent_plain_exchanges(self, limit: int = 8) -> list[dict]:
        """
        Returns the last `limit` messages as plain role/content dicts,
        text-only — attachments are flattened to their text parts (or
        skipped if they had none), since the memory model only needs
        the conversational substance, not raw file/image payloads.
        """
        out = []
        for msg in self.messages[-limit:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if isinstance(content, str):
                if content.strip():
                    out.append({"role": role, "content": content})
            else:
                text_parts = [
                    p.get("text", "") for p in content
                    if isinstance(p, dict) and p.get("type") == "text"
                ]
                text = " ".join(text_parts).strip()
                if text:
                    out.append({"role": role, "content": text})
        return out

    # ── History ───────────────────────────────────────────────────────────

    def _load_history(self):
        stored = load_history(self.agent_name)
        self.messages = []
        for msg in stored:
            content = msg.get("content", "")
            role    = msg.get("role", "user")
            is_user = role == "user"
            if isinstance(content, str):
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
        saveable = []
        for msg in self.messages:
            content = msg.get("content", "")
            role    = msg.get("role", "user")
            if isinstance(content, str):
                saveable.append({"role": role, "content": content})
            else:
                text_parts = []
                file_names = []
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    pt = part.get("type", "")
                    if pt == "text":
                        raw = part.get("text", "")
                        if raw.startswith("[File: "):
                            first_line = raw.split("\n", 1)[0]
                            fname = first_line[7:].rstrip("]")
                            file_names.append(fname)
                        else:
                            text_parts.append(raw)
                    elif pt == "image_url":
                        url_val = part.get("image_url", {}).get("url", "")
                        if url_val.startswith("data:"):
                            try:
                                header, b64data = url_val.split(",", 1)
                                mime = header.split(":")[1].split(";")[0]
                                ext  = mime.split("/")[-1].replace("jpeg", "jpg")
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
                parts_out = []
                for fname in file_names:
                    if fname.startswith(_IMG_MARKER_PREFIX):
                        parts_out.append(fname)
                    else:
                        parts_out.append(f"{_FILE_MARKER_PREFIX}{fname}{_FILE_MARKER_SUFFIX}")
                if text_parts:
                    parts_out.append(" ".join(text_parts))
                saved_content = "\n".join(parts_out).strip()
                if saved_content:
                    saveable.append({"role": role, "content": saved_content})
        save_history(self.agent_name, saveable)

    # ── Clear ─────────────────────────────────────────────────────────────

    def _confirm_clear(self):
        am = ArtifactManager()
        art_count = am.artifact_count(self.agent_name)
        art_note = ""
        if art_count > 0:
            art_note = (
                f" This will also delete {art_count} artifact"
                f"{'s' if art_count != 1 else ''} in the Workspace."
            )

        dlg = ConfirmDialog(
            "Clear Chat History",
            f"This will permanently delete your conversation with "
            f"{self.agent_name}.{art_note} This cannot be undone.",
            parent=self
        )
        if dlg.exec() == QDialog.Accepted:
            self._clear_chat()

    def _clear_chat(self):
        self.messages.clear()
        clear_history(self.agent_name)
        self._exchanges_since_distill = 0

        # Clear artifacts too
        am = ArtifactManager()
        am.clear_agent_artifacts(self.agent_name)
        self.artifacts_changed.emit(self.agent_name)

        while self.msg_layout.count() > 1:
            item = self.msg_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    # ── Helpers ───────────────────────────────────────────────────────────

    def _add_message(self, text: str, is_user: bool,
                     attachments: list = None,
                     file_chips: list[str] = None,
                     artifact_chips: list[tuple] = None):
        w = MessageWidget(
            text, is_user=is_user,
            agent_color=self.agent_color,
            attachments=attachments,
            file_chips=file_chips,
            artifact_chips=artifact_chips,
            agent_name=self.agent_name,
        )
        w.artifact_open_requested.connect(self.artifact_open_requested)
        self.msg_layout.insertWidget(self.msg_layout.count() - 1, w)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        QTimer.singleShot(50, lambda: self.scroll.verticalScrollBar().setValue(
            self.scroll.verticalScrollBar().maximum()
        ))


# ── Marker helpers ────────────────────────────────────────────────────────────

def _extract_file_markers(text: str) -> tuple[list[str], str, list[dict]]:
    file_pat = re.compile(r"\[\[DESK_FILE:(.+?)\]\]")
    filenames = file_pat.findall(text)
    text = file_pat.sub("", text)

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