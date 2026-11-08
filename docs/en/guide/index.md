# Getting Started Guide

> Complete walkthrough from installation to exporting your first demo video in approximately 15 minutes.

This guide is designed for first-time Recordly users, walking you through the complete "Record -> Edit -> Export" workflow and introducing essential keyboard shortcuts and editing operations.

---

## Installation

### Distribution Packages (Recommended)

| Platform | Installation Method |
|----------|---------------------|
| Arch Linux | Download `.pkg.tar.zst` from [GitHub Releases](https://github.com/devcxl/recordly/releases), then run `sudo pacman -U ./recordly-*.pkg.tar.zst` |
| Debian / Ubuntu | Download `recordly_*.deb`, then run `sudo dpkg -i recordly_*.deb` |
| Windows | Download `recordly.exe` and double-click to run directly |
| macOS | Download `recordly-macos.zip`, extract, and move `Recordly.app` into `/Applications` |

### Running from Source

Requires Python 3.10+ and FFmpeg installed on your system:

```bash
git clone https://github.com/devcxl/recordly
cd recordly
pip install -e .
recordly          # or python main.py
```

::: warning Missing FFmpeg?
If Recordly reports missing system dependencies upon startup, please install FFmpeg:
- macOS: `brew install ffmpeg`
- Linux: `sudo apt install ffmpeg`
- Windows: `choco install ffmpeg` or download from [ffmpeg.org](https://ffmpeg.org/download.html).
:::

---

## Home Gallery

When Recordly launches, you will see the **Home Gallery** showing saved projects in chronological order:

- **Start Recording**: Begins a new screen capture session.
- **Open Project**: Selects an existing `project.json` file from disk.
- **Project Cards**: Click to open in the editor; double-click the title to rename inline; right-click to delete.

---

## First Recording

1. Click **Start Recording** on the home screen and confirm the dialog.
2. The Recordly window automatically minimizes to the system tray, and recording starts after a brief buffer.
3. Recordly captures your **entire primary display**, while recording **microphone narration** and **system audio** concurrently.
4. When finished, right-click the system tray icon and select **Stop Recording**.
5. The project automatically saves and opens inside the editor.

::: tip System Tray Menu
Right-click the tray icon to access: **Start Recording**, **Stop Recording**, **Show Window**, and **Quit**.
:::

::: warning Closing Window Does Not Exit
Clicking the window close button hides Recordly to the system tray so that ongoing recordings are not interrupted. To terminate the application, select "Quit" from the tray menu.
:::

---

## Editor Interface

The editor contains four primary zones:

| Zone | Description |
|------|-------------|
| **Toolbar** | Undo / Redo, playback controls (Rewind / Prev Frame / Play Pause / Next Frame / Fast Forward), timecode display, Export, Crop Mode, and Add Audio |
| **Preview** | Live canvas showing current frame, zoom region bounding box, and cropping area |
| **Timeline** | Video track, audio tracks (Mic and System), zoom track, and additional audio tracks |
| **Status Bar** | System status and action feedback |

---

## Timeline Editing

### Basic Navigation
- **Playhead Movement**: Click or drag across the timeline ruler.
- **Quick Play**: Double-click empty timeline space to jump the playhead to that point and begin playing.
- **Moving Clips**: Drag clip bodies along or across audio tracks.
- **Trimming**: Hover over left or right clip boundaries until the resize cursor appears, then drag to trim.
- **Timeline Zoom**: Use `Ctrl + Wheel` to zoom the timeline centered on the mouse position.
- **Magnetic Snapping**: Dragged clips snap to adjacent clip boundaries or the playhead with visual dashed lines.

### Clip Context Menu & Actions
- `Ctrl + Click` to select or deselect multiple clips.
- Right-click any clip to access:
  - **Split**: Splits the clip at the current playhead position.
  - **Speed**: Adjusts speed to 0.25x, 0.5x, 1x, 1.5x, or 2x.
  - **Volume**: Mute, 50%, 100%, or 150%.
  - **Re-record Audio**: (Microphone track only) Re-records narration for the chosen section.
  - **Delete**: Removes the clip.

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Space` | Play / Pause |
| `X` | Split clip at playhead |
| `S` | Split selected clip |
| `Delete` / `Backspace` | Delete selected clip |
| `I` | Trim in-point (remove preceding segment) |
| `O` | Trim out-point (remove subsequent segment) |
| `Ctrl+Z` | Undo |
| `Ctrl+Shift+Z` / `Ctrl+Y` | Redo |

Shortcuts can be customized via **File -> Settings -> Shortcuts**.

---

## Advanced Audio

### Dual Tracks
Recordings contain two separate audio tracks: **Microphone** and **System Audio**. Both tracks are mixed synchronously during export.

### Voiceover Re-Recording
If you make a verbal slip during recording, right-click the microphone clip, choose **Re-record Audio**, and record a new take. The original clip will be muted and the new recording inserted at the exact same location.

### Adding Background Audio
Click **Add Audio** in the toolbar to import MP3, WAV, AAC, M4A, FLAC, or OGG tracks starting from the playhead location.

---

## Smart Zoom Track

Double-click the **Zoom Track** (orange) to add a 2-second zoom block:
- Drag the blue bounding box in the preview to select the focus area.
- Resize corners to change magnification (10% to 90% of screen).
- Video smoothly pans into the bounding box during playback and returns to full scale at block completion.

---

## Exporting Video

Click **Export** in the toolbar or menu to open the export dialog:
- **Format**: MP4 (H.264) or GIF.
- **Resolution**: Native, 4K, 2K, 1080p, 720p, or custom.
- **Aspect Ratio**: Native, 16:9, 9:16, 1:1, or 4:3.
- **Quality**: Native (100%), High (90%), Good (75%), Medium (60%).
- **GPU Hardware Encoding**: Enable NVIDIA NVENC acceleration if supported by hardware.

---

## Troubleshooting and FAQ

**Q: Where is the window after clicking Start Recording?**  
Recordly minimizes to your system tray. Right-click the tray icon to stop recording or restore the window.

**Q: Can I record only a portion of the screen?**  
The recorder currently captures the full primary display. You can crop the view in the editor using Crop Mode or during export using aspect ratio presets.

**Q: Can I record only mic or only system audio?**  
Both tracks record simultaneously by default. You can mute the unwanted track on the timeline prior to export.

**Q: Is GPU hardware acceleration available on my system?**  
If NVENC is grayed out in the export dialog, no compatible NVIDIA GPU or driver was detected. The default CPU encoder will be used instead.
