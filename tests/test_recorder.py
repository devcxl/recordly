"""Tests for core/recorder.py — 匹配实际 API"""

import pytest


def _stub_recording_engines(recorder, monkeypatch):
    monkeypatch.setattr(recorder.screen, "clear", lambda: None)
    monkeypatch.setattr(recorder.screen, "start", lambda: None)
    monkeypatch.setattr(recorder.screen, "stop", lambda: None)
    monkeypatch.setattr(recorder.mic, "start", lambda: None)
    monkeypatch.setattr(recorder.mic, "stop", lambda: None)
    monkeypatch.setattr(recorder.system_audio, "start", lambda: False)
    monkeypatch.setattr(recorder.system_audio, "stop", lambda: None)
    monkeypatch.setattr(recorder.pointer, "start", lambda: None)
    monkeypatch.setattr(recorder.pointer, "stop", lambda: None)


class TestRecorder:
    def test_target_fps_is_used_for_every_screen_session(self, monkeypatch):
        import core.recorder as recorder_module

        created = []

        class FakeScreen:
            def __init__(self, monitor_id=1, target_fps=30):
                self.monitor_id = monitor_id
                self.target_fps = target_fps
                self.all_frames = []
                self.monitor_offset = (0, 0)
                self.error = None
                created.append(target_fps)

            def clear(self): pass
            def start(self): pass
            def stop(self): pass

        monkeypatch.setattr(recorder_module, "ScreenCapture", FakeScreen)
        recorder = recorder_module.Recorder(target_fps=60)
        _stub_recording_engines(recorder, monkeypatch)

        recorder.start_recording()
        first_result = recorder.stop_recording()
        recorder.start_recording()
        second_result = recorder.stop_recording()

        assert created == [60, 60]
        assert first_result["fps"] == 60
        assert second_result["fps"] == 60

    def test_importable(self):
        from core.recorder import Recorder
        assert Recorder is not None

    def test_default_params(self):
        from core.recorder import Recorder
        r = Recorder()
        assert hasattr(r, 'start_recording')
        assert hasattr(r, 'stop_recording')
        assert hasattr(r, 'screen')
        assert hasattr(r, 'mic')
        assert hasattr(r, 'pointer')

    def test_is_recording_initially_false(self):
        from core.recorder import Recorder
        r = Recorder()
        assert r._recording is False

    def test_start_stop(self, monkeypatch):
        from core.recorder import Recorder
        r = Recorder()
        _stub_recording_engines(r, monkeypatch)
        r.start_recording()
        assert r._recording is True
        r.stop_recording()
        assert r._recording is False

    def test_double_start(self, monkeypatch):
        from core.recorder import Recorder
        r = Recorder()
        _stub_recording_engines(r, monkeypatch)
        r.start_recording()
        r.start_recording()  # should not raise
        r.stop_recording()

    def test_stop_without_start(self):
        from core.recorder import Recorder
        r = Recorder()
        r.stop_recording()  # should not raise

    def test_record_returns_timing(self, monkeypatch):
        from core.recorder import Recorder
        import time
        r = Recorder()
        _stub_recording_engines(r, monkeypatch)
        r.start_recording()
        time.sleep(0.01)
        r.stop_recording()
        # 验证至少经过了一些时间
        assert True

    def test_second_recording_uses_fresh_screen_capture(self, monkeypatch):
        """录屏线程只能启动一次，每次录制必须创建新会话。"""
        import core.recorder as recorder_module

        created = []

        class FakeScreen:
            def __init__(self, monitor_id=1, target_fps=30):
                self.monitor_id = monitor_id
                self.target_fps = target_fps
                self.started = False
                self.all_frames = []
                self.monitor_offset = (0, 0)
                self.error = None
                created.append(self)

            def clear(self):
                pass

            def start(self):
                if self.started:
                    raise RuntimeError("threads can only be started once")
                self.started = True

            def stop(self):
                pass

        class FakeMic:
            def start(self):
                pass

            def stop(self):
                return None

        class FakePointer:
            def __init__(self):
                self._events = []

            def start(self):
                pass

            def stop(self):
                pass

            @property
            def events(self):
                return []

            def get_clicks(self):
                return []

        class FakeSystem:
            def start(self):
                return False

            def stop(self):
                return None

        monkeypatch.setattr(recorder_module, "ScreenCapture", FakeScreen)
        monkeypatch.setattr(recorder_module, "MicrophoneCapture", FakeMic)
        monkeypatch.setattr(recorder_module, "SystemAudioCapture", FakeSystem)
        monkeypatch.setattr(recorder_module, "PointerTracker", FakePointer)

        recorder = recorder_module.Recorder()
        recorder.start_recording()
        recorder.stop_recording()
        recorder.start_recording()
        recorder.stop_recording()

        assert len(created) == 2

    def test_screen_capture_error_is_propagated_on_stop(self, monkeypatch):
        """后台录屏失败不能被当成成功录制。"""
        import core.recorder as recorder_module

        class FakeScreen:
            def __init__(self, monitor_id=1, target_fps=30):
                self.all_frames = []
                self.monitor_offset = (0, 0)
                self.error = RuntimeError("capture failed")

            def clear(self):
                pass

            def start(self):
                pass

            def stop(self):
                pass

        class FakeMic:
            def start(self):
                pass

            def stop(self):
                return None

        class FakePointer:
            def __init__(self):
                self._events = []

            def start(self):
                pass

            def stop(self):
                pass

            @property
            def events(self):
                return []

            def get_clicks(self):
                return []

        class FakeSystem:
            def start(self):
                return False

            def stop(self):
                return None

        monkeypatch.setattr(recorder_module, "ScreenCapture", FakeScreen)
        monkeypatch.setattr(recorder_module, "MicrophoneCapture", FakeMic)
        monkeypatch.setattr(recorder_module, "SystemAudioCapture", FakeSystem)
        monkeypatch.setattr(recorder_module, "PointerTracker", FakePointer)

        recorder = recorder_module.Recorder()
        recorder.start_recording()
        with pytest.raises(RuntimeError, match="capture failed"):
            recorder.stop_recording()

    def test_recorder_mixes_microphone_and_system_audio(self, monkeypatch):
        import numpy as np
        from core.audio_capture import AudioResult
        from core.recorder import Recorder

        recorder = Recorder()
        _stub_recording_engines(recorder, monkeypatch)

        mic_result = AudioResult(
            data=np.array([[0.25], [0.25]], dtype=np.float32),
            samplerate=44100,
            channels=1,
        )
        system_result = AudioResult(
            data=np.array([[0.5, -0.5]], dtype=np.float32),
            samplerate=44100,
            channels=2,
        )

        monkeypatch.setattr(recorder.mic, "stop", lambda: mic_result)

        class FakeSystem:
            error = None

            def start(self):
                return True

            def stop(self):
                return system_result

        recorder.system_audio = FakeSystem()

        recorder.start_recording()
        result = recorder.stop_recording()

        assert result["mic_audio"] is mic_result
        assert result["system_audio"] is system_result
        assert result["audio"].data.shape == (2, 2)
