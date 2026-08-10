"""音频时间轴合成 — 纯 numpy 内存合成（无 Qt/FFmpeg 依赖）"""

import numpy as np

from core.audio_capture import read_wav
from core.project import AudioRegion


def compose_audio(regions: list[AudioRegion], samplerate: int,
                  duration: float | None = None) -> np.ndarray | None:
    """按 AudioRegion 列表合成时间轴音频。

    - 每个 region：读取 audio_path（缺失文件跳过）→ 按 source_start/source_end
      切片 → × volume → 定位到 start_ms。
    - 采样率 ≠ samplerate 的 region 先用 np.interp 重采样（线性插值）。
    - 各 region 逐样本相加，clip 到 [-1.0, 1.0]；
      输出声道数 = max(2, 各输入声道数)。
    - duration 给定则输出长度 = round(duration*samplerate)（超出截断），
      否则 = max(region.end_ms)。无有效 region 返回 None。
    """
    valid = []
    for region in regions:
        if not region.audio_path:
            continue
        result = read_wav(region.audio_path)
        if result is not None:
            valid.append((region, result))
    if not valid:
        return None

    if duration is not None:
        total_frames = int(round(duration * samplerate))
    else:
        total_frames = max(
            int(round(region.end_ms * samplerate / 1000.0))
            for region in regions)

    target_channels = max(2, *(result.channels for _, result in valid))
    mixed = np.zeros((total_frames, target_channels), dtype=np.float32)

    for region, result in valid:
        data = np.asarray(result.data, dtype=np.float32)
        if data.ndim == 1:
            data = data.reshape(-1, result.channels)

        # 按源采样率切片 source_start_ms → source_end_ms
        start_frame = int(round(
            region.source_start_ms * result.samplerate / 1000.0))
        if region.source_end_ms is not None:
            end_frame = int(round(
                region.source_end_ms * result.samplerate / 1000.0))
            data = data[start_frame:end_frame]
        else:
            data = data[start_frame:]

        # 采样率不一致 → np.interp 线性插值重采样
        if result.samplerate != samplerate and data.shape[0] > 0:
            new_frames = max(1, int(round(
                data.shape[0] * samplerate / result.samplerate)))
            x_old = np.linspace(0.0, 1.0, data.shape[0])
            x_new = np.linspace(0.0, 1.0, new_frames)
            resampled = np.empty((new_frames, data.shape[1]),
                                 dtype=np.float32)
            for channel in range(data.shape[1]):
                resampled[:, channel] = np.interp(
                    x_new, x_old, data[:, channel])
            data = resampled

        if data.shape[0] == 0:
            continue

        # × volume
        if region.volume != 1.0:
            data = data * region.volume

        # 定位 start_ms → 逐样本相加（超出总长截断）
        pos_frame = int(round(region.start_ms * samplerate / 1000.0))
        end_pos = min(pos_frame + data.shape[0], total_frames)
        if end_pos <= pos_frame:
            continue
        if data.shape[1] == 1 and target_channels > 1:
            data = np.repeat(data, target_channels, axis=1)
        mixed[pos_frame:end_pos, :] += data[:end_pos - pos_frame, :]

    np.clip(mixed, -1.0, 1.0, out=mixed)
    return mixed
