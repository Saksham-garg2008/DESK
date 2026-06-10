"""
WorkspacePanel — Modal panel showing all agent workspaces and their artifacts.

Layout:
- Search bar (filters agents by name)
- List of agent "folders" (cards) with artifact count + last modified
- Click agent → expands to show all artifacts
- Click artifact → emits signal to open CodeInspectorPanel

Design: matches DESK dark theme. Raised cards, colored dots per agent.
"""
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QFrame, QLineEdit,
    QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor

from core.artifact_manager import ArtifactManager
from core.config_loader import load_agents_config

LANG_DISPLAY = {
    "python": "Python", "py": "Python",
    "javascript": "JavaScript", "js": "JavaScript",
    "typescript": "TypeScript", "ts": "TypeScript",
    "html": "HTML", "css": "CSS", "scss": "SCSS",
    "sass": "SASS", "less": "LESS", "json": "JSON",
    "yaml": "YAML", "yml": "YAML", "sql": "SQL",
    "bash": "Bash", "sh": "Shell", "shell": "Shell",
    "go": "Go", "rust": "Rust", "rs": "Rust",
    "java": "Java", "kotlin": "Kotlin", "kt": "Kotlin",
    "swift": "Swift", "cpp": "C++", "c": "C",
    "cs": "C#", "csharp": "C#", "php": "PHP",
    "ruby": "Ruby", "rb": "Ruby", "r": "R",
    "jsx": "React JSX", "tsx": "React TSX",
    "vue": "Vue", "svelte": "Svelte",
    "markdown": "Markdown", "md": "Markdown",
    "toml": "TOML", "xml": "XML",
    "dockerfile": "Dockerfile", "makefile": "Makefile",
}


