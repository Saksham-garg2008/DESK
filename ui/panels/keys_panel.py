"""
Keys Panel — API key management per backend.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QScrollArea, QFrame
)
from PySide6.QtCore import Qt

from core.config_loader import get_key, set_key, load_models_config


CLOUD_BACKENDS = ["openai", "anthropic", "gemini", "mistral", "groq", "openrouter"]

BACKEND_INFO = {
    "openai":      ("OpenAI",        "https://platform.openai.com/api-keys",     "sk-..."),
    "anthropic":   ("Anthropic",     "https://console.anthropic.com/keys",       "sk-ant-..."),
    "gemini":      ("Google Gemini", "https://aistudio.google.com/apikey",       "AIza..."),
    "mistral":     ("Mistral AI",    "https://console.mistral.ai/api-keys",      "..."),
    "groq":        ("Groq",          "https://console.groq.com/keys",            "gsk_..."),
    "openrouter":  ("OpenRouter",    "https://openrouter.ai/keys",               "sk-or-..."),
}


class KeyRow(QWidget):
    def __init__(self, backend: str, parent=None):
        super().__init__(parent)
        self.backend = backend
        info = BACKEND_INFO.get(backend, (backend, "", ""))
        label_text, url, placeholder = info

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Label row
        label_row = QHBoxLayout()
        name_label = QLabel(label_text)
        name_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #C8C8CE;")
        label_row.addWidget(name_label)
        label_row.addStretch()

        if url:
            link = QLabel(f'<a href="{url}" style="color: #5A5A7E; font-size: 11px; text-decoration: none;">Get API key →</a>')
            link.setOpenExternalLinks(True)
            label_row.addWidget(link)

        layout.addLayout(label_row)

        # Input + save row
        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        self.input = QLineEdit()
        self.input.setEchoMode(QLineEdit.Password)
        self.input.setPlaceholderText(placeholder or "Enter API key...")
        existing = get_key(backend)
        if existing:
            self.input.setText(existing)
        input_row.addWidget(self.input, 1)

        self.toggle_btn = QPushButton("Show")
        self.toggle_btn.setObjectName("key_save_btn")
        self.toggle_btn.setFixedWidth(52)
        self.toggle_btn.clicked.connect(self._toggle_visibility)
        input_row.addWidget(self.toggle_btn)

        save_btn = QPushButton("Save")
        save_btn.setObjectName("key_save_btn")
        save_btn.setFixedWidth(52)
        save_btn.clicked.connect(self._save)
        input_row.addWidget(save_btn)

        layout.addLayout(input_row)

        # Wrapper card
        self.setStyleSheet("""
            QWidget {
                background-color: #222226;
                border-radius: 10px;
                padding: 4px;
            }
        """)
        self.setContentsMargins(16, 12, 16, 12)

    def _toggle_visibility(self):
        if self.input.echoMode() == QLineEdit.Password:
            self.input.setEchoMode(QLineEdit.Normal)
            self.toggle_btn.setText("Hide")
        else:
            self.input.setEchoMode(QLineEdit.Password)
            self.toggle_btn.setText("Show")

    def _save(self):
        value = self.input.text().strip()
        set_key(self.backend, value)


class KeysPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
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
        layout.setSpacing(24)

        title = QLabel("API Keys")
        title.setObjectName("panel_title")
        layout.addWidget(title)

        desc = QLabel(
            "Keys are stored locally on your machine. Never shared. Never sent anywhere except the provider you configure."
        )
        desc.setStyleSheet("color: #4A4A4E; font-size: 12px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Divider
        div = QFrame()
        div.setObjectName("divider")
        div.setFrameShape(QFrame.HLine)
        layout.addWidget(div)

        # Ollama note
        ollama_card = QWidget()
        ollama_card.setStyleSheet("background-color: #1E2A1E; border-radius: 10px;")
        ollama_layout = QVBoxLayout(ollama_card)
        ollama_layout.setContentsMargins(16, 12, 16, 12)

        ollama_title = QLabel("🖥  Ollama (Local — No Key Required)")
        ollama_title.setStyleSheet("font-size: 13px; font-weight: 600; color: #6AAF7A;")
        ollama_desc = QLabel(
            "Ollama runs locally on your machine. Install from ollama.com, then pull any model.\n"
            "Example: open Terminal and run  ollama pull llama3.2:3b"
        )
        ollama_desc.setStyleSheet("color: #4A6A4E; font-size: 12px; line-height: 1.5;")
        ollama_desc.setWordWrap(True)

        ollama_layout.addWidget(ollama_title)
        ollama_layout.addWidget(ollama_desc)
        layout.addWidget(ollama_card)

        # Cloud backend keys
        section = QLabel("CLOUD PROVIDERS")
        section.setObjectName("section_label")
        layout.addWidget(section)

        for backend in CLOUD_BACKENDS:
            row = KeyRow(backend)
            layout.addWidget(row)

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)
