"""Tests for core/audio_capture.py — 匹配实际 API"""

import pytest


class TestAudioResult:
    def test_importable(self):
        from core.audio_capture import AudioResult
        assert AudioResult is not None

    def test_fields(self):
        from core.audio_capture import AudioResult
        import numpy as np
        r = AudioResult(data=np.array([0.1, 0.2]), samplerate=44100, channels=2)
        assert r.samplerate == 44100
        assert r.channels == 2

    def test_empty_data(self):
        from core.audio_capture import AudioResult
        import numpy as np
        r = AudioResult(data=np.array([]), samplerate=16000, channels=1)
        assert len(r.data) == 0


class TestMicrophoneCapture:
    def test_importable(self):
        from core.audio_capture import MicrophoneCapture
        assert MicrophoneCapture is not None

    def test_default_params(self):
        from core.audio_capture import MicrophoneCapture
        mc = MicrophoneCapture()
        assert mc.samplerate == 44100
        assert mc.channels == 2

    def test_custom_samplerate(self):
        from core.audio_capture import MicrophoneCapture
        mc = MicrophoneCapture(samplerate=16000)
        assert mc.samplerate == 16000

    def test_start_stop(self):
        from core.audio_capture import MicrophoneCapture
        mc = MicrophoneCapture()
        mc.start()
        result = mc.stop()
        assert result is not None

    def test_stop_without_start(self):
        from core.audio_capture import MicrophoneCapture
        mc = MicrophoneCapture()
        result = mc.stop()
        assert result is not None


class TestSystemAudioCapture:
    def test_importable(self):
        from core.audio_capture import SystemAudioCapture
        assert SystemAudioCapture is not None

    def test_default_params(self):
        from core.audio_capture import SystemAudioCapture
        sac = SystemAudioCapture()
        assert sac.samplerate == 44100

    @pytest.mark.skip(reason="需要系统装有 ffmpeg + pulseaudio")
    def test_start_stop(self):
        from core.audio_capture import SystemAudioCapture
        sac = SystemAudioCapture()
        sac.start()
        sac.stop()  # should not raise
