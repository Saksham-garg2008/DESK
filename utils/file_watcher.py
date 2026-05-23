"""
FileWatcher — Watches the bucket/ folder for .md changes.
Emits signals when agents are hired (file added) or fired (file deleted).
"""
from pathlib import Path
from PySide6.QtCore import QFileSystemWatcher, QObject, Signal


BUCKET_DIR = Path(__file__).parent.parent / "bucket"


class FileWatcher(QObject):
    agent_hired = Signal(str)   # agent name
    agent_fired = Signal(str)   # agent name

    def __init__(self, parent=None):
        super().__init__(parent)
        BUCKET_DIR.mkdir(exist_ok=True)
        self._known = self._scan()
        self._watcher = QFileSystemWatcher([str(BUCKET_DIR)], self)
        self._watcher.directoryChanged.connect(self._on_change)

    def _scan(self) -> set[str]:
        return {p.stem for p in BUCKET_DIR.glob("*.md")}

    def _on_change(self):
        current = self._scan()
        hired = current - self._known
        fired = self._known - current
        for name in hired:
            self.agent_hired.emit(name)
        for name in fired:
            self.agent_fired.emit(name)
        self._known = current

    def all_agents(self) -> list[str]:
        return sorted(self._scan())
