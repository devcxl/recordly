"""导出配置与结果模型。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.project import CropRegion


@dataclass
class ExportSettings:
    output_path: str
    format: str = "mp4"            # "mp4" / "gif"
    fps: int = 30
    bitrate: str = "10M"
    width: int = 0                 # 0 = 自动计算；>0 = 自定义精确宽度
    height: int = 0                # 0 = 自动计算；>0 = 自定义精确高度
    max_height: int | None = None  # 分辨率上限（仅缩小不放大），None = 不限制
    samplerate: int = 44100
    aspect_ratio: str = "native"
    quality: float = 1.0
    loop: bool = True              # GIF 是否循环
    preset: str = "veryfast"       # x264 preset: ultrafast/superfast/veryfast/faster/fast/medium/slow/slower/veryslow
    use_gpu: bool = False          # 使用 GPU (NVENC CUDA) 硬件编码
    audio_regions: list | None = None  # list[AudioRegion]，全部音频区域（含内置轨）
    crop_region: 'CropRegion | None' = None
    fill_crop_ratio: str | None = None  # crop-to-fill 目标比例（如 "16:9"），与 crop_region 互斥，物化时优先


@dataclass
class ExportResult:
    success: bool
    path: str
    duration: float = 0.0
    size_bytes: int = 0
    error: str | None = None

