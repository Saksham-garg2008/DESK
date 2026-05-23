"""
ComputeManager — Controls threading behavior across the app.
High: non-blocking, multiple agents can run concurrently.
Low: serial, one inference at a time, kills background tasks.
"""
from __future__ import annotations
from PySide6.QtCore import QThreadPool, QRunnable, QObject, Signal, Slot
from core.config_loader import get_app_setting, set_app_setting


class WorkerSignals(QObject):
    chunk = Signal(str)
    finished = Signal()
    error = Signal(str)


class InferenceWorker(QRunnable):
    def __init__(self, generator_fn, *args, **kwargs):
        super().__init__()
        self.generator_fn = generator_fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self._cancelled = False
        self.setAutoDelete(True)

    def cancel(self):
        self._cancelled = True

    @Slot()
    def run(self):
        try:
            for chunk in self.generator_fn(*self.args, **self.kwargs):
                if self._cancelled:
                    break
                self.signals.chunk.emit(chunk)
            if not self._cancelled:
                self.signals.finished.emit()
        except Exception as e:
            self.signals.error.emit(str(e))


class ComputeManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self.mode = get_app_setting("compute_mode", "high")
        self._active_workers: list[InferenceWorker] = []
        self.pool = QThreadPool.globalInstance()
        if self.mode == "high":
            self.pool.setMaxThreadCount(4)
        else:
            self.pool.setMaxThreadCount(1)

    def set_mode(self, mode: str):
        assert mode in ("high", "low")
        self.mode = mode
        set_app_setting("compute_mode", mode)
        if mode == "low":
            self.kill_all()
            self.pool.setMaxThreadCount(1)
        else:
            self.pool.setMaxThreadCount(4)

    def run(self, worker: InferenceWorker):
        if self.mode == "low":
            self.kill_all()
        self._active_workers.append(worker)
        worker.signals.finished.connect(lambda: self._cleanup(worker))
        self.pool.start(worker)

    def kill_all(self):
        for w in self._active_workers:
            w.cancel()
        self._active_workers.clear()

    def _cleanup(self, worker: InferenceWorker):
        if worker in self._active_workers:
            self._active_workers.remove(worker)

    @property
    def is_high(self) -> bool:
        return self.mode == "high"
