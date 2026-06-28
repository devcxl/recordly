"""梯度图像生成工具"""

from PIL import Image


def create_gradient(w: int, h: int,
                    color1: tuple, color2: tuple,
                    direction: str = "vertical") -> Image.Image:
    """创建线性渐变图像"""
    img = Image.new("RGB", (w, h))
    if direction == "vertical":
        for y in range(h):
            ratio = y / h
            _draw_line(img, y, w, color1, color2, ratio)
    elif direction == "horizontal":
        for x in range(w):
            ratio = x / w
            _draw_col(img, x, h, color1, color2, ratio)
    elif direction == "diagonal":
        for y in range(h):
            for x in range(w):
                ratio = (x + y) / (w + h)
                r = int(color1[0] + (color2[0] - color1[0]) * ratio)
                g = int(color1[1] + (color2[1] - color1[1]) * ratio)
                b = int(color1[2] + (color2[2] - color1[2]) * ratio)
                img.putpixel((x, y), (r, g, b))
    return img


def _draw_line(img, y, w, c1, c2, ratio):
    r = int(c1[0] + (c2[0] - c1[0]) * ratio)
    g = int(c1[1] + (c2[1] - c1[1]) * ratio)
    b = int(c1[2] + (c2[2] - c1[2]) * ratio)
    for x in range(w):
        img.putpixel((x, y), (r, g, b))


def _draw_col(img, x, h, c1, c2, ratio):
    r = int(c1[0] + (c2[0] - c1[0]) * ratio)
    g = int(c1[1] + (c2[1] - c1[1]) * ratio)
    b = int(c1[2] + (c2[2] - c1[2]) * ratio)
    for y in range(h):
        img.putpixel((x, y), (r, g, b))
