"""RecordingController 状态机测试"""

import pytest
from app.recording_controller import (
    RecordingController, RecordingState,
    RecordingStartError, RecordingStopError,
)


class FakeConfig:
    default_fps = 30


class TestRecordingController:
    def test_initial_state_is_idle(self):
        from unittest.mock import MagicMock
        config = FakeConfig()
        ctrl = RecordingController(config)
        ctrl._recorder = MagicMock()
        assert ctrl.state == RecordingState.IDLE

    def test_start_transitions_to_recording(self, monkeypatch):
        from unittest.mock import MagicMock
        import core.recorder as recorder_module
        monkeypatch.setattr(recorder_module, "ScreenCapture", MagicMock())
        monkeypatch.setattr(recorder_module, "MicrophoneCapture", MagicMock())
        monkeypatch.setattr(recorder_module, "SystemAudioCapture", MagicMock())
        monkeypatch.setattr(recorder_module, "PointerTracker", MagicMock())

        config = FakeConfig()
        ctrl = RecordingController(config)

        states = []
        ctrl.set_callbacks(on_state_changed=lambda s: states.append(s))

        # Mock start_recording to not actually try to start hardware
        monkeypatch.setattr(ctrl._recorder, "start_recording", lambda *a, **kw: None)

        ctrl.start("/tmp/test_project")
        assert states == [RecordingState.STARTING, RecordingState.RECORDING]
        assert ctrl.state == RecordingState.RECORDING

    def test_start_failure_returns_to_idle(self, monkeypatch):
        from unittest.mock import MagicMock
        import core.recorder as recorder_module
        monkeypatch.setattr(recorder_module, "ScreenCapture", MagicMock())
        monkeypatch.setattr(recorder_module, "MicrophoneCapture", MagicMock())
        monkeypatch.setattr(recorder_module, "SystemAudioCapture", MagicMock())
        monkeypatch.setattr(recorder_module, "PointerTracker", MagicMock())

        config = FakeConfig()
        ctrl = RecordingController(config)

        monkeypatch.setattr(ctrl._recorder, "start_recording",
                            lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("mic error")))

        with pytest.raises(RecordingStartError, match="mic error"):
            ctrl.start("/tmp/test")
        assert ctrl.state == RecordingState.IDLE

    def test_stop_returns_data(self, monkeypatch):
        from unittest.mock import MagicMock
        import core.recorder as recorder_module
        monkeypatch.setattr(recorder_module, "ScreenCapture", MagicMock())
        monkeypatch.setattr(recorder_module, "MicrophoneCapture", MagicMock())
        monkeypatch.setattr(recorder_module, "SystemAudioCapture", MagicMock())
        monkeypatch.setattr(recorder_module, "PointerTracker", MagicMock())

        config = FakeConfig()
        ctrl = RecordingController(config)

        expected = {"frames": [], "audio": None}
        monkeypatch.setattr(ctrl._recorder, "start_recording", lambda *a, **kw: None)
        monkeypatch.setattr(ctrl._recorder, "stop_recording", lambda: expected)

        ctrl.start("/tmp/test")
        result = ctrl.stop()
        assert result is expected
        assert ctrl.state == RecordingState.IDLE

    def test_stop_failure_raises_stop_error(self, monkeypatch):
        from unittest.mock import MagicMock
        import core.recorder as recorder_module
        monkeypatch.setattr(recorder_module, "ScreenCapture", MagicMock())
        monkeypatch.setattr(recorder_module, "MicrophoneCapture", MagicMock())
        monkeypatch.setattr(recorder_module, "SystemAudioCapture", MagicMock())
        monkeypatch.setattr(recorder_module, "PointerTracker", MagicMock())

        config = FakeConfig()
        ctrl = RecordingController(config)

        monkeypatch.setattr(ctrl._recorder, "start_recording", lambda *a, **kw: None)
        monkeypatch.setattr(ctrl._recorder, "stop_recording",
                            lambda: (_ for _ in ()).throw(RuntimeError("screen error")))

        ctrl.start("/tmp/test")
        with pytest.raises(RecordingStopError, match="screen error") as exc_info:
            ctrl.stop()
        assert exc_info.value.recoverable is True
        assert ctrl.state == RecordingState.IDLE

    def test_double_start_raises(self, monkeypatch):
        from unittest.mock import MagicMock
        import core.recorder as recorder_module
        monkeypatch.setattr(recorder_module, "ScreenCapture", MagicMock())
        monkeypatch.setattr(recorder_module, "MicrophoneCapture", MagicMock())
        monkeypatch.setattr(recorder_module, "SystemAudioCapture", MagicMock())
        monkeypatch.setattr(recorder_module, "PointerTracker", MagicMock())

        config = FakeConfig()
        ctrl = RecordingController(config)

        monkeypatch.setattr(ctrl._recorder, "start_recording", lambda *a, **kw: None)
        ctrl.start("/tmp/test")
        with pytest.raises(RuntimeError):
            ctrl.start("/tmp/test")
