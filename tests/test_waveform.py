"""core/waveform.py 纯函数测试"""

import numpy as np
import pytest


class TestComputeWaveformPeaks:
    def test_empty_data_returns_zeros(self):
        from core.waveform import compute_waveform_peaks

        assert compute_waveform_peaks(None, 44100, 0, 1, 1.0, 10) == [0.0] * 10

    def test_normalized_peaks_in_range(self):
        from core.waveform import compute_waveform_peaks

        data = np.sin(np.linspace(0, 100, 44100)).astype(np.float32)
        peaks = compute_waveform_peaks(data, 44100, 0, 1.0, 1.0, 50)

        assert len(peaks) == 50
        assert all(0.0 <= p <= 1.0 for p in peaks)
        assert max(peaks) == pytest.approx(1.0)

    def test_out_of_range_window_returns_zeros(self):
        from core.waveform import compute_waveform_peaks

        data = np.zeros(44100, dtype=np.float32)
        peaks = compute_waveform_peaks(data, 44100, 10, 11, 1.0, 8)

        assert peaks == [0.0] * 8

    def test_speed_maps_window(self):
        """0.5x 速度：时间线 1s 对应源 2s，峰值应来自前 2s 数据。"""
        from core.waveform import compute_waveform_peaks

        data = np.zeros(44100 * 3, dtype=np.float32)
        data[:44100] = 1.0  # 前 1s 为高幅
        fast = compute_waveform_peaks(data, 44100, 0, 1.0, 1.0, 4)
        slow = compute_waveform_peaks(data, 44100, 0, 1.0, 0.5, 4)

        assert max(fast) == pytest.approx(1.0)
        # 0.5x 时窗口覆盖源 2s，前 1s 高幅仍应被采样到
        assert max(slow) == pytest.approx(1.0)

    def test_stereo_uses_channel(self):
        from core.waveform import compute_waveform_peaks

        data = np.zeros((44100, 2), dtype=np.float32)
        data[:44100, 1] = 0.8
        peaks = compute_waveform_peaks(data, 44100, 0, 1.0, 1.0, 5, channel=1)

        assert max(peaks) == pytest.approx(1.0)

    def test_zero_bucket_count(self):
        from core.waveform import compute_waveform_peaks

        data = np.ones(1000, dtype=np.float32)
        assert compute_waveform_peaks(data, 44100, 0, 1, 1.0, 0) == []
