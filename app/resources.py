"""Recordly 资源定位工具

统一处理三种运行模式的资源路径：
1. 源码开发模式：相对于项目根目录
2. PyInstaller 冻结模式：sys._MEIPASS
3. 系统包安装模式（Debian/AUR pip）：/usr/share/recordly 或 site-packages 同级
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def project_root() -> Path:
    """返回项目根目录（源码/PyInstaller/系统安装模式下都指向包含 resources 的目录）。"""
    # PyInstaller 冻结包：资源被解压到 _MEIPASS
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)

    # 系统包安装模式（Debian / AUR pip 安装）：资源随包放到 site-packages 同级
    # pyproject.toml 的 [tool.setuptools.package-data] resources = ["icons/*"]
    # 实际系统安装下 resources 包会被复制到 .../site-packages/resources/
    candidate = Path(__file__).resolve().parent.parent / "resources"
    if candidate.is_dir():
        return candidate.parent

    # 系统级 /usr/share/recordly（未来扩展点）
    share = Path("/usr/share/recordly")
    if share.is_dir():
        return share

    return candidate.parent  # 兜底：返回推测的根


def resource_path(*parts: str) -> Path:
    """拼接项目资源绝对路径。"""
    return project_root().joinpath("resources", *parts)


def load_text(*parts: str, encoding: str = "utf-8") -> str:
    """读取文本资源，缺失时返回空串（与原 _load_stylesheet 行为一致）。"""
    try:
        return resource_path(*parts).read_text(encoding=encoding)
    except (FileNotFoundError, PermissionError, OSError):
        return ""


def exists(*parts: str) -> bool:
    """判断资源是否存在。"""
    return resource_path(*parts).is_file()