# Feature Details

Recordly is built specifically for software demonstrations, video tutorials, and product walkthroughs. It integrates high-fidelity screen capture with lightweight, demo-focused timeline editing to help you produce presentation-grade videos and animated GIFs in minutes.

---

## High-Performance Screen Capture

### Lightweight Footprint & High Fluidity
- **Full-Screen & High-DPI Optimization**: Smoothly captures your entire desktop with minimal CPU consumption, whether on 4K multi-monitor workstations or compact laptops.
- **Customizable Frame Rates**: Select anywhere between 10 and 120 FPS. The default 30 FPS offers the ideal balance of fluidity and file size for tutorials.
- **Silent System Tray Operation**: Recordly automatically minimizes into your system tray when recording starts, keeping your working canvas completely unobstructed.

---

## Cursor Beautification and Trajectory Smoothing

### Make Every Click Clear to Viewers
- **Click Wave Ripples**: Every click produces an expanding highlight ripple, ensuring viewers clearly see every button press and menu selection.
- **Motion Smoothing**: Motion smoothing algorithms eliminate erratic mouse jitter and teleportation, lending your video a fluid, cinematic feel.
- **Customizable Appearance**: Configure cursor dimensions (16 to 96 px), dark or light theme, and toggle between classic arrows, highlighted dots, or spotlights in Settings.

---

## Dual Audio Channels & In-Place Voiceover Retakes

### Fix Verbal Mistakes Without Re-Recording Your Screen
- **Independent Mic & System Audio**: Microphone speech and computer system sound effects record into separate audio tracks simultaneously without cross-talk.
- **Waveform Inspection & Volume Sliders**: Inspect real-time audio waveforms directly on the timeline, adjust gain from 0% to 200% with continuous sliders, or mute individual tracks with one click.
- **Revolutionary Voiceover Retakes**: Made a verbal slip-up or had background noise during an otherwise perfect take? Right-click the microphone clip, select "Re-record Audio", speak the corrected sentence, and replace it in-place. The original take is muted automatically.
- **Background Music Support**: Click "Add Audio" in the toolbar to import MP3, WAV, AAC, or FLAC music tracks directly under your narration.

---

## Demo-First Multi-Track Timeline

### Zero Complex Video Editor Learning Curve
- **Instant Edge Trimming**: Hover near the start or end of any video or audio clip, wait for the resize cursor, and drag to trim off pauses or false starts.
- **Playhead Splitting**: Press `X` or right-click to slice clips instantly at the playhead position.
- **Magnetic Snapping**: Clips snap automatically to adjacent boundaries or the playhead with visual alignment indicators, preventing accidental blank frames.
- **Speed Control (0.25x - 2.0x)**: Fast-forward through long package installations or compile steps at 1.5x or 2.0x speed.
- **Multi-Selection & Unlimited Undo**: `Ctrl + Click` to select multiple clips for collective movement, and undo or redo any change with `Ctrl+Z` and `Ctrl+Shift+Z`.

---

## Cinematic Camera Pan & Zoom

### Highlight Code Details Seamlessly
- **Dedicated Zoom Track**: Double-click on the Zoom track to drop in a camera zoom block.
- **Interactive Focus Framing**: Drag the blue bounding box in the preview canvas over the exact area you want viewers to focus on (a code snippet, button, or menu).
- **Smooth Transition Dynamics**: The video smoothly glides and scales into the target area, then seamlessly glides back out when the block ends.

---

## Multi-Platform Formats & Fast GPU Export

### Ready to Share from Social Media to GitHub READMEs
- **Aspect Ratio Presets**: Switch with one click between 16:9 (YouTube, desktop), 9:16 (mobile reels, shorts), 1:1, or 4:3, with automatic crop-to-fill or freehand cropping.
- **Ultra-HD 4K & MP4 Export**: Export standard H.264 MP4 videos across 4K, 2K, 1080p, and 720p resolutions.
- **Compact Animated GIFs**: Export lightweight, smooth GIFs designed specifically for GitHub README headers, release notes, and documentation.
- **GPU Hardware Acceleration (NVENC)**: Offload rendering to NVIDIA GPUs for rapid export speeds and reduced system heat.

---

## Project Safety & 100% Offline Privacy

- **Automatic Project Storage**: Every recording creates a dedicated project folder locally under `~/Recordly/projects/` containing raw frames, dual audio files, and a project manifest.
- **Atomic Saves & Power-Loss Protection**: Project manifests are written atomically to prevent file corruption during unexpected power outages.
- **Crash Recovery**: Recordly automatically scans for abandoned frame caches on launch. If a recording was cut off unexpectedly, you can reopen and recover your footage directly from the home gallery.
- **Zero Cloud Uploads**: Works entirely offline with zero telemetry or account requirements. Your recordings remain strictly on your own machine.
