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

    def test_stereo_failure_retries_with_mono(self, monkeypatch):
        import core.audio_capture as audio_module

        requested_channels = []

        class FakeStream:
            def __init__(self, channels):
                self.channels = channels

            def start(self):
                if self.channels == 2:
                    raise RuntimeError("stereo unsupported")

            def stop(self):
                pass

            def close(self):
                pass

        def make_stream(**kwargs):
            requested_channels.append(kwargs["channels"])
            return FakeStream(kwargs["channels"])

        monkeypatch.setattr(audio_module.sd, "InputStream", make_stream)

        capture = audio_module.MicrophoneCapture(channels=2)
        capture.start()
        result = capture.stop()

        assert requested_channels == [2, 1]
        assert result.channels == 1


class TestSystemAudioCapture:
    def test_importable(self):
        from core.audio_capture import SystemAudioCapture
        assert SystemAudioCapture is not None

    def test_default_params(self):
        from core.audio_capture import SystemAudioCapture
        sac = SystemAudioCapture()
        assert sac.samplerate == 44100

    def test_linux_command_uses_default_monitor_and_raw_pcm(self, monkeypatch):
        import core.audio_capture as audio_module

        monkeypatch.setattr(audio_module.sys, "platform", "linux")
        cmd = audio_module.SystemAudioCapture()._build_cmd()

        assert "@DEFAULT_MONITOR@" in cmd
        assert cmd[-2:] == ["s16le", "pipe:1"]

    def test_unsupported_platform_is_non_fatal(self, monkeypatch):
        import core.audio_capture as audio_module

        monkeypatch.setattr(audio_module.sys, "platform", "darwin")
        capture = audio_module.SystemAudioCapture()

        assert capture.start() is False
        assert isinstance(capture.error, RuntimeError)


class TestMixAudioResults:
    def test_mixes_mono_and_stereo_with_zero_padding(self):
        import numpy as np
        from core.audio_capture import AudioResult, mix_audio_results

        mono = AudioResult(
            data=np.array([[0.5], [0.5]], dtype=np.float32),
            samplerate=44100,
            channels=1,
        )
        stereo = AudioResult(
            data=np.array([[0.25, -0.25]], dtype=np.float32),
            samplerate=44100,
            channels=2,
        )

        mixed = mix_audio_results(mono, stereo)

        assert mixed.channels == 2
        assert mixed.data.shape == (2, 2)
        assert mixed.data[0].tolist() == pytest.approx([0.75, 0.25])
        assert mixed.data[1].tolist() == pytest.approx([0.5, 0.5])

    def test_single_mono_input_is_expanded_to_stereo(self):
        import numpy as np
        from core.audio_capture import AudioResult, mix_audio_results

        mono = AudioResult(
            data=np.array([[0.25], [-0.25]], dtype=np.float32),
            samplerate=44100,
            channels=1,
        )

        mixed = mix_audio_results(mono)

        assert mixed.channels == 2
        np.testing.assert_allclose(mixed.data, [
            [0.25, 0.25], [-0.25, -0.25],
        ])

    @pytest.mark.skip(reason="需要系统装有 ffmpeg + pulseaudio")
    def test_start_stop(self):
        from core.audio_capture import SystemAudioCapture
        sac = SystemAudioCapture()
        sac.start()
        sac.stop()  # should not raise
