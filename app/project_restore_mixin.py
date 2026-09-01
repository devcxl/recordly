"""项目打开/恢复流程 — MainWindow 拆分之一（issue #143 Step 1）

纯搬移自 app/main_window.py，方法签名与实现体不变。
共享 MainWindow 实例状态（_compositor/_timeline/_playback/_project_dir 等），
通过 Mixin 继承链访问 MainWindow 的 UI 方法（_show_notification 等）。
"""

import os

from core.project import Clip, Project, Track
from app.project_session import ProjectSession

def _read_wav(path: str):
    """从 WAV 文件读取音频（委托 core.audio_capture.read_wav，返回 AudioResult | None）"""
    from core.audio_capture import read_wav
    return read_wav(path)

def _resolve_media_path(project_dir: str, rel_path: str) -> str:
    """安全解析项目内媒体路径。
    相对/绝对路径均解析后检查是否位于 project_dir 内；外部绝对路径和 '..' 越界拒绝。
    """
    project_real = os.path.realpath(project_dir)
    candidate = rel_path if os.path.isabs(rel_path) else os.path.join(project_dir, rel_path)
    resolved = os.path.realpath(candidate)
    try:
        if os.path.commonpath([resolved, project_real]) != project_real:
            raise ValueError(f"路径越界: {rel_path}")
    except ValueError as exc:
        if "路径越界" in str(exc):
            raise
        raise ValueError(f"路径越界: {rel_path}") from exc
    return resolved

def ensure_builtin_audio_tracks(project, project_dir: str) -> None:
    """幂等补齐旧项目的内置音频轨（纯数据操作，供加载路径调用）。

    1) audio 轨 clip 无 source_path → 回退 _resolve_media_path(project_dir, source.audio_mic)
    2) source.audio_system 存在且无 audio_system 轨 → 追加全时长 clip
    已补齐项目再调用无变化。
    """
    for track in project.timeline:
        if track.type == "audio" and track.clips and not track.clips[0].source_path:
            if project.source and project.source.audio_mic:
                track.clips[0].source_path = _resolve_media_path(
                    project_dir, project.source.audio_mic)
    if project.source and project.source.audio_system:
        if not any(t.type == "audio_system" for t in project.timeline):
            sys_path = _resolve_media_path(project_dir, project.source.audio_system)
            project.timeline.append(Track(type="audio_system", name="系统音频", clips=[
                Clip(type="audio_system", start=0.0, end=project.duration,
                     source_start=0.0, source_path=sys_path, content="系统音频"),
            ]))

def _load_project_audio(project_dir: str, source) -> "AudioResult | None":
    """从 project.json source 声明的 WAV 路径恢复混合音频。无音频时返回 None。"""
    from core.audio_capture import mix_audio_results

    mic_audio = None
    sys_audio = None
    if source and source.audio_mic:
        mic_path = _resolve_media_path(project_dir, source.audio_mic)
        mic_audio = _read_wav(mic_path)
    if source and source.audio_system:
        sys_path = _resolve_media_path(project_dir, source.audio_system)
        sys_audio = _read_wav(sys_path)

    if mic_audio is None and sys_audio is None:
        return None
    return mix_audio_results(mic_audio, sys_audio)


