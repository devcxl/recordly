#!/usr/bin/env python3
"""导出速度 profiling 脚本 — 对真实项目做分段耗时采样
用法: .venv/bin/python tools/profile_export.py [project_dir]
若不指定 project_dir，默认使用 20260716_064342 项目。
"""

import json, time, os, sys, random, numpy as np
from pathlib import Path
from unittest.mock import MagicMock
sys.modules.setdefault('pynput', MagicMock())
sys.modules['pynput.mouse'] = MagicMock()
sys.modules['pynput.mouse'].Listener = MagicMock()

from PyQt5.QtWidgets import QApplication
from core.compositor import Compositor
from core.exporter import ExportWorker, ExportSettings
from core.cursor_effects import CursorEffect


def load_project(proj_dir: str):
    project = json.loads(open(Path(proj_dir) / 'project.json').read())
    source = project['source']
    comp = Compositor(source['width'], source['height'], source['fps'])

    EventData = type("EventData", (), {})
    for c in project['cursor_events']:
        evt = EventData()
        evt.x, evt.y, evt.timestamp = int(c[0]), int(c[1]), float(c[2])
        comp._cursor_events.append(evt)
    for c in project['click_events']:
        comp._click_events.append((int(c[0]), int(c[1]), float(c[2])))

    comp.load_frames_data(str(Path(proj_dir) / 'frames.data'),
                          project.get('frame_count', 0),
                          source['fps'], source['duration'])

    cursor_effect = CursorEffect(cursor_size=90, cursor_theme='dark', cursor_style='ring')
    comp.register_effect("cursor", cursor_effect)

    from types import SimpleNamespace
    for track in project['timeline']:
        track_obj = SimpleNamespace(type=track['type'], clips=[])
        for clip_dict in track['clips']:
            track_obj.clips.append(SimpleNamespace(**clip_dict))
        if track['type'] == 'video':
            comp.load_clips(track_obj.clips)
        elif track['type'] == 'zoom':
            comp.load_manual_zoom_clips(track_obj.clips)
    return comp


def profile_stages(comp, num_samples=50, target_w=1920, target_h=1080):
    timings = {
        'jpeg_decode_ms': [],
        'compose_ms': [],
        'resize_ms': [],
        'convert_ms': [],
        'tobytes_ms': [],
    }
    total = comp.total_output_frames
    indices = sorted(random.sample(range(min(num_samples * 3, total)), min(num_samples, total)))

    for out_idx in indices:
        ts = out_idx / comp.fps
        source_idx = comp._source_index_at(ts)
        if source_idx is None:
            continue
        raw_frame = comp._frames[source_idx]

        t0 = time.perf_counter()
        img_data = raw_frame.data
        timings['jpeg_decode_ms'].append((time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        img = comp.compose(raw_frame, ts)
        timings['compose_ms'].append((time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        if img.size != (target_w, target_h):
            img = img.resize((target_w, target_h))
        timings['resize_ms'].append((time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        if img.mode != 'RGB':
            img = img.convert('RGB')
        timings['convert_ms'].append((time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        img.tobytes()
        timings['tobytes_ms'].append((time.perf_counter() - t0) * 1000)

    print(f'{"stage":20s}  {"avg":>6s}  {"min":>6s}  {"max":>6s}  {"n":>4s}')
    print('-' * 45)
    for key, vals in timings.items():
        if vals:
            print(f'{key:20s}  {np.mean(vals):6.1f}  {np.min(vals):6.1f}  {np.max(vals):6.1f}  {len(vals):4d}')
    return timings


def run_export(comp, label, use_gpu, fps, target_w=1920, target_h=1080):
    out = f'/tmp/recordly_profile_{label}.mp4'
    worker = ExportWorker(comp, None,
        ExportSettings(output_path=out, fps=fps, width=target_w, height=target_h,
                       use_gpu=use_gpu))
    t0 = time.perf_counter()
    worker.run()
    elapsed = time.perf_counter() - t0
    size = os.path.getsize(out) / 1024 / 1024 if os.path.exists(out) else 0
    actual_fps = comp.total_output_frames_for(fps) / elapsed
    print(f'{label:15s}  {elapsed:.1f}s  ({actual_fps:.0f}fps)  {size:.1f}MB')
    os.remove(out)
    return elapsed


if __name__ == '__main__':
    app = QApplication.instance() or QApplication([])
    proj_dir = sys.argv[1] if len(sys.argv) > 1 else (
        '/home/devcxl/Recordly/projects/20260716_064342_录制 2026-07-16 06:43')

    comp = load_project(proj_dir)
    print(f'frames={len(comp.frames)} total_output={comp.total_output_frames} '
          f'src_dur={comp.source_duration:.1f}s fps={comp.fps}\n')

    print('=== 分段 profiling ===')
    timings = profile_stages(comp, num_samples=50)

    decode = np.mean(timings['jpeg_decode_ms']) if timings['jpeg_decode_ms'] else 0
    comp_t = np.mean(timings['compose_ms']) if timings['compose_ms'] else 0
    resize = np.mean(timings['resize_ms']) if timings['resize_ms'] else 0
    convert = np.mean(timings['convert_ms']) if timings['convert_ms'] else 0
    tobytes = np.mean(timings['tobytes_ms']) if timings['tobytes_ms'] else 0
    per_frame = decode + comp_t + resize + convert + tobytes
    print(f'\nper_frame_total={per_frame:.0f}ms  serial_est={comp.total_output_frames*per_frame/1000:.0f}s\n')

    print('=== 全量导出 ===')
    for label, use_gpu, fps in [
        ('CPU 30fps', False, 30), ('GPU 30fps', True, 30),
        ('CPU 60fps', False, 60), ('GPU 60fps', True, 60),
    ]:
        comp2 = load_project(proj_dir)
        run_export(comp2, label, use_gpu, fps)
    app.processEvents()
