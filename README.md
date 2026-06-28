# Recordly

> 开源演示视频录制与编辑工具 — PyQt5 + FFmpeg

Recordly 是一款桌面录屏与演示视频编辑工具，支持屏幕录制、鼠标光标特效、音频混合、视频剪辑与导出。

---

## 技术栈

**Python 依赖：**
- **PyQt5** — GUI 框架
- **mss** — 跨平台屏幕截图
- **Pillow** + **numpy** — 图像合成与帧处理
- **sounddevice** — 麦克风音频捕获
- **pynput** — 全局鼠标追踪
- **ffmpeg-python** — 视频导出（MP4/GIF）
- **opencv-python-headless** — 摄像头画中画

**系统依赖：** FFmpeg、PortAudio（可选摄像头）

## 快速开始

```bash
# 1. 克隆
git clone https://github.com/devcxl/recordly
cd recordly

# 2. 安装 Python 依赖
pip install -r requirements.txt

# 3. 安装 FFmpeg
# macOS:  brew install ffmpeg
# Linux:  sudo apt install ffmpeg
# Windows: choco install ffmpeg

# 4. 启动
python main.py
```

## 功能

| 模块 | 状态 |
|------|------|
| 🎬 屏幕录制 (mss) | ✅ |
| 🎤 麦克风录制 (sounddevice) | ✅ |
| 🔊 系统音频录制 (FFmpeg) | ✅ |
| 🖱️ 鼠标追踪与特效 | ✅ |
| 🎨 实时预览 + 合成管线 | ✅ |
| ✂️ 时间线编辑器 | ✅ |
| 📹 摄像头画中画 | ✅ |
| 📝 文字标注 | ✅ |
| 🖼️ 视频背景样式 | ✅ |
| ⏏ MP4/GIF 导出 | ✅ |

## 架构

详见 `docs/` 目录

## 协议

AGPL-3.0