class ArtifactRowWidget(QWidget):
    """Single artifact row inside an expanded agent folder."""
    open_requested = Signal(str, str)  # agent_name, filename

    def __init__(self, agent_name: str, filename: str, artifact: dict, parent=None):
        super().__init__(parent)
        self.agent_name = agent_name
        self.filename = filename
        self.artifact = artifact
        self.setCursor(Qt.PointingHandCursor)
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        # File icon
        icon = QLabel("📄")
        icon.setStyleSheet("font-size: 13px;")
        icon.setFixedWidth(20)
        layout.addWidget(icon)

        # Filename
        name_lbl = QLabel(self.filename)
        name_lbl.setStyleSheet(
            "font-size: 12px; color: #C0C0CC; font-weight: 500;"
        )
        layout.addWidget(name_lbl, 1)

        # Version badge
        ver = self.artifact.get("current_version", 1)
        total_vers = len(self.artifact.get("versions", []))
        ver_lbl = QLabel(f"v{ver}")
        ver_lbl.setStyleSheet(
            "font-size: 10px; color: #505068; background: #1E1E2A; "
            "border-radius: 4px; padding: 2px 7px; font-weight: 600;"
        )
        layout.addWidget(ver_lbl)

        # Language badge
        lang = self.artifact.get("language", "")
        lang_display = LANG_DISPLAY.get(lang, lang.upper() if lang else "")
        if lang_display:
            lang_lbl = QLabel(lang_display)
            lang_lbl.setStyleSheet(
                "font-size: 10px; color: #404058; "
                "padding: 2px 6px; font-weight: 500;"
            )
            layout.addWidget(lang_lbl)

        # Last modified
        versions = self.artifact.get("versions", [])
        if versions:
            ts = versions[-1].get("timestamp", "")
            try:
                dt = datetime.fromisoformat(ts)
                now = datetime.now()
                diff = now - dt
                if diff.days == 0:
                    if diff.seconds < 3600:
                        time_str = f"{diff.seconds // 60}m ago"
                    else:
                        time_str = f"{diff.seconds // 3600}h ago"
                elif diff.days == 1:
                    time_str = "Yesterday"
                else:
                    time_str = dt.strftime("%b %d")
            except Exception:
                time_str = ""
            if time_str:
                time_lbl = QLabel(time_str)
                time_lbl.setStyleSheet("font-size: 10px; color: #383848;")
                layout.addWidget(time_lbl)

        self.setStyleSheet("""
            QWidget {
                background: transparent;
                border-radius: 6px;
            }
            QWidget:hover {
                background: #1E1E2C;
            }
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.open_requested.emit(self.agent_name, self.filename)


class AgentFolderWidget(QWidget):
    """
    Collapsible agent folder card.
    Shows agent color dot + name + artifact count.
    Expands to show artifact rows on click.
    """
    artifact_open_requested = Signal(str, str)  # agent_name, filename

    def __init__(self, agent_name: str, color: str, parent=None):
        super().__init__(parent)
        self.agent_name = agent_name
        self.agent_color = color
        self._expanded = False
        self._build_ui()

    def _build_ui(self):
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)
        self._outer.setSpacing(0)

        # ── Header row ────────────────────────────────────────────────────
        self._header = QWidget()
        self._header.setCursor(Qt.PointingHandCursor)
        self._header.setFixedHeight(52)
        self._header.setStyleSheet("""
            QWidget {
                background: #1E1E26;
                border-radius: 10px;
                border: 1px solid #2A2A34;
            }
            QWidget:hover {
                background: #22222E;
                border-color: #363646;
            }
        """)
        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(14, 0, 14, 0)
        header_layout.setSpacing(10)

        # Color dot
        dot = QWidget()
        dot.setFixedSize(10, 10)
        dot.setStyleSheet(
            f"background-color: {self.agent_color}; border-radius: 5px;"
        )
        header_layout.addWidget(dot)

        # Agent name
        self._name_lbl = QLabel(self.agent_name)
        self._name_lbl.setStyleSheet(
            "font-size: 13px; font-weight: 600; color: #D8D8E2;"
        )
        header_layout.addWidget(self._name_lbl)
        header_layout.addStretch()

        # Artifact count
        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet("font-size: 11px; color: #404055;")
        header_layout.addWidget(self._count_lbl)

        # Expand chevron
        self._chevron = QLabel("›")
        self._chevron.setStyleSheet("font-size: 14px; color: #383850;")
        self._chevron.setFixedWidth(16)
        header_layout.addWidget(self._chevron)

        self._outer.addWidget(self._header)

        # ── Expanded artifacts area ────────────────────────────────────────
        self._artifacts_widget = QWidget()
        self._artifacts_widget.setStyleSheet(
            "background: #19191F; border-radius: 0 0 10px 10px; "
            "border: 1px solid #232330; border-top: none;"
        )
        self._artifacts_layout = QVBoxLayout(self._artifacts_widget)
        self._artifacts_layout.setContentsMargins(8, 8, 8, 8)
        self._artifacts_layout.setSpacing(2)
        self._artifacts_widget.setVisible(False)
        self._outer.addWidget(self._artifacts_widget)

        self._header.mousePressEvent = self._toggle

    def _toggle(self, event=None):
        self._expanded = not self._expanded
        self._artifacts_widget.setVisible(self._expanded)
        self._chevron.setText("⌄" if self._expanded else "›")
        if self._expanded:
            self._header.setStyleSheet("""
                QWidget {
                    background: #22222E;
                    border-radius: 10px 10px 0 0;
                    border: 1px solid #363646;
                    border-bottom: none;
                }
            """)
        else:
            self._header.setStyleSheet("""
                QWidget {
                    background: #1E1E26;
                    border-radius: 10px;
                    border: 1px solid #2A2A34;
                }
                QWidget:hover {
                    background: #22222E;
                    border-color: #363646;
                }
            """)

    def refresh(self):
        """Reload artifacts from ArtifactManager."""
        am = ArtifactManager()
        artifacts = am.get_agent_artifacts(self.agent_name)

        # Update count label
        count = len(artifacts)
        if count == 0:
            self._count_lbl.setText("No artifacts")
        elif count == 1:
            self._count_lbl.setText("1 artifact")
        else:
            self._count_lbl.setText(f"{count} artifacts")

        # Rebuild artifacts list
        while self._artifacts_layout.count():
            item = self._artifacts_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not artifacts:
            empty_lbl = QLabel("No artifacts yet")
            empty_lbl.setStyleSheet(
                "font-size: 11px; color: #2A2A38; padding: 8px 12px;"
            )
            self._artifacts_layout.addWidget(empty_lbl)
        else:
            for filename, artifact in artifacts.items():
                row = ArtifactRowWidget(self.agent_name, filename, artifact)
                row.open_requested.connect(self.artifact_open_requested)
                self._artifacts_layout.addWidget(row)

    def set_expanded(self, expanded: bool):
        if expanded != self._expanded:
            self._toggle()


class WorkspacePanel(QWidget):
    """
    Modal workspace panel — shows all agent folders + their artifacts.
    Opened from topbar button.
    """
    artifact_open_requested = Signal(str, str)  # agent_name, filename

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("workspace_panel")
        self._agent_folders: dict[str, AgentFolderWidget] = {}
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Panel header ──────────────────────────────────────────────────
        header = QWidget()
        header.setObjectName("workspace_header")
        header.setFixedHeight(54)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 0, 16, 0)
        header_layout.setSpacing(0)

        title = QLabel("WORKSPACE")
        title.setStyleSheet(
            "font-size: 11px; font-weight: 700; color: #3A3A50; letter-spacing: 2px;"
        )
        header_layout.addWidget(title)
        header_layout.addStretch()

        layout.addWidget(header)

        # ── Search bar ────────────────────────────────────────────────────
        search_wrapper = QWidget()
        search_wrapper.setStyleSheet(
            "background: #18181B; border-bottom: 1px solid #222228;"
        )
        search_layout = QHBoxLayout(search_wrapper)
        search_layout.setContentsMargins(16, 8, 16, 8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search agents…")
        self.search_input.setFixedHeight(32)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background: #1E1E26;
                border: 1px solid #2A2A34;
                border-radius: 8px;
                padding: 4px 12px;
                font-size: 12px;
                color: #C0C0CC;
            }
            QLineEdit:focus {
                border-color: #383850;
                background: #20202A;
            }
        """)
        self.search_input.textChanged.connect(self._filter_agents)
        search_layout.addWidget(self.search_input)

        layout.addWidget(search_wrapper)

        # ── Scroll area for agent folders ─────────────────────────────────
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("""
            QScrollArea {
                background: #18181B;
                border: none;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 4px;
            }
            QScrollBar::handle:vertical {
                background: #2A2A36;
                border-radius: 2px;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical { height: 0; }
        """)

        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background: #18181B;")
        self.folders_layout = QVBoxLayout(self.scroll_content)
        self.folders_layout.setContentsMargins(16, 16, 16, 16)
        self.folders_layout.setSpacing(8)
        self.folders_layout.addStretch()

        # Empty state label
        self.empty_label = QLabel("No agents yet.\nCreate one with Ctrl+N.")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet(
            "font-size: 12px; color: #2A2A38; line-height: 1.8;"
        )
        self.folders_layout.insertWidget(0, self.empty_label)

        self.scroll.setWidget(self.scroll_content)
        layout.addWidget(self.scroll, 1)

    # ── Public API ─────────────────────────────────────────────────────────

    def refresh(self):
        """
        Rebuild the agent folder list from config + artifact manager.
        Call whenever agents change (hire/fire/edit) or artifacts change.
        """
        agents_cfg = load_agents_config().get("agents", {})

        # Determine which agents to show
        # Show ALL agents (even those with 0 artifacts)
        all_agents = dict(agents_cfg)

        # Remove folders for agents that no longer exist
        for name in list(self._agent_folders.keys()):
            if name not in all_agents:
                folder = self._agent_folders.pop(name)
                self.folders_layout.removeWidget(folder)
                folder.deleteLater()

        # Add/update folders
        for name, cfg in all_agents.items():
            color = cfg.get("color", "#5B7FA6")
            if name not in self._agent_folders:
                folder = AgentFolderWidget(name, color)
                folder.artifact_open_requested.connect(self.artifact_open_requested)
                insert_idx = max(0, self.folders_layout.count() - 1)
                self.folders_layout.insertWidget(insert_idx, folder)
                self._agent_folders[name] = folder
            else:
                # Update color if changed
                self._agent_folders[name].agent_color = color

            self._agent_folders[name].refresh()

        # Show/hide empty state
        self.empty_label.setVisible(len(all_agents) == 0)
        self._filter_agents(self.search_input.text())

    def refresh_agent(self, agent_name: str):
        """Refresh just one agent's folder (after new artifact)."""
        if agent_name in self._agent_folders:
            self._agent_folders[agent_name].refresh()

    def remove_agent(self, agent_name: str):
        """Remove agent folder (called on Fire)."""
        if agent_name in self._agent_folders:
            folder = self._agent_folders.pop(agent_name)
            self.folders_layout.removeWidget(folder)
            folder.deleteLater()
        self.empty_label.setVisible(len(self._agent_folders) == 0)

    def rename_agent(self, old_name: str, new_name: str, new_color: str):
        """Handle agent rename."""
        self.refresh()  # Simplest — full refresh

    # ── Private ────────────────────────────────────────────────────────────

    def _filter_agents(self, query: str):
        q = query.strip().lower()
        for name, folder in self._agent_folders.items():
            folder.setVisible(q == "" or q in name.lower())