class ProjectRestoreMixin:
    """项目打开/恢复/状态收集。"""

    def _collect_project_state(self, project: Project) -> None:
        """将当前 compositor 和编辑器状态写入 Project 对象"""
        comp = self._compositor
        # 光标轨迹（保存为相对 compositor._base_time 的时间戳）
        project.cursor_events = []
        base_ts = comp._base_time
        for c in comp._cursor_events:
            ts = c.timestamp - base_ts if hasattr(c, 'timestamp') else c[2] - base_ts
            if hasattr(c, 'x'):
                project.cursor_events.append([c.x, c.y, ts])
            else:
                project.cursor_events.append([c[0], c[1], ts])
        # 点击事件
        project.click_events = []
        for c in comp._click_events:
            if hasattr(c, 'x'):
                project.click_events.append([c.x, c.y, c.timestamp])
            else:
                project.click_events.append([c[0], c[1], c[2]])
        # 显示器偏移
        project.monitor_offset = [comp._monitor_left, comp._monitor_top]
        # 时间线轨道
        project.timeline = self._timeline.tracks
        # 裁剪区域
        project.crop_region = comp._crop_region
        # 音频区域
        project.audio_regions = self._audio_regions[:]

    def _on_open_project(self, path: str):
        project_dir = ProjectSession.normalize_path(path)
        self._clear_editor_state()

        try:
            project = self._project_manager.open_project(project_dir)
        except Exception as exc:
            self._show_notification("打开项目失败", str(exc), "error")
            return

        self._project_dir = project_dir
        comp = self._compositor

        try:
            self._restore_cursor_events(comp, project)
            self._restore_video_frames(comp, project, project_dir)
            mixed_audio = self._restore_project_audio(
                project_dir, project.source)
            self._build_recorded_data_from_project(comp, mixed_audio)
            self._restore_timeline_and_playback(comp, project)
            self._restore_editor_ui(comp, project)
        except Exception as exc:
            # 回退到干净状态，避免界面半初始化后残留脏数据
            self._clear_editor_state()
            self._project_dir = None
            self._show_notification(
                "打开项目失败", f"项目数据恢复失败: {exc}", "error")
            return

        self._switch_to_editor()
        self.update_status(f"● 已打开项目: {project.name}")

    def _clear_editor_state(self):
        self._recorded_data = None
        self._playback = None
        self._compositor.frames = []
        self._compositor.frame_times = []
        self._compositor.cursor_events = []
        self._compositor.click_events = []
        self._compositor.crop_region = None
        self._crop_active = False
        self._audio_regions = []
        self._track_audio_cache = {}

    def _restore_cursor_events(self, comp, project):
        EventData = type("EventData", (), {})
        comp._cursor_events = []
        for c in project.cursor_events:
            evt = EventData()
            evt.x, evt.y, evt.timestamp = int(c[0]), int(c[1]), float(c[2])
            comp._cursor_events.append(evt)
        comp._click_events = []
        for c in project.click_events:
            comp._click_events.append((int(c[0]), int(c[1]), float(c[2])))
        if project.monitor_offset:
            comp._monitor_left = project.monitor_offset[0]
            comp._monitor_top = project.monitor_offset[1]

    def _restore_video_frames(self, comp, project, project_dir: str):
        if not project.source or not project.source.video:
            return
        video_path = project.source.video
        try:
            video_path = _resolve_media_path(project_dir, video_path)
        except ValueError:
            self._show_notification(
                "视频路径不安全", f"拒绝越界视频路径: {video_path}", "error")
            return
        if not video_path:
            return
        try:
            if video_path.endswith(".frames.data") or project.source.video == "frames.data":
                num_frames = comp.load_frames_data(
                    video_path,
                    getattr(project, '_frame_count', 0),
                    project.source.fps,
                    project.source.duration or project.duration,
                )
            else:
                num_frames = comp.load_video(video_path, project.source.fps)
            if num_frames > 0:
                self._register_cursor_effect(comp)
        except Exception as exc:
            self._show_notification("视频解码失败", str(exc), "warning")

    def _register_cursor_effect(self, comp):
        from core.cursor_effects import CursorEffect
        self._cursor_effect = CursorEffect(
            cursor_size=self.config.cursor_size,
            cursor_theme=self.config.cursor_theme,
            cursor_style=self.config.cursor_style,
        )
        comp.register_effect("cursor", self._cursor_effect)
        if not self.config.trail_enabled:
            self._cursor_effect.enabled["trail"] = False

    def _restore_project_audio(self, project_dir: str, source):
        try:
            return _load_project_audio(project_dir, source)
        except Exception as exc:
            self._show_notification("音频加载失败", str(exc), "warning")
            return None

    def _build_recorded_data_from_project(self, comp, mixed_audio):
        has_content = bool(comp.frames) or mixed_audio is not None
        if has_content:
            self._recorded_data = {
                "audio": mixed_audio,
                "frames": comp.frames,
                "cursor_events": comp._cursor_events,
                "clicks": comp._click_events,
            }

    def _restore_timeline_and_playback(self, comp, project):
        ensure_builtin_audio_tracks(project, self._project_dir)
        self._timeline.set_tracks(project.timeline)
        self._timeline.duration = project.duration
        self._timeline.source_duration = getattr(
            comp, "source_duration", None)
        for track in project.timeline:
            if track.type == "video":
                comp.load_clips(track.clips, project.duration)
            elif track.type == "zoom":
                comp.load_manual_zoom_clips(track.clips)

        # regions 恢复 + 三轨 sync 必须先于播放器创建（播放器消费 regions）
        self._audio_regions = project.audio_regions[:]
        self._sync_audio_regions()

        if comp.frames:
            self._bind_thumbnail_provider()
            self._create_playback_controller()
            self._playback.seek(0)
            self._connect_timeline_signals()

        if self._audio_regions:
            self._update_audio_timeline()

    def _restore_editor_ui(self, comp, project):
        if project.crop_region:
            comp.set_crop(project.crop_region)
            self._crop_active = True
            self._btn_crop.setChecked(True)

        has_frames = len(comp.frames) > 0
        self._btn_export.setEnabled(has_frames)
        self._btn_crop.setEnabled(has_frames)
        self._btn_add_audio.setEnabled(has_frames)
        self._enable_playback_controls(has_frames)
        total = len(comp.frames)
        self._frame_label.setText(f"1 / {max(total, 1)}")
