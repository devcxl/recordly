"""Tests for core/audio_mix.compose_audio — 时间轴音频合成（方案 §9.1）"""

import wave

import numpy as np
import pytest

from core.project import AudioRegion


def _write_wav(path: str, data, samplerate: int):
    """写入 16-bit PCM WAV（等价 app/main_window._write_wav 逻辑，纯 wave 模块）"""
    arr = np.asarray(data, dtype=np.float32)
    arr = np.clip(arr, -1.0, 1.0)
    if arr.ndim == 1:
        channels = 1
        arr = arr.reshape(-1, 1)
    else:
        channels = arr.shape[1]
    samples = (arr * 32767).astype(np.int16)
    with wave.open(path, "w") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(samplerate)
        wf.writeframes(samples.tobytes())


def _region(path: str, start_ms=0.0, end_ms=5.0, source_start_ms=0.0,
            source_end_ms=5.0, volume=1.0) -> AudioRegion:
    return AudioRegion(
        start_ms=start_ms,
        end_ms=end_ms,
        source_start_ms=source_start_ms,
        source_end_ms=source_end_ms,
        audio_path=path,
        volume=volume,
    )


class TestNoEditEquivalence:
    def test_two_full_length_regions_match_mix_audio_results(self, tmp_path):
        from core.audio_capture import mix_audio_results, read_wav
        from core.audio_mix import compose_audio

        samplerate = 1000
        mic_data = np.array([
            [0.10, -0.20], [0.30, 0.40], [-0.50, 0.60],
            [0.70, -0.80], [0.90, 1.00],
        ], dtype=np.float32)
        sys_data = np.array([
            [0.05, 0.15], [-0.25, 0.35], [0.45, -0.55],
            [0.65, 0.75], [-0.85, 0.95],
        ], dtype=np.float32)
        mic_path = str(tmp_path / "mic.wav")
        sys_path = str(tmp_path / "sys.wav")
        _write_wav(mic_path, mic_data, samplerate)
        _write_wav(sys_path, sys_data, samplerate)

        regions = [_region(mic_path), _region(sys_path)]
        expected = mix_audio_results(
            read_wav(mic_path), read_wav(sys_path)).data
        actual = compose_audio(regions, samplerate)

        assert actual is not None
        assert actual.dtype == np.float32
        np.testing.assert_allclose(actual, expected, rtol=1e-6, atol=1e-6)


class TestEditSemantics:
    """编辑语义：删除=静音 / volume / source 切片 / start 移动"""

    def test_deleted_region_interval_is_silent(self, tmp_path):
        from core.audio_mix import compose_audio

        samplerate = 1000
        mic_data = np.full((5, 2), 0.5, dtype=np.float32)
        sys_data = np.full((5, 2), 0.25, dtype=np.float32)
        mic_path = str(tmp_path / "mic.wav")
        sys_path = str(tmp_path / "sys.wav")
        _write_wav(mic_path, mic_data, samplerate)
        _write_wav(sys_path, sys_data, samplerate)

        # mic 全时长 + sys 从 2ms 开始；删除 mic region → 前 2ms 静音
        regions = [_region(sys_path, start_ms=2.0)]
        out = compose_audio(regions, samplerate)

        assert out is not None
        np.testing.assert_allclose(out[:2], 0.0, atol=1e-7)
        np.testing.assert_allclose(
            out[2:], np.full((3, 2), 0.25, dtype=np.float32),
            rtol=1e-3, atol=1e-3)

    @pytest.mark.parametrize("volume, scale", [(1.0, 1.0), (0.5, 0.5), (0.0, 0.0)])
    def test_volume_scales_samples(self, tmp_path, volume, scale):
        from core.audio_capture import read_wav
        from core.audio_mix import compose_audio

        samplerate = 1000
        data = np.array([
            [0.1, 0.2], [0.3, 0.4], [0.5, 0.6], [0.7, 0.8], [0.9, 1.0],
        ], dtype=np.float32)
        path = str(tmp_path / "a.wav")
        _write_wav(path, data, samplerate)

        out = compose_audio([_region(path, volume=volume)], samplerate)

        assert out is not None
        np.testing.assert_allclose(
            out, read_wav(path).data * scale, rtol=1e-4, atol=1e-4)

    def test_source_crop_only_keeps_window(self, tmp_path):
        from core.audio_mix import compose_audio

        samplerate = 1000
        data = np.array([
            [0.1, 0.2], [0.3, 0.4], [0.5, 0.6], [0.7, 0.8], [0.9, 1.0],
        ], dtype=np.float32)
        path = str(tmp_path / "a.wav")
        _write_wav(path, data, samplerate)

        # 只取源 1ms-3ms 窗口 → 窗口内容从时间轴 0 连续播放
        # （剪辑语义，与 audio_extra filtergraph atrim→asetpts→adelay 一致）；
        # 总时长仍按 end_ms=5，窗口外为静音
        out = compose_audio(
            [_region(path, source_start_ms=1.0, source_end_ms=3.0)],
            samplerate)

        assert out is not None
        np.testing.assert_allclose(out[:2], data[1:3], rtol=1e-3, atol=1e-3)
        np.testing.assert_allclose(out[2:], 0.0, atol=1e-7)

    def test_start_offset_shifts_samples(self, tmp_path):
        from core.audio_mix import compose_audio

        samplerate = 1000
        data = np.array([
            [0.1, 0.2], [0.3, 0.4], [0.5, 0.6], [0.7, 0.8], [0.9, 1.0],
        ], dtype=np.float32)
        path = str(tmp_path / "a.wav")
        _write_wav(path, data, samplerate)

        # start_ms=2 → 样本从第 2 帧开始，前 2 帧为 0；输出长度取 end_ms=7
        out = compose_audio([_region(path, start_ms=2.0, end_ms=7.0)], samplerate)

        assert out is not None
        assert out.shape == (7, 2)
        np.testing.assert_allclose(out[:2], 0.0, atol=1e-7)
        np.testing.assert_allclose(out[2:], data, rtol=1e-3, atol=1e-3)


