# Recordly

> 开源桌面录屏与演示视频编辑工具 —— 录制、剪辑、导出，一气呵成

**简体中文** | [English](README.en.md)

Recordly 是一款基于 PyQt5 + FFmpeg 的桌面录屏与视频编辑工具，支持屏幕录制、鼠标光标特效、音频混合、时间线剪辑与 MP4/GIF 导出，并提供 Arch Linux / Debian / Windows / macOS 全平台分发产物。

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue" alt="Python">
  <img src="https://img.shields.io/badge/PyQt5-5.15%2B-green" alt="PyQt5">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License">
  <img src="https://img.shields.io/badge/tests-691%20passed-brightgreen" alt="Tests">
</p>

---

## 功能特性

### 录制

- 屏幕录制：基于 mss 的跨平台屏幕捕获，支持自定义帧率与录制区域
- 音频录制：麦克风（sounddevice）与系统音频（FFmpeg）双轨采集
- 鼠标轨迹：全局鼠标追踪，可选轨迹/波纹/摇摆/模糊等光标特效

### 编辑

- 时间线：拖拽、跨轨移动、拆分、多选批量操作、吸附、滚轮缩放
- 速度控制：0.25x - 2.0x 变速
- 音量调节：clip 内嵌连续音量滑块（0% - 200%）+ Inspector 属性面板，支持撤销/重做
- 音频混合：时间轴音频区域合成（compose_audio），预览与导出语义一致
- 标注：文本/箭头/图片/模糊
- 帧样式：背景色、圆角、阴影
- 智能缩放：自动追踪鼠标点击区域放大（zoom 轨道）
- 摄像头画中画：OpenCV 摄像头叠加，支持智能缩放

### 导出

- 格式：MP4（H.264，支持 NVENC GPU 加速）/ GIF
- 分辨率预设：4K / 2K / 1080p / 720p，支持自定义宽高比与 crop-to-fill 裁剪
- 音频：AAC 编码，双轨混合导出

### 项目

- 录制即建项目，独立目录保存帧数据、音频与工程文件（JSON）
- 首页卡片网格浏览，缩略图预览，原子化保存

---

## 安装

### 分发版（推荐）

| 平台 | 安装方式 |
|------|----------|
| Arch Linux | 下载 Release 中的 `.pkg.tar.zst` 后 `sudo pacman -U` |
| Debian / Ubuntu | 下载 Release 中的 `recordly_*.deb` 后 `sudo dpkg -i` |
| Windows | 下载 Release 中的 `recordly.exe` 直接运行 |
| macOS | 下载 Release 中的 `recordly-macos.zip`，解压后拖入 Applications |

所有平台产物可在 [GitHub Releases](https://github.com/devcxl/recordly/releases) 页面下载。

### 从源码运行

前置要求：Python 3.10+，并已安装 FFmpeg。

```bash
# 克隆
git clone https://github.com/devcxl/recordly
cd recordly

# 安装 Python 依赖（PEP 621，依赖声明于 pyproject.toml）
pip install -e .

# 安装 FFmpeg（系统依赖）
# macOS:   brew install ffmpeg
# Linux:   sudo apt install ffmpeg
# Windows: choco install ffmpeg

# 启动
recordly
# 或 python main.py
```

---

## 技术栈

| 组件 | 用途 |
|------|------|
| PyQt5 | GUI 框架 |
| mss | 跨平台屏幕捕获 |
| Pillow + NumPy | 图像合成与帧处理 |
| sounddevice | 麦克风音频捕获 |
| pynput | 全局鼠标追踪 |
| ffmpeg-python | 视频导出（FFmpeg 封装） |
| opencv-python-headless | 视频解码与摄像头画中画 |

---

## 项目结构

```
recordly/
├── main.py                 # 程序入口
├── pyproject.toml          # PEP 621 包配置（依赖 / 构建 / 入口）
├── app/                    # Qt 控制器层
│   ├── main_window.py      # 主窗口（QMainWindow）
│   ├── resources.py        # 统一资源加载（打包感知）
│   ├── config.py           # 应用配置（QSettings）
│   ├── recorder.py / export_controller.py / project_session.py
│   └── constants.py        # 常量
├── core/                   # 纯 Python 引擎层（无 Qt 依赖，可独立测试）
│   ├── recorder.py         # 录制控制器
│   ├── screen_capture.py   # 屏幕捕获（帧存储 / 崩溃残留清理）
│   ├── audio_capture.py    # 音频捕获
│   ├── audio_mix.py        # 音频合成（compose_audio）
│   ├── pointer_tracker.py  # 鼠标追踪
│   ├── cursor_effects.py   # 光标特效
│   ├── compositor.py       # 帧合成器
│   ├── camera.py           # 智能镜头系统
│   ├── effects.py          # 标注效果
│   ├── frame_style.py      # 帧样式
│   ├── exporter.py         # FFmpeg 导出引擎（CPU / NVENC / GIF）
│   ├── project.py          # 项目数据模型（加载时深度校验）
│   ├── project_manager.py  # 多项目管理器
│   ├── commands.py         # 撤销/重做命令
│   ├── aspect_ratio.py     # 宽高比 + 分辨率预设
│   └── speed.py            # 速度计算
├── ui/                     # Qt 组件层
│   ├── timeline.py         # 时间线（含 clip 内嵌音量滑块）
│   ├── inspector_panel.py  # 音量属性面板
│   ├── preview_widget.py   # 预览播放器
│   ├── export_dialog.py    # 导出对话框
│   ├── settings_dialog.py  # 设置对话框
│   ├── annotation_panel.py # 标注面板
│   ├── crop_overlay.py     # 裁剪叠加层
│   ├── project_card.py     # 项目卡片组件
│   └── project_gallery.py  # 项目画廊
├── tests/                  # 33 个测试文件，691 个用例
├── docs/                   # 文档（prd / adr / design / dev / review / task）
├── debian/                 # Debian 打包（dh-python + pybuild）
├── .aur/                   # AUR PKGBUILD
├── recordly.spec           # PyInstaller 配置（Linux / macOS）
└── recordly-windows.spec   # PyInstaller 配置（Windows）
```

---

## 测试

```bash
pip install pytest pytest-cov
python -m pytest tests/ -v
```

测试套件共 691 个用例，覆盖录制、合成、导出、命令层与 UI 交互；CI 在每次推送时自动运行，并包含 wheel 构建冒烟测试。

---

## 文档

- **[新用户使用指南](docs/guide/index.md)** —— 从安装、第一次录制到剪辑与导出的完整上手流程
- [项目概览](docs/00-overview/index.md)
- [产品需求文档（PRD）](docs/01-product/prd/index.md)
- [架构决策记录（ADR）](docs/03-architecture/adr/index.md)
- [技术方案与规格](docs/03-architecture/system-design/index.md)
- [在线文档站（GitHub Pages）](https://devcxl.github.io/recordly/)

---

## 许可证

本项目以 [MIT License](LICENSE) 发布。