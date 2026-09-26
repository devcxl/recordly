# Recordly

> Open-source desktop screen recorder and demo video editor — record, edit, and export in one flow.

[简体中文](README.md) | **English** | [Documentation](https://devcxl.github.io/recordly/)

Recordly is a PyQt5 + FFmpeg based desktop screen recorder and video editor. It supports screen capture, cursor effects, audio mixing, timeline editing, and MP4/GIF export, with prebuilt packages for Arch Linux, Debian/Ubuntu, Windows, and macOS.

<p align="center">
  <a href="https://devcxl.github.io/recordly/"><img src="https://img.shields.io/badge/docs-devcxl.github.io%2Frecordly-blue" alt="Documentation"></a>
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue" alt="Python">
  <img src="https://img.shields.io/badge/PyQt5-5.15%2B-green" alt="PyQt5">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License">
  <img src="https://img.shields.io/badge/tests-696%20passed-brightgreen" alt="Tests">
</p>

---

## Features

### Recording

- Screen capture via mss with configurable frame rate and capture region
- Dual-track audio: microphone (sounddevice) plus system audio (FFmpeg)
- Global mouse tracking with optional trail / ripple / sway / blur cursor effects

### Editing

- Timeline: drag, cross-track move, split, multi-select batch operations, snapping, wheel zoom
- Speed control from 0.25x to 2.0x
- Volume: inline continuous volume slider on each clip (0% - 200%) plus an Inspector panel, both with Undo/Redo support
- Audio mixing: timeline audio regions composed in memory (compose_audio), identical semantics for preview and export
- Annotations: text / arrow / image / blur
- Frame styling: background color, rounded corners, shadow
- Smart zoom: automatically tracks the area around mouse clicks (zoom track)
- Camera picture-in-picture via OpenCV with smart scaling

### Export

- Formats: MP4 (H.264, optional NVENC GPU acceleration) / GIF
- Resolution presets: 4K / 2K / 1080p / 720p, custom aspect ratios, and crop-to-fill
- Audio: AAC encoding with mixed dual-track audio

### Project management

- Every recording becomes a project directory holding frame data, audio, and a JSON project file
- Home page card grid with thumbnail previews, atomic project saves

---

## Installation

### Prebuilt packages (recommended)

| Platform | Install |
|----------|---------|
| Arch Linux | Download the `.pkg.tar.zst` from Releases and run `sudo pacman -U` |
| Debian / Ubuntu | Download `recordly_*.deb` from Releases and run `sudo dpkg -i` |
| Windows | Download `recordly.exe` from Releases and run it directly |
| macOS | Download `recordly-macos.zip` from Releases, unzip, and drag into Applications |

All assets are available on the [GitHub Releases](https://github.com/devcxl/recordly/releases) page.

### Building from source

Requirements: Python 3.10+ and a working FFmpeg installation.

```bash
# Clone
git clone https://github.com/devcxl/recordly
cd recordly

# Install Python dependencies (PEP 621, declared in pyproject.toml)
pip install -e .

# Install FFmpeg (system dependency)
# macOS:   brew install ffmpeg
# Linux:   sudo apt install ffmpeg
# Windows: choco install ffmpeg

# Run
recordly
# or python main.py
```

---

## Tech stack

| Component | Purpose |
|-----------|---------|
| PyQt5 | GUI framework |
| mss | Cross-platform screen capture |
| Pillow + NumPy | Image composition and frame processing |
| sounddevice | Microphone audio capture |
| pynput | Global mouse tracking |
| ffmpeg-python | Video export (FFmpeg binding) |
| opencv-python-headless | Video decoding and camera picture-in-picture |

---

## Project layout

```
recordly/
├── main.py                 # Entry point
├── pyproject.toml          # PEP 621 packaging (deps / build / entry)
├── app/                    # Qt controller layer
│   ├── main_window.py      # Main window (QMainWindow)
│   ├── resources.py        # Unified resource loading (packaging-aware)
│   ├── config.py           # App config (QSettings)
│   ├── recorder.py / export_controller.py / project_session.py
│   └── constants.py        # Constants
├── core/                   # Pure-Python engine layer (Qt-free, unit-testable)
│   ├── recorder.py         # Recording controller
│   ├── screen_capture.py   # Screen capture (frame store / stale temp cleanup)
│   ├── audio_capture.py    # Audio capture
│   ├── audio_mix.py        # Audio composition (compose_audio)
│   ├── pointer_tracker.py  # Mouse tracking
│   ├── cursor_effects.py   # Cursor effects
│   ├── compositor.py       # Frame compositor
│   ├── camera.py           # Smart camera system
│   ├── effects.py          # Annotation effects
│   ├── frame_style.py      # Frame styling
│   ├── exporter.py         # FFmpeg export engine (CPU / NVENC / GIF)
│   ├── project.py          # Project model (deep validation on load)
│   ├── project_manager.py  # Project manager
│   ├── commands.py         # Undo/Redo commands
│   ├── aspect_ratio.py     # Aspect ratio + resolution presets
│   └── speed.py            # Speed math
├── ui/                     # Qt widget layer
│   ├── timeline.py         # Timeline (with inline volume slider)
│   ├── inspector_panel.py  # Volume inspector panel
│   ├── preview_widget.py   # Preview player
│   ├── export_dialog.py    # Export dialog
│   ├── settings_dialog.py  # Settings dialog
│   ├── annotation_panel.py # Annotation panel
│   ├── crop_overlay.py     # Crop overlay
│   ├── project_card.py     # Project card widget
│   └── project_gallery.py  # Project gallery
├── tests/                  # 33 test files, 691 test cases
├── docs/                   # Docs (prd / adr / design / dev / review / task)
├── debian/                 # Debian packaging (dh-python + pybuild)
├── .aur/                   # AUR PKGBUILD
├── recordly.spec           # PyInstaller spec (Linux / macOS)
└── recordly-windows.spec   # PyInstaller spec (Windows)
```

---

## Tests

```bash
pip install pytest pytest-cov
python -m pytest tests/ -v
```

The suite contains 691 test cases covering recording, composition, export, the command layer, and UI interactions. CI runs it on every push, including a wheel build smoke test.

---

## Docs

- **[Docs site (GitHub Pages)](https://devcxl.github.io/recordly/)** — full user guides, PRDs, ADRs, and system design docs
- **[User guide (中文)](docs/guide/index.md)** — a complete getting-started walkthrough: install, first recording, editing, and export
- [Project overview](docs/00-overview/index.md)
- [Product requirements (PRD)](docs/01-product/prd/index.md)
- [Architecture decision records (ADR)](docs/03-architecture/adr/index.md)
- [Technical specs](docs/03-architecture/system-design/index.md)

---

## License

Distributed under the [MIT License](LICENSE).