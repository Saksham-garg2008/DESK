"""
DESK — Main Window
Fixes:
- Refresh NEVER deletes history or config. It only reloads UI.
- Colors preserved on refresh (config not wiped).
- Right-click agent strip → Edit or Fire context menu.
- Fire button in topbar (fires the currently active agent).
"""
import sys
import os
from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QStackedWidget, QSizePolicy,
    QScrollArea, QFrame, QApplication, QMenu, QDialog
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut, QFont, QColor, QPainter, QPen

from utils.file_watcher import FileWatcher
from ui.dialogs.add_agent_dialog import NewAgentDialog
from ui.dialogs.edit_agent_dialog import EditAgentDialog
from ui.panels.chat_panel import ChatPanel, ConfirmDialog
from ui.panels.settings_panel import SettingsPanel
from ui.panels.keys_panel import KeysPanel
from core.history_manager import delete_agent_history
from core.config_loader import (
    get_agent_config, load_agents_config, delete_agent_config,
    get_app_setting, set_app_setting
)

BUCKET_DIR = Path(__file__).parent.parent / "bucket"


class AgentStrip(QPushButton):
    """A single horizontal colored strip on The Pole."""

    def __init__(self, name: str, color: str, parent=None):
        super().__init__(parent)
        self.agent_name = name
        self.agent_color = color
        self.setFixedSize(52, 88)
        self.setCursor(Qt.PointingHandCursor)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self._active = False
        self._apply_style()

    def update_color(self, color: str):
        self.agent_color = color
        self._apply_style()

    def set_active(self, active: bool):
        self._active = active
        self._apply_style()

    def _apply_style(self):
        border = (
            "border-left: 3px solid rgba(255,255,255,0.75);"
            if self._active else
            "border-left: 3px solid transparent;"
        )
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.agent_color};
                border: none;
                {border}
                border-radius: 0px;
            }}
            QPushButton:hover {{
                background-color: {self._lighten(self.agent_color)};
            }}
        """)
        self.setText("")
        self.update()

    def _lighten(self, hex_color: str) -> str:
        try:
            c = QColor(hex_color)
            h, s, v, a = c.getHsvF()
            v = min(1.0, v + 0.12)
            c.setHsvF(h, s, v, a)
            return c.name()
        except Exception:
            return hex_color

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        painter.save()
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(-90)
        font = QFont("SF Pro Display", 9, QFont.DemiBold)
        font.setLetterSpacing(QFont.AbsoluteSpacing, 0.6)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255, 200))
        name = self.agent_name
        if len(name) > 10:
            name = name[:9] + "…"
        rect_w = self.height() - 16
        painter.drawText(
            -rect_w // 2, -self.width() // 2 + 10,
            rect_w, self.width(), Qt.AlignCenter, name
        )
        painter.restore()
        painter.end()


class WelcomeScreen(QWidget):
    new_agent_requested = __import__('PySide6.QtCore', fromlist=['Signal']).Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("welcome")
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(16)

        title = QLabel("DESK")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            "font-size: 42px; font-weight: 200; color: #2A2A2E; letter-spacing: 8px;"
        )
        layout.addWidget(title)

        sub = QLabel("your AI office")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet(
            "font-size: 13px; color: #2A2A2E; font-weight: 400; letter-spacing: 1px;"
        )
        layout.addWidget(sub)
        layout.addSpacing(32)

        btn = QPushButton("+ New Agent")
        btn.setObjectName("welcome_new_btn")
        btn.setFixedWidth(200)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(self.new_agent_requested)
        layout.addWidget(btn, alignment=Qt.AlignCenter)

        hint = QLabel("or press  Ctrl+N")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("font-size: 11px; color: #2A2A2E;")
        layout.addWidget(hint)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DESK")
        self.setMinimumSize(900, 640)
        self._restore_geometry()

        self._agent_strips: dict[str, AgentStrip] = {}
        self._agent_panels: dict[str, ChatPanel] = {}
        self._active_agent: str | None = None

        self._build_ui()
        self._load_stylesheet()
        self._setup_shortcuts()
        self._setup_file_watcher()
        self._load_existing_agents()

    # ── UI Build ───────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)

        main_layout = QHBoxLayout(root)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── The Pole ─────────────────────────────────────────────────
        self.sidebar = QWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(52)

        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        self.pole_top = QVBoxLayout()
        self.pole_top.setContentsMargins(0, 0, 0, 0)
        self.pole_top.setSpacing(0)
        sidebar_layout.addLayout(self.pole_top)

        strips_scroll = QScrollArea()
        strips_scroll.setWidgetResizable(True)
        strips_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        strips_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        strips_scroll.setStyleSheet("background: transparent; border: none;")

        self.strips_container = QWidget()
        self.strips_container.setStyleSheet("background: transparent;")
        self.strips_layout = QVBoxLayout(self.strips_container)
        self.strips_layout.setContentsMargins(0, 0, 0, 0)
        self.strips_layout.setSpacing(0)
        self.strips_layout.addStretch()

        strips_scroll.setWidget(self.strips_container)
        sidebar_layout.addWidget(strips_scroll, 1)

        self.pole_bottom = QVBoxLayout()
        self.pole_bottom.setContentsMargins(0, 0, 0, 0)
        self.pole_bottom.setSpacing(0)
        sidebar_layout.addLayout(self.pole_bottom)

        self._build_pole_icons()
        main_layout.addWidget(self.sidebar)

        # ── Right side ────────────────────────────────────────────────
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self._build_topbar(right_layout)

        self.stack = QStackedWidget()
        self.stack.setObjectName("center")

        self.welcome = WelcomeScreen()
        self.welcome.new_agent_requested.connect(self._open_new_agent_dialog)
        self.stack.addWidget(self.welcome)

        self.settings_panel = SettingsPanel()
        self.stack.addWidget(self.settings_panel)

        self.keys_panel = KeysPanel()
        self.stack.addWidget(self.keys_panel)

        right_layout.addWidget(self.stack, 1)
        main_layout.addWidget(right, 1)

    def _build_pole_icons(self):
        new_btn = self._pole_icon_btn("＋", "New Agent (Ctrl+N)", self._open_new_agent_dialog)
        self.pole_top.addWidget(new_btn)

        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet("background-color: #222228;")
        self.pole_top.addWidget(div)

        div2 = QFrame()
        div2.setFixedHeight(1)
        div2.setStyleSheet("background-color: #222228;")
        self.pole_bottom.addWidget(div2)

        self.pole_bottom.addWidget(self._pole_icon_btn("⚙", "Settings", self._show_settings))
        self.pole_bottom.addWidget(self._pole_icon_btn("🔑", "API Keys", self._show_keys))
        self.pole_bottom.addWidget(self._pole_icon_btn("↺", "Refresh", self._refresh_app))

    def _pole_icon_btn(self, icon: str, tooltip: str, callback) -> QPushButton:
        btn = QPushButton(icon)
        btn.setFixedSize(52, 44)
        btn.setToolTip(tooltip)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                font-size: 16px;
                color: #3A3A42;
            }
            QPushButton:hover {
                background-color: #222228;
                color: #7A7A84;
            }
        """)
        btn.clicked.connect(callback)
        return btn

    def _build_topbar(self, parent_layout):
        topbar = QWidget()
        topbar.setObjectName("topbar")
        topbar.setFixedHeight(44)

        layout = QHBoxLayout(topbar)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(10)

        self.topbar_title = QLabel("DESK")
        self.topbar_title.setStyleSheet(
            "font-size: 12px; font-weight: 700; color: #303036; letter-spacing: 3px;"
        )
        layout.addWidget(self.topbar_title)
        layout.addStretch()

        # Compute mode pill
        self.compute_pill = QPushButton()
        self._update_compute_pill()
        self.compute_pill.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #252530;
                border-radius: 4px;
                padding: 3px 10px;
                font-size: 10px;
                color: #404050;
                font-weight: 600;
                letter-spacing: 0.5px;
            }
            QPushButton:hover {
                border-color: #353545;
                color: #606070;
            }
        """)
        self.compute_pill.clicked.connect(self._toggle_compute_mode)
        layout.addWidget(self.compute_pill)

        # ── Fire Agent button ────────────────────────────────────────
        self.fire_btn = QPushButton("🔥 Fire Agent")
        self.fire_btn.setToolTip("Fire (delete) the currently active agent")
        self.fire_btn.setVisible(False)  # Hidden until an agent is active
        self.fire_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3A1A1E,
                    stop:1 #2A1216
                );
                border: 1px solid #5A2A2E;
                border-bottom: 2px solid #180A0C;
                border-radius: 8px;
                padding: 5px 14px;
                font-size: 12px;
                font-weight: 600;
                color: #C06060;
            }
            QPushButton:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4A2224,
                    stop:1 #381A1C
                );
                color: #E07070;
                border-color: #7A3A3E;
            }
            QPushButton:pressed {
                background: #22101 2;
                border-bottom: 1px solid #180A0C;
                padding-top: 6px;
                padding-bottom: 4px;
            }
        """)
        self.fire_btn.clicked.connect(self._fire_active_agent)
        layout.addWidget(self.fire_btn)

        # New Agent button
        new_btn = QPushButton("+ New Agent")
        new_btn.setObjectName("new_agent_btn")
        new_btn.clicked.connect(self._open_new_agent_dialog)
        layout.addWidget(new_btn)

        parent_layout.addWidget(topbar)

    # ── Agent Management ───────────────────────────────────────────────────

    def _load_existing_agents(self):
        """
        Load agents from bucket/ — reads config for color.
        NEVER deletes anything.
        """
        agents_cfg = load_agents_config().get("agents", {})
        for md_file in sorted(BUCKET_DIR.glob("*.md"), key=lambda p: p.stem):
            agent_name = md_file.stem
            cfg = agents_cfg.get(agent_name, {})
            color = cfg.get("color", "#5B7FA6")
            self._add_agent_to_pole(agent_name, color)

        if self._agent_strips:
            self._activate_agent(next(iter(self._agent_strips)))
        else:
            self.stack.setCurrentWidget(self.welcome)

    def _add_agent_to_pole(self, name: str, color: str):
        if name in self._agent_strips:
            return

        strip = AgentStrip(name, color)
        strip.clicked.connect(lambda checked, n=name: self._activate_agent(n))
        strip.customContextMenuRequested.connect(
            lambda pos, n=name: self._show_agent_context_menu(n, pos)
        )

        insert_idx = max(0, self.strips_layout.count() - 1)
        self.strips_layout.insertWidget(insert_idx, strip)
        self._agent_strips[name] = strip

        panel = ChatPanel(name, color)
        self.stack.addWidget(panel)
        self._agent_panels[name] = panel

    def _activate_agent(self, name: str):
        if name not in self._agent_panels:
            return

        if self._active_agent and self._active_agent in self._agent_strips:
            self._agent_strips[self._active_agent].set_active(False)

        self._active_agent = name
        self._agent_strips[name].set_active(True)
        self.stack.setCurrentWidget(self._agent_panels[name])
        self.topbar_title.setText(name.upper())
        self.fire_btn.setVisible(True)

    def _hard_remove_agent(self, name: str):
        """
        Permanently remove agent: UI + config + bucket file + history.
        Called only from Fire actions.
        """
        # Remove UI
        if name in self._agent_strips:
            strip = self._agent_strips.pop(name)
            self.strips_layout.removeWidget(strip)
            strip.deleteLater()

        if name in self._agent_panels:
            panel = self._agent_panels.pop(name)
            self.stack.removeWidget(panel)
            panel.deleteLater()

        # Remove data
        md_path = BUCKET_DIR / f"{name}.md"
        if md_path.exists():
            md_path.unlink()
        delete_agent_config(name)
        delete_agent_history(name)

        # Navigate away
        if self._active_agent == name:
            self._active_agent = None
            self.fire_btn.setVisible(False)
            if self._agent_strips:
                self._activate_agent(next(iter(self._agent_strips)))
            else:
                self.stack.setCurrentWidget(self.welcome)
                self.topbar_title.setText("DESK")

    def _soft_remove_agent(self, name: str):
        """
        Remove agent from UI only — used by refresh.
        Does NOT delete config, history, or bucket files.
        """
        if name in self._agent_strips:
            strip = self._agent_strips.pop(name)
            self.strips_layout.removeWidget(strip)
            strip.deleteLater()

        if name in self._agent_panels:
            panel = self._agent_panels.pop(name)
            self.stack.removeWidget(panel)
            panel.deleteLater()

    # ── Fire Agent ─────────────────────────────────────────────────────────

    def _fire_active_agent(self):
        if not self._active_agent:
            return
        name = self._active_agent
        dlg = ConfirmDialog(
            f"Fire {name}?",
            f"This will permanently delete {name} and all their chat history. "
            "The agent's .md file will be removed from bucket/. This cannot be undone.",
            parent=self
        )
        dlg.setStyleSheet(self.styleSheet())
        if dlg.exec() == QDialog.Accepted:
            self._hard_remove_agent(name)
            self.settings_panel.refresh()

    # ── Right-click Context Menu ───────────────────────────────────────────

    def _show_agent_context_menu(self, name: str, pos):
        strip = self._agent_strips.get(name)
        if not strip:
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1E1E24;
                border: 1px solid #2E2E38;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 8px 20px;
                color: #C8C8D4;
                font-size: 13px;
                border-radius: 5px;
            }
            QMenu::item:selected {
                background-color: #2A2A36;
                color: #E0E0EC;
            }
            QMenu::separator {
                height: 1px;
                background: #2A2A32;
                margin: 3px 8px;
            }
        """)

        edit_action = menu.addAction(f"✏️  Edit {name}")
        menu.addSeparator()
        fire_action = menu.addAction(f"🔥  Fire {name}")
        fire_action.setData("fire")

        chosen = menu.exec(strip.mapToGlobal(pos))
        if chosen == edit_action:
            self._open_edit_agent_dialog(name)
        elif chosen == fire_action:
            self._confirm_fire_agent(name)

    def _confirm_fire_agent(self, name: str):
        dlg = ConfirmDialog(
            f"Fire {name}?",
            f"This will permanently delete {name} and all their chat history. "
            "The agent's .md file will be removed from bucket/. This cannot be undone.",
            parent=self
        )
        dlg.setStyleSheet(self.styleSheet())
        if dlg.exec() == QDialog.Accepted:
            self._hard_remove_agent(name)
            self.settings_panel.refresh()

    # ── Edit Agent ─────────────────────────────────────────────────────────

    def _open_edit_agent_dialog(self, name: str):
        dlg = EditAgentDialog(name, parent=self)
        dlg.setStyleSheet(self.styleSheet())
        dlg.agent_updated.connect(self._on_agent_updated)
        dlg.exec()

    def _on_agent_updated(self, old_name: str, new_name: str, color: str):
        """
        Handle agent edit result.
        If name changed: rebuild UI entry under new name.
        If only color/config changed: update strip color in place.
        """
        if old_name != new_name:
            # Name changed — soft remove old, add new
            was_active = (self._active_agent == old_name)
            self._soft_remove_agent(old_name)
            self._add_agent_to_pole(new_name, color)
            if was_active:
                self._activate_agent(new_name)
        else:
            # Just update color in existing strip and panel
            if old_name in self._agent_strips:
                self._agent_strips[old_name].update_color(color)
            if old_name in self._agent_panels:
                self._agent_panels[old_name].agent_color = color

        self.settings_panel.refresh()

    # ── Refresh ────────────────────────────────────────────────────────────

    def _refresh_app(self):
        """
        Soft reload: tear down UI widgets, rebuild from disk.
        NEVER deletes history, config, or bucket files.
        Config and history are read fresh from disk after reload.
        """
        previously_active = self._active_agent

        # Soft-remove all agents (UI only — no data deleted)
        for name in list(self._agent_strips.keys()):
            self._soft_remove_agent(name)

        self._active_agent = None
        self.fire_btn.setVisible(False)
        self.topbar_title.setText("DESK")

        # Reload stylesheet
        self._load_stylesheet()

        # Rebuild from disk
        self._load_existing_agents()
        self.settings_panel.refresh()

        # Restore previously active agent if it still exists
        if previously_active and previously_active in self._agent_strips:
            self._activate_agent(previously_active)

    # ── Panels ─────────────────────────────────────────────────────────────

    def _open_new_agent_dialog(self):
        dlg = NewAgentDialog(self)
        dlg.setStyleSheet(self.styleSheet())
        dlg.agent_created.connect(self._on_agent_created)
        dlg.exec()

    def _on_agent_created(self, name: str, color: str):
        self._add_agent_to_pole(name, color)
        self._activate_agent(name)
        self.settings_panel.refresh()

    def _show_settings(self):
        self.settings_panel.refresh()
        self.stack.setCurrentWidget(self.settings_panel)
        if self._active_agent and self._active_agent in self._agent_strips:
            self._agent_strips[self._active_agent].set_active(False)
        self._active_agent = None
        self.fire_btn.setVisible(False)
        self.topbar_title.setText("SETTINGS")

    def _show_keys(self):
        self.stack.setCurrentWidget(self.keys_panel)
        if self._active_agent and self._active_agent in self._agent_strips:
            self._agent_strips[self._active_agent].set_active(False)
        self._active_agent = None
        self.fire_btn.setVisible(False)
        self.topbar_title.setText("API KEYS")

    # ── Compute Mode ───────────────────────────────────────────────────────

    def _toggle_compute_mode(self):
        from core.compute_manager import ComputeManager
        cm = ComputeManager()
        cm.set_mode("low" if cm.mode == "high" else "high")
        self._update_compute_pill()

    def _update_compute_pill(self):
        mode = get_app_setting("compute_mode", "high")
        self.compute_pill.setText("⚡ HIGH" if mode == "high" else "🔋 LOW")

    # ── File Watcher ───────────────────────────────────────────────────────

    def _setup_file_watcher(self):
        self.file_watcher = FileWatcher(self)
        self.file_watcher.agent_hired.connect(self._on_agent_hired)
        self.file_watcher.agent_fired.connect(self._on_agent_fired)

    def _on_agent_hired(self, name: str):
        cfg = get_agent_config(name)
        color = cfg.get("color", "#5B7FA6")
        self._add_agent_to_pole(name, color)
        self.settings_panel.refresh()

    def _on_agent_fired(self, name: str):
        # File deleted externally (from file manager, not DESK UI)
        self._hard_remove_agent(name)
        self.settings_panel.refresh()

    # ── Shortcuts ──────────────────────────────────────────────────────────

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(
            self._open_new_agent_dialog
        )
        QShortcut(QKeySequence("Shift+Tab"), self).activated.connect(
            self._cycle_agents
        )
        QShortcut(QKeySequence("Ctrl+,"), self).activated.connect(
            self._show_settings
        )

    def _cycle_agents(self):
        names = list(self._agent_strips.keys())
        if not names:
            return
        if self._active_agent not in names:
            self._activate_agent(names[0])
            return
        idx = names.index(self._active_agent)
        self._activate_agent(names[(idx + 1) % len(names)])

    # ── Stylesheet & Geometry ──────────────────────────────────────────────

    def _load_stylesheet(self):
        qss_path = Path(__file__).parent / "styles" / "theme.qss"
        if qss_path.exists():
            self.setStyleSheet(qss_path.read_text(encoding="utf-8"))

    def _restore_geometry(self):
        w = get_app_setting("window", {}).get("width", 1200)
        h = get_app_setting("window", {}).get("height", 800)
        self.resize(w, h)

    def closeEvent(self, event):
        set_app_setting("window", {
            "width": self.width(),
            "height": self.height(),
        })
        super().closeEvent(event)
