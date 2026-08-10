"""RecordAudioDialog（麦克风补录窗口）交互测试。

FakeCapture 经 mic_factory 注入，验证开始/结束/关闭/0 秒四种交互路径：
- 开始 → 结束：audio_result 为 FakeCapture 返回的 AudioResult，对话框 Accepted
- 直接关闭（reject）：audio_result 为 None 且 FakeCapture 被 stop（丢弃数据）
- 0 秒数据：对话框 Rejected 且 audio_result 为 None
"""

import numpy as np
import pytest

from core.audio_capture import AudioResult


class FakeCapture:
    """记录调用次数并返回预设 AudioResult 的假采集器。"""

    def __init__(self, result):
        self.result = result
        self.started = 0
        self.stopped = 0

    def start(self):
        self.started += 1

    def stop(self):
        self.stopped += 1
        return self.result


def _make_dialog(result):
    """以 FakeCapture 为注入点构造 RecordAudioDialog"""
    from ui.record_audio_dialog import RecordAudioDialog

    return RecordAudioDialog(mic_factory=lambda: FakeCapture(result))


def test_start_then_stop_yields_audio_result(qapp):
    """点开始 → 结束：audio_result 为 FakeCapture 返回的 AudioResult，且 Accepted"""
    from PyQt5.QtWidgets import QDialog

    result = AudioResult(np.zeros(48000), samplerate=48000, channels=1)
    dialog = _make_dialog(result)

    dialog._btn_start.click()
    dialog._btn_stop.click()

    assert dialog.audio_result is result
    assert dialog.result() == QDialog.Accepted


def test_close_without_stop_discards_and_stops_capture(qapp):
    """直接关闭/取消（未点结束）：audio_result 为 None，且 FakeCapture 被 stop 丢弃"""
    result = AudioResult(np.zeros(48000), samplerate=48000, channels=1)
    capture = FakeCapture(result)
    from ui.record_audio_dialog import RecordAudioDialog

    dialog = RecordAudioDialog(mic_factory=lambda: capture)
    dialog._btn_start.click()

    dialog.reject()  # 模拟关闭窗口 / 取消

    assert dialog.audio_result is None
    assert capture.started == 1
    assert capture.stopped == 1


def test_zero_second_recording_rejects(qapp, monkeypatch):
    """0 秒数据：对话框 Rejected 且 audio_result 为 None（不产生文件）"""
    from PyQt5.QtWidgets import QDialog

    import ui.record_audio_dialog as dialog_module

    monkeypatch.setattr(
        dialog_module.QMessageBox, "warning", lambda *args, **kwargs: None)

    result = AudioResult(np.array([]), samplerate=48000, channels=1)
    dialog = _make_dialog(result)

    dialog._btn_start.click()
    dialog._btn_stop.click()

    assert dialog.result() == QDialog.Rejected
    assert dialog.audio_result is None