class TestResampling:
    def test_different_sample_rate_keeps_signal_shape(self, tmp_path):
        from core.audio_mix import compose_audio

        src_sr, target_sr = 2000, 1000
        t = np.arange(src_sr) / src_sr
        sine = np.sin(2 * np.pi * 2 * t).astype(np.float32)
        stereo = np.column_stack([sine, sine])
        path = str(tmp_path / "extra.wav")
        _write_wav(path, stereo, src_sr)

        out = compose_audio(
            [_region(path, end_ms=1000.0, source_end_ms=1000.0)],
            target_sr, duration=1.0)

        assert out is not None
        assert out.shape[0] == round(1.0 * target_sr)  # 1000 帧
        # 2Hz 正弦在目标采样率的形状保留：峰值位于 0.125s/0.625s
        # （帧 125/625），过零位于 0.25s（帧 250）
        assert out[125, 0] > 0.99
        assert out[625, 0] > 0.99
        assert abs(out[250, 0]) < 0.05


class TestMissingFiles:
    def test_missing_file_is_skipped(self, tmp_path):
        from core.audio_capture import read_wav
        from core.audio_mix import compose_audio

        samplerate = 1000
        data = np.full((5, 2), 0.5, dtype=np.float32)
        path = str(tmp_path / "a.wav")
        _write_wav(path, data, samplerate)

        missing = str(tmp_path / "missing.wav")
        out = compose_audio([_region(missing), _region(path)], samplerate)

        assert out is not None
        np.testing.assert_allclose(out, read_wav(path).data, rtol=1e-3, atol=1e-3)

    def test_all_missing_returns_none(self, tmp_path):
        from core.audio_mix import compose_audio

        missing = str(tmp_path / "missing.wav")
        assert compose_audio(
            [_region(missing), _region(str(tmp_path / "nope.wav"))], 1000) is None

    def test_empty_regions_returns_none(self, tmp_path):
        from core.audio_mix import compose_audio
        assert compose_audio([], 1000) is None


class TestDuration:
    def test_duration_truncates_output(self, tmp_path):
        from core.audio_mix import compose_audio

        samplerate = 1000
        data = np.array([
            [0.1, 0.2], [0.3, 0.4], [0.5, 0.6], [0.7, 0.8], [0.9, 1.0],
        ], dtype=np.float32)
        path = str(tmp_path / "a.wav")
        _write_wav(path, data, samplerate)

        out = compose_audio([_region(path)], samplerate, duration=0.003)

        assert out is not None
        assert out.shape == (3, 2)
        np.testing.assert_allclose(out, data[:3], rtol=1e-3, atol=1e-3)

    def test_duration_defaults_to_max_region_end(self, tmp_path):
        from core.audio_capture import read_wav
        from core.audio_mix import compose_audio

        samplerate = 1000
        mic_data = np.full((5, 2), 0.4, dtype=np.float32)
        sys_data = np.full((10, 2), 0.2, dtype=np.float32)
        mic_path = str(tmp_path / "mic.wav")
        sys_path = str(tmp_path / "sys.wav")
        _write_wav(mic_path, mic_data, samplerate)
        _write_wav(sys_path, sys_data, samplerate)

        # 未给定 duration → 输出长度 = max(region.end_ms) = 10ms
        out = compose_audio([
            _region(mic_path, end_ms=5.0),
            _region(sys_path, end_ms=10.0, source_end_ms=10.0),
        ], samplerate)

        assert out is not None
        assert out.shape == (10, 2)
        # 前 5ms 两者叠加，后 5ms 仅 sys
        np.testing.assert_allclose(out[:5], 0.4 + 0.2, rtol=1e-2, atol=1e-2)
        np.testing.assert_allclose(
            out[5:], read_wav(sys_path).data[5:], rtol=1e-3, atol=1e-3)
