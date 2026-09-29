# Feature Details

Recordly combines lightweight screen recording and streamlined timeline editing into a single desktop tool built for developers, educators, and product teams.

---

## Screen and Audio Capture

### Screen Capture Engine
- **Low CPU Overhead**: Powered by `mss` for high-throughput, low-latency display frame acquisition.
- **Configurable Frame Rates**: Select frame rates from 10 FPS up to 120 FPS (30 FPS default for balanced performance).
- **Tray-Minimized Recording**: The main interface automatically hides into the system tray when recording starts to prevent screen clutter.

### Dual Audio Channel Capture
- **Independent Microphone Track**: High-fidelity voice capture via `sounddevice` saved directly to uncompressed WAV.
- **System Audio Capture**: Audio output from desktop applications captured independently via FFmpeg.
- **Waveform & Track Control**: Both tracks display separate audio waveforms in the timeline with individual mute toggles and volume gain sliders (0% to 200%).
- **Voiceover Re-Recording**: If a narration mistake occurs, right-click the microphone clip and select "Re-record Audio" to record a replacement segment without re-capturing the video.

---

## Cursor Effects and Tracking

### High-Precision Pointer Sampling
- Global pointer tracking via `pynput` records exact cursor coordinates with millisecond timestamps.
- **Click Ripple Effects**: Generates animated ripple waves on mouse clicks to emphasize user actions.
- **Cursor Interpolation**: Motion smoothing algorithms eliminate cursor teleportation and jitter across high-refresh displays.
- **Customizable Appearance**: Configure cursor size (16 to 96 px), dark or light theme, and cursor styles (classic arrow, dot, spotlight).

---

## Timeline Editing

### Core Interactions
- **Precision Playhead**: Single click on the time ruler positions the playhead; double-clicking empty timeline space immediately begins playback from that point.
- **Timeline Zooming**: Zoom the timeline in and out centered on the cursor position with `Ctrl + Wheel`.
- **Magnetic Snapping**: Dragging audio or video clips snaps automatically to adjacent clip edges or the playhead with visual alignment indicators.
- **Multi-Selection**: `Ctrl + Click` selects multiple clips across tracks for collective movement, deletion, or speed adjustments.

### Clip Trimming and Splitting
- **Edge Trimming**: Hover near clip boundaries and drag to adjust in and out points (minimum 0.5s duration).
- **Playhead Splitting**: Press `X` or use the context menu to split a clip at the current playhead position.
- **Variable Playback Speed**: Apply speed adjustments (0.25x, 0.5x, 1.0x, 1.5x, 2.0x) to shorten repetitive waiting segments.
- **Comprehensive Undo/Redo**: All editing operations (moves, trims, splits, volume changes) integrate into a unified Command Stack with `Ctrl+Z` and `Ctrl+Shift+Z`.

---

## Smart Zoom Track

- **Dedicated Zoom Track**: Add zoom blocks directly to the timeline to define camera focus regions.
- **Interactive Focus Box**: Resize and move the focus bounding box over key screen areas (code blocks, buttons, menus).
- **Smooth Transitions**: Video smoothly pans and zooms into the designated area and seamlessly pans back when the segment concludes.

---

## Export and Hardware Acceleration

### Formats & Aspect Ratios
- **MP4 & Animated GIF**: Produce standard H.264 MP4 videos for presentations or animated GIFs for documentation and GitHub pull requests.
- **Resolution Presets**: Choose 4K (2160p), 2K (1440p), 1080p, 720p, or custom dimensions.
- **Social & Media Aspect Ratios**: Crop to 16:9, 9:16 (vertical mobile), 1:1, or 4:3 with center cropping or free-form canvas trimming.

### Performance
- **NVIDIA GPU Acceleration (NVENC)**: Hardware-accelerated video encoding on supported NVIDIA GPUs for fast rendering and minimal CPU strain.
- **Background Export Worker**: Export tasks run in dedicated worker threads with non-blocking UI and safe cancellation.

---

## Project Safety & Persistence

- **Project Storage Model**: Each recording creates an isolated project directory under `~/Recordly/projects/` containing raw frames, dual audio files, and a `project.json` manifest.
- **Atomic File Writing**: Configuration saves use atomic file replacement to safeguard against power loss or crashes.
- **Crash Recovery**: Automatically cleans abandoned temporary frame caches on startup; recovers interrupted recordings if frames were written before termination.
