"""补录音频窗口 — 独立录音对话框（方案 §7.1）

复用 core.audio_capture.MicrophoneCapture（sounddevice 回调线程，UI 不阻塞）；
mic_factory 构造参数为测试注入点（FakeCapture）。
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox,
)
from PyQt5.QtCore import QTimer

from core.audio_capture import MicrophoneCapture, AudioResult


class RecordAudioDialog(QDialog):
    """独立补录窗口。开始/结束按钮 + 计时显示 + 取消。"""

    def __init__(self, parent=None, mic_factory=MicrophoneCapture):
        super().__init__(parent)
        self.setWindowTitle("补录音频")
        self.setMinimumWidth(320)

        self._mic_factory = mic_factory
        self._capture = None
        self._audio_result = None
        self._recording = False
        self._elapsed_s = 0

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._on_tick)

        self._time_label = QLabel("00:00")
        self._time_label.setAlignment(self._time_label.AlignCenter)

        self._btn_start = QPushButton("开始录音")
        self._btn_start.clicked.connect(self._on_start)
        self._btn_stop = QPushButton("结束录音")
        self._btn_stop.clicked.connect(self._on_stop)
        self._btn_stop.setEnabled(False)
        self._btn_cancel = QPushButton("取消")
        self._btn_cancel.clicked.connect(self.reject)

        buttons = QHBoxLayout()
        buttons.addWidget(self._btn_start)
        buttons.addWidget(self._btn_stop)
        buttons.addWidget(self._btn_cancel)

        layout = QVBoxLayout(self)
        layout.addWidget(self._time_label)
        layout.addLayout(buttons)

    @property
    def audio_result(self) -> AudioResult | None:
        """结束录音后返回采集到的音频；未完成/取消/无效为 None。"""
        return self._audio_result

    def _on_start(self):
        if self._recording:
            return
        self._capture = self._mic_factory()
        self._capture.start()
        self._recording = True
        self._elapsed_s = 0
        self._time_label.setText("00:00")
        self._btn_start.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._timer.start()

    def _on_stop(self):
        if not self._recording:
            return
        self._timer.stop()
        result = self._capture.stop()
        self._recording = False
        self._btn_stop.setEnabled(False)

        duration = 0.0
        if result is not None and result.samplerate > 0:
            duration = len(result.data) / result.samplerate
        if duration <= 0:
            QMessageBox.warning(self, "录音无效", "未捕获到有效音频，请重试")
            self.reject()
            return
        self._audio_result = result
        self.accept()

    def _on_tick(self):
        self._elapsed_s += 1
        self._time_label.setText(f"{self._elapsed_s // 60:02d}:{self._elapsed_s % 60:02d}")

    def reject(self):
        """关闭/取消：录音未结束时 stop 并丢弃数据。"""
        if self._recording and self._capture is not None:
            self._timer.stop()
            self._capture.stop()
            self._recording = False
            self._btn_stop.setEnabled(False)
        super().reject()
