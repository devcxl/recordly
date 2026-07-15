"""导出控制器 — QObject，管理 QThread + ExportWorker 生命周期"""

import numpy as np
from PyQt5.QtCore import QObject, QThread, pyqtSignal

from core.compositor import Compositor
from core.exporter import ExportWorker, ExportSettings


class ExportController(QObject):
    """导出控制器。唯一的 QObject Controller，管理导出线程生命周期。"""

    export_finished = pyqtSignal(object)
    export_progress = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: ExportWorker | None = None

    @property
    def is_exporting(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def start_export(self, compositor: Compositor,
                     audio_data: np.ndarray | None,
                     settings: ExportSettings):
        if self.is_exporting:
            raise RuntimeError("已有导出进行中")
        self._worker = ExportWorker(compositor, audio_data, settings)
        self._worker.progress.connect(self.export_progress)
        self._thread = QThread(self)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_worker_finished)
        self._thread.start()

    def cancel(self):
        if self._worker:
            self._worker.cancel()

    def _on_worker_finished(self, result):
        self.export_finished.emit(result)
        if self._thread:
            self._thread.quit()
            self._thread.wait(5000)
            self._thread.deleteLater()
            self._thread = None
        if self._worker:
            self._worker.deleteLater()
            self._worker = None

    def cleanup(self):
        self.cancel()
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(3000)
