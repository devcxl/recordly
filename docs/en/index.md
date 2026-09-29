---
layout: home

hero:
  name: "Recordly"
  text: "Open-Source Screen Recorder & Video Editor"
  tagline: "Record, add cursor effects, mix dual audio tracks, edit on timeline, and export with NVENC acceleration."
  image:
    src: /logo.svg
    alt: Recordly Logo
  actions:
    - theme: brand
      text: Download (All Platforms)
      link: "#download"
    - theme: alt
      text: Getting Started Guide
      link: /en/guide/
    - theme: alt
      text: Features
      link: /en/features
    - theme: alt
      text: GitHub Source
      link: https://github.com/devcxl/recordly

features:
  - title: Screen Capture & Global Cursor Tracking
    details: Low-overhead screen capture powered by mss with real-time cursor tracking, click ripple effects, and smooth interpolation.
  - title: Independent Dual Audio Tracks & Mixing
    details: Capture microphone and system audio simultaneously on separate tracks. Adjust volume, mute clips, or re-record voiceovers directly on the timeline.
  - title: Demo-First Timeline Editing
    details: Multi-track timeline built for software tutorials. Features magnetic snapping, speed control (0.25x-2.0x), zoom track focusing, and precise trimming.
  - title: Hardware Acceleration & Multi-Format Export
    details: Supports NVIDIA NVENC GPU encoding for fast 4K/2K/1080p MP4 export, animated GIF output, and flexible aspect ratio cropping.
  - title: Project Persistence & Data Safety
    details: Standalone project folders with atomic project.json saves, automatic crash cleanup, and recovery for interrupted recordings.
  - title: Native Cross-Platform Distribution
    details: Packages available for Arch Linux (.pkg.tar.zst), Debian/Ubuntu (.deb), Windows (.exe), and macOS (.zip).
---

<DownloadCards lang="en" />

## Workflow Overview

<div class="workflow-grid">
  <div class="workflow-card">
    <div class="workflow-step">Step 01</div>
    <div class="workflow-title">Record</div>
    <div class="workflow-desc">
      Launch recording with one click. Recordly minimizes to the system tray while simultaneously capturing screen frames, mic narration, system audio, and cursor coordinates.
    </div>
  </div>
  <div class="workflow-card">
    <div class="workflow-step">Step 02</div>
    <div class="workflow-title">Edit</div>
    <div class="workflow-desc">
      The editor opens automatically after recording. Trim unnecessary pauses, split clips, adjust volume sliders, change playback speed, and add zoom-in focus boxes.
    </div>
  </div>
  <div class="workflow-card">
    <div class="workflow-step">Step 03</div>
    <div class="workflow-title">Export</div>
    <div class="workflow-desc">
      Choose your target aspect ratio (16:9, 9:16, 1:1, or 4:3), set resolution and bitrate, and export hardware-accelerated MP4 videos or high-fidelity animated GIFs.
    </div>
  </div>
</div>

## Feature Comparison

Recordly is designed for developers, educators, and creators who need a fast, self-contained desktop recording and editing workflow without subscription fees or heavy editing software:

<div class="comparison-table-wrapper">
  <table class="comparison-table">
    <thead>
      <tr>
        <th>Dimension</th>
        <th class="highlight-col">Recordly</th>
        <th>OBS Studio</th>
        <th>Screen Studio</th>
        <th>Kap</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>License & Pricing</td>
        <td class="highlight-col">Free & Open Source (MIT)</td>
        <td>Free & Open Source (GPL v2)</td>
        <td>Paid Commercial Proprietary</td>
        <td>Free & Open Source (MIT)</td>
      </tr>
      <tr>
        <td>Supported OS</td>
        <td class="highlight-col">Linux / Windows / macOS</td>
        <td>Linux / Windows / macOS</td>
        <td>macOS Only</td>
        <td>macOS Only</td>
      </tr>
      <tr>
        <td>Built-in Timeline Editor</td>
        <td class="highlight-col">Full Timeline (Trim / Snap / Speed)</td>
        <td>None (requires external NLE)</td>
        <td>Built-in Timeline</td>
        <td>Basic Trim Only</td>
      </tr>
      <tr>
        <td>Cursor Tracking & Effects</td>
        <td class="highlight-col">Native Tracking & Click Ripples</td>
        <td>Requires complex plugins</td>
        <td>Native Smooth Tracking</td>
        <td>Basic Highlight Only</td>
      </tr>
      <tr>
        <td>Dual Audio & Re-Recording</td>
        <td class="highlight-col">Dual Tracks + Voiceover Re-Record</td>
        <td>Mixer Only (No Re-Recording)</td>
        <td>Basic Dual Tracks</td>
        <td>Single Track Only</td>
      </tr>
      <tr>
        <td>Smart Zoom & Focus</td>
        <td class="highlight-col">Dedicated Zoom Track</td>
        <td>Manual Scene Filters</td>
        <td>Automatic Click Zoom</td>
        <td>None</td>
      </tr>
      <tr>
        <td>Project Persistence</td>
        <td class="highlight-col">Project Folders (project.json)</td>
        <td>Direct video save only</td>
        <td>Proprietary Project Format</td>
        <td>No Project Concept</td>
      </tr>
    </tbody>
  </table>
</div>

## Architecture

Recordly is engineered with strict separation of concerns to guarantee high recording reliability:

- **GUI Controller Layer (PyQt5)**: Main window, multi-track timeline, inspector panel, project gallery, and configuration dialogs.
- **Pure Python Core Engine**: Completely decoupled from Qt, managing screen capture, dual-track audio mixing, pointer tracking, and crash recovery.
- **Media Pipeline**: Fast image compositing via Pillow and NumPy, backed by an FFmpeg wrapper supporting NVENC GPU acceleration.
- **Quality & Reliability**: Thoroughly validated with automated test suites and tracked through immutable Architectural Decision Records (ADRs).
