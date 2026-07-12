"""宽高比计算工具"""

from dataclasses import dataclass
from typing import Literal

# 宽高比预设值列表（与 core.project 同步）
ASPECT_RATIO_PRESETS: list[str] = [
    "native", "16:9", "9:16", "1:1", "4:3", "4:5", "16:10", "10:16",
]
"""字符串类型: 预设值之一或 "W:H" 自定义"""
AspectRatio = str

# 分辨率预设：显示名 → 最大高度像素（None = 不限制）
RESOLUTION_PRESETS: dict[str, int | None] = {
    "原始（不限制）": None,
    "2160p (4K)": 2160,
    "1440p (2K)": 1440,
    "1080p (Full HD)": 1080,
    "720p (HD)": 720,
    "480p (SD)": 480,
    "360p": 360,
}


@dataclass
class ExportDimensions:
    width: int
    height: int


def parse_aspect_ratio(ratio: AspectRatio) -> float | None:
    """解析宽高比字符串为浮点数。native 返回 None"""
    if ratio == "native":
        return None
    parts = ratio.split(":")
    if len(parts) == 2:
        try:
            return int(parts[0]) / int(parts[1])
        except ZeroDivisionError:
            return None
    return None


def normalize_even(n: int) -> int:
    """归一化到偶数（H.264 编码要求）"""
    return n if n % 2 == 0 else n - 1


def calculate_export_dimensions(
    source_width: int, source_height: int,
    aspect_ratio: AspectRatio,
    crop_width: float = 1.0, crop_height: float = 1.0,
    quality: float = 1.0,
    max_height: int | None = None,
) -> ExportDimensions:
    """
    根据宽高比、裁剪和质量计算导出尺寸。

    - native: 使用裁剪后的源尺寸
    - 预设 (如 "16:9", "4:3"): 在裁剪区域内 fit 到指定比例
    - 自定义 "W:H": 同上
    - max_height: 最大高度上限（仅缩小，不放大），None = 不限制
    - 所有结果归一化到偶数
    """
    cw = int(source_width * crop_width)
    ch = int(source_height * crop_height)

    if cw < 1 or ch < 1:
        w = normalize_even(int(source_width * quality))
        h = normalize_even(int(source_height * quality))
        return ExportDimensions(width=max(2, w), height=max(2, h))

    ratio_val = parse_aspect_ratio(aspect_ratio)
    if ratio_val is None:  # native
        w, h = cw, ch
    else:
        current = cw / ch
        if current > ratio_val:
            # 更宽 → 限制高度
            h = ch
            w = int(h * ratio_val)
        else:
            # 更高 → 限制宽度
            w = cw
            h = int(w / ratio_val)

    # 分辨率上限（仅缩小，不放大）
    if max_height is not None and h > max_height:
        scale = max_height / h
        w = int(w * scale)
        h = max_height

    w = normalize_even(int(w * quality))
    h = normalize_even(int(h * quality))
    return ExportDimensions(width=max(2, w), height=max(2, h))
