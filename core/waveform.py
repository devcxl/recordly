"""音频波形降采样与缩略图辅助 — 纯函数，无 Qt 依赖"""

import numpy as np


def compute_waveform_peaks(data: np.ndarray, samplerate: float,
                           start_s: float, end_s: float,
                           speed: float, bucket_count: int,
                           channel: int = 0) -> list[float]:
    """计算 clip 源时间范围内 [start_s, end_s) 的峰值包络（每 bucket 一个峰值）。

    时间线 clip 的源窗口 = [source_start, source_end)（秒），按 speed 映射：
    时间线 1s 对应源 speed 秒。bucket_count 为 clip 像素宽对应的分段数。

    Returns:
        bucket_count 个 0.0~1.0 的归一化峰值；数据不足时补 0。
    """
    if data is None or len(data) == 0 or samplerate <= 0:
        return [0.0] * bucket_count
    if bucket_count <= 0:
        return []

    source = np.asarray(data)
    if source.ndim == 1:
        source = source.reshape(-1, 1)
    channel = min(channel, source.shape[1] - 1)
    mono = np.abs(source[:, channel].astype(np.float32))

    src_start = int(max(0, start_s * samplerate))
    src_end = int(min(len(mono), end_s * samplerate))
    if src_end <= src_start:
        return [0.0] * bucket_count

    window = mono[src_start:src_end]
    peaks = []
    window_size = max(1, len(window) // bucket_count)
    for b in range(bucket_count):
        lo = b * window_size
        hi = min(len(window), lo + window_size)
        if hi > lo:
            peaks.append(float(window[lo:hi].max()))
        else:
            peaks.append(0.0)
    peak_max = max(peaks) if peaks else 1.0
    if peak_max <= 0:
        return [0.0] * bucket_count
    return [p / peak_max for p in peaks]
