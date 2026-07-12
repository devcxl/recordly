# Recordly

> 🎬 开源桌面录屏与演示视频编辑工具 — 录制、剪辑、导出，一气呵成

Recordly 是一款基于 PyQt5 + FFmpeg 的桌面录屏与视频编辑工具，支持屏幕录制、鼠标光标特效、音频混合、时间线剪辑与 MP4/GIF 导出。

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11%2B-blue" alt="Python">
  <img src="https://img.shields.io/badge/PyQt5-5.15%2B-green" alt="PyQt5">
  <img src="https://img.shields.io/badge/license-AGPL--3.0-orange" alt="License">
  <img src="https://img.shields.io/badge/tests-288%20passed-brightgreen" alt="Tests">
</p>

---

## 功能

| 模块 | 说明 |
|------|------|
| 🎬 屏幕录制 | 基于 mss 跨平台屏幕捕获，自定义帧率/区域 |
| 🎤 音频录制 | 麦克风 (sounddevice) + 系统音频 (FFmpeg) |
| 🖱️ 鼠标特效 | 6 种光标样式 + 轨迹/波纹/摇摆/模糊效果 |
| ✂️ 时间线编辑 | 拖拽、拆分、速度控制、撤销/重做 |
| 📹 摄像头画中画 | opencv 摄像头叠加，智能缩放 |
| 📝 文字标注 | 文本/箭头/图片/模糊标注 |
| 🖼️ 帧样式 | 背景色、圆角、阴影 |
| 🔍 智能缩放 | 自动追踪鼠标点击区域放大 |
| ⏏ 导出 | MP4 / GIF，分辨率预设（4K/2K/1080p/720p），自定义宽高比 |
| 📁 项目管理 | 录制即创建项目，卡片网格浏览，缩略图预览 |

## 快速开始

```bash
# 克隆
git clone https://github.com/devcxl/recordly
cd recordly

# 安装 Python 依赖
pip install -r requirements.txt

# 安装 FFmpeg（系统依赖）
# macOS:  brew install ffmpeg
# Linux:  sudo apt install ffmpeg
# Windows: choco install ffmpeg

# 启动
python main.py
```

## 技术栈

| 组件 | 用途 |
|------|------|
| **PyQt5** | GUI 框架 |
| **mss** | 跨平台屏幕截图 |
| **Pillow + numpy** | 图像合成与帧处理 |
| **sounddevice** | 麦克风音频捕获 |
| **pynput** | 全局鼠标追踪 |
| **ffmpeg-python** | 视频导出 |
| **opencv-python-headless** | 摄像头画中画 |

## 项目结构

```
recordly/
├── main.py                 # 入口 + 全局暗色主题
├── app/
│   ├── main_window.py      # 主窗口（QMainWindow）
│   ├── config.py           # 应用配置（QSettings）
│   └── constants.py        # 常量
├── core/
│   ├── recorder.py         # 录制控制器
│   ├── screen_capture.py   # 屏幕捕获引擎
│   ├── audio_capture.py    # 音频捕获
│   ├── pointer_tracker.py  # 鼠标追踪
│   ├── cursor_effects.py   # 光标特效
│   ├── compositor.py       # 帧合成器
│   ├── camera.py           # 智能镜头系统
│   ├── effects.py          # 标注效果
│   ├── frame_style.py      # 帧样式
│   ├── exporter.py         # FFmpeg 导出引擎
│   ├── project.py          # 项目数据模型
│   ├── project_manager.py  # 多项目管理器
│   ├── commands.py         # 撤销/重做命令
│   ├── aspect_ratio.py     # 宽高比 + 分辨率预设
│   └── speed.py            # 速度计算
├── ui/
│   ├── timeline.py         # 时间线组件
│   ├── preview_widget.py   # 预览播放器
│   ├── export_dialog.py    # 导出对话框
│   ├── settings_dialog.py  # 设置对话框
│   ├── annotation_panel.py # 标注面板
│   ├── crop_overlay.py     # 裁剪叠加层
│   ├── project_card.py     # 项目卡片组件
│   └── project_gallery.py  # 项目画廊（卡片网格）
├── tests/                  # 18 个测试文件，288 个用例
├── docs/                   # 文档
│   ├── prd/                # 产品需求文档
│   ├── adr/                # 架构决策记录
│   └── dev/                # 技术方案 + 任务定义
└── resources/
    └── icons/
```

## 测试

```bash
pip install pytest pytest-cov
python -m pytest tests/ -v
```

## 文档

- [PRD: 项目管理功能](docs/prd/project-management.md)
- [技术方案: 项目管理](docs/dev/specs/project-management.md)
- [ADR: 目录扫描存储方案](docs/adr/2026-07-13-project-management.md)

## 协议

AGPL-3.0