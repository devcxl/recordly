"""梯度图像生成工具（numpy 加速）"""

from PIL import Image
import numpy as np


def create_gradient(w: int, h: int,
                    color1: tuple, color2: tuple,
                    direction: str = "vertical") -> Image.Image:
    """创建线性渐变图像（numpy 向量化实现）"""
    c1 = np.array(color1, dtype=np.float64)
    c2 = np.array(color2, dtype=np.float64)

    if direction == "vertical":
        ratios = np.linspace(0, 1, h).reshape(h, 1, 1)                   # (h, 1, 1)
        pixels = (c1 + (c2 - c1) * ratios).astype(np.uint8)              # (h, 1, 3) → (h, w, 3)
        pixels = np.broadcast_to(pixels, (h, w, 3)).copy()
    elif direction == "horizontal":
        ratios = np.linspace(0, 1, w).reshape(1, w, 1)                  # (1, w, 1)
        pixels = (c1 + (c2 - c1) * ratios).astype(np.uint8)             # (1, w, 3) → (h, w, 3)
        pixels = np.broadcast_to(pixels, (h, w, 3)).copy()
    elif direction == "diagonal":
        yy, xx = np.meshgrid(np.linspace(0, 1, h), np.linspace(0, 1, w), indexing="ij")
        ratios = (xx + yy) / 2.0                                         # (h, w)
        pixels = (c1 + (c2 - c1) * ratios[..., np.newaxis]).astype(np.uint8)

    return Image.fromarray(pixels, "RGB")
