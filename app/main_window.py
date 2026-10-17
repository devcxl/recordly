"""Recordly 主窗口 — 纯 PyQt5"""

import os
from pathlib import Path

from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.QtWidgets import QApplication, QFileDialog, QMainWindow, QMessageBox

from app.config import AppConfig
from app.constants import DEFAULT_SAMPLE_RATE
from core.compositor import Compositor
from core.shortcuts import ShortcutRegistry
from core.commands import ChangeVolumeCommand
from core.project import Clip, Track, CropRegion
from core.project_manager import ProjectManager
from ui.crop_overlay import CropOverlay
from app.project_session import ProjectSession
from app.project_restore_mixin import ProjectRestoreMixin
from app.audio_flow_mixin import AudioFlowMixin
from app.recording_flow_mixin import RecordingFlowMixin
from app.export_flow_mixin import ExportFlowMixin
from app.recording_controller import RecordingController, RecordingState
from app.export_controller import ExportController
from app.window_setup_mixin import WindowSetupMixin


class MainWindow(WindowSetupMixin, ExportFlowMixin, RecordingFlowMixin, AudioFlowMixin, ProjectRestoreMixin, QMainWindow):
    """主窗口，管理录制/预览/导出的生命周期"""

    recording_started = pyqtSignal()
    recording_stopped = pyqtSignal()

    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self._project_session: ProjectSession | None = None
        self._recording_controller = RecordingController(config)
        self._compositor = Compositor(1920, 1080, config.default_fps)
        self._recorded_data = None
        self._audio_regions = []
        self._track_audio_cache = {}
        self._export_controller = ExportController(self)
        self._progress = None
        self._playback = None
        self._editing_zoom_clip = None
        self._crop_overlay = None
        self._crop_active = False
        os.makedirs(config.projects_dir, exist_ok=True)
        self._project_manager = ProjectManager(config.projects_dir)
        self._shortcut_registry = ShortcutRegistry(config.shortcuts)

        self._setup_window()
        self._setup_interfaces()
        self._setup_navigation()
        self._setup_tray()
        self._check_deps()
        self._update_ui_state()

        self.recording_started.connect(self._on_recording_started)
        self.recording_stopped.connect(self._on_recording_stopped)
        self._export_controller.export_progress.connect(
            self._on_export_progress)
        self._export_controller.export_finished.connect(self._on_export_finished)

    @property
    def _project_dir(self) -> str | None:
        return self._project_session.project_dir if self._project_session else None

    @_project_dir.setter
    def _project_dir(self, value: str | None):
        self._project_session = ProjectSession(value) if value else None

    @property
    def _is_recording(self) -> bool:
        return self._recording_controller.state == RecordingState.RECORDING

    @_is_recording.setter
    def _is_recording(self, value: bool):
        pass  # no-op, state managed by controller

    # ── 窗口 ──────────────────────────────────────────────

    def _on_open_settings(self):
        from ui.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self.config, self)
        if dialog.exec_() == SettingsDialog.Accepted:
            if self._shortcut_registry.replace_bindings(self.config.shortcuts).ok:
                self.config.shortcuts = self._shortcut_registry.bindings()
                self._timeline.set_shortcut_registry(self._shortcut_registry)
                self._rebind_window_shortcuts()
                self._refresh_undo_redo_state()
            self._compositor.fps = self.config.default_fps
            if self._is_recording:
                self._show_notification(
                    "设置未完全应用",
                    "录制过程中无法修改帧率，将在下次录制时生效",
                    "warning",
                )
            else:
                self._recording_controller.recorder.set_target_fps(self.config.default_fps)
            self._apply_cursor_config()
            self._compositor.set_preview_quality(self.config.preview_quality)

    def _apply_cursor_config(self):
        if not hasattr(self, '_cursor_effect'):
            return
        self._cursor_effect.cursor_size = self.config.cursor_size
        self._cursor_effect.cursor_theme = self.config.cursor_theme
        self._cursor_effect.cursor_style = self.config.cursor_style
        self._cursor_effect.enabled["trail"] = self.config.trail_enabled
        playback = getattr(self, "_playback", None)
        if playback:
            playback.seek(playback.current_frame)

    # ── 首页交互 ──────────────────────────────────────────

    def _on_home_open_project(self):
        """首页点击'打开项目' → 文件选择器"""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择项目文件", self.config.projects_dir,
            "Recordly 项目 (project.json)",
        )
        if path:
            self._on_open_project(ProjectSession.normalize_path(path))

    # ── 录制 ──────────────────────────────────────────────

    def _toggle_record(self):
        if self._is_recording:
            self._is_recording = False
            self.recording_stopped.emit()
        else:
            self._is_recording = True
            self.recording_started.emit()
        self._update_ui_state()





    def _connect_timeline_signals(self):
        """重复录制时保持时间线信号单次连接。"""
        pairs = (
            (self._timeline.playhead_changed, self._on_timeline_seek),
            (self._timeline.playhead_drag_started,
             self._on_playhead_drag_started),
            (self._timeline.playhead_drag_finished,
             self._on_playhead_drag_finished),
            (self._timeline.zoom_double_clicked, self._on_zoom_double_clicked),
            (self._timeline.zoom_add_requested, self._on_zoom_double_clicked),
            (self._timeline.zoom_clip_selected, self._on_zoom_clip_selected),
            (self._timeline.clips_changed, self._on_clips_changed),
            (self._timeline.clips_changed, self._refresh_undo_redo_state),
            (self._timeline.status_message, self.update_status),
            (self._timeline.playhead_seek_play, self._on_playhead_seek_play),
            (self._timeline.re_record_requested, self._on_re_record_requested),
            (self._timeline.selection_changed, self._on_timeline_selection_changed),
            (self._timeline.clip_volume_changed, self._on_clip_volume_changing),
            (self._inspector.volume_changing, self._on_inspector_volume_changing),
            (self._inspector.volume_committed, self._on_inspector_volume_committed),
        )
        for signal, slot in pairs:
            try:
                signal.disconnect(slot)
            except TypeError:
                pass
            signal.connect(slot)

    def _populate_timeline(self):
        """录制结束后在时间线中创建视频、音频、缩放轨道"""
        self._track_audio_cache = {}
        frames = self._compositor.frames
        if not frames:
            return
        duration = self._get_recording_duration()
        tracks = []
        tracks.append(Track(type="video", name="视频", clips=[
            Clip(type="video", start=0, end=duration,
                 content=f"屏幕录制 {self._compositor.width}x{self._compositor.height}"),
        ]))

        project_dir = self._project_dir or ""
        mic_wav = os.path.join(project_dir, "audio_mic.wav") if project_dir else ""
        sys_wav = os.path.join(project_dir, "audio_system.wav") if project_dir else ""

        tracks.append(Track(type="audio", name="麦克风", clips=[
            Clip(type="audio", start=0, end=duration,
                 source_path=mic_wav if os.path.exists(mic_wav) else "",
                 content="麦克风"),
        ]))
        tracks.append(Track(type="audio_system", name="系统音频", clips=[
            Clip(type="audio_system", start=0, end=duration,
                 source_path=sys_wav if os.path.exists(sys_wav) else "",
                 content="系统音频"),
        ]))

        clicks = self._recorded_data.get("clicks", [])
        cursor_events = self._recorded_data.get("cursor_events", [])
        base_time = frames[0].timestamp
        from core.camera import build_camera
        camera = build_camera(clicks, self._compositor.fps,
                              self._compositor.width,
                              self._compositor.height, duration,
                              cursor_events, base_time,
                              self._compositor.monitor_left,
                              self._compositor.monitor_top)
        self._compositor.load_camera(camera)

        zoom_clips = camera.build_zoom_clips() if camera else []
        tracks.append(Track(type="zoom", name="缩放", clips=zoom_clips))

        self._timeline.set_tracks(tracks)
        self._timeline.source_duration = self._compositor.source_duration
        self._timeline.duration = duration
        self._compositor.load_clips(tracks[0].clips, duration)
        self._compositor.load_manual_zoom_clips(zoom_clips)
        if self._audio_regions:
            self._update_audio_timeline()


    def _update_ui_state(self):
        rec = self._is_recording
        self._btn_export.setEnabled(not rec)
        self._tray_record_act.setEnabled(not rec)
        self._tray_stop_act.setEnabled(rec)
        self.update_status("● 录制中..." if rec else "● 准备就绪")

    def set_recording_state(self, recording: bool):
        self._is_recording = recording
        self._update_ui_state()

    def update_status(self, text: str):
        self._status_label.setText(text)

    def _on_play_toggle(self):
        if not self._compositor.frames:
            return
        if not self._playback:
            self._create_playback_controller()
            start_frame = int(self._timeline.playhead * self._compositor.fps)
            self._playback.play(start_frame)
            self._btn_play.setText("⏸")
            self._btn_play.setToolTip("暂停")
        elif not self._playback._playing:
            self._playback.play(self._playback.current_frame)
            self._btn_play.setText("⏸")
            self._btn_play.setToolTip("暂停")
        elif self._playback.is_paused:
            self._playback.pause()
            self._btn_play.setText("⏸")
            self._btn_play.setToolTip("暂停")
        else:
            self._playback.pause()
            self._btn_play.setText("▶")
            self._btn_play.setToolTip("继续播放")

    def _on_playhead_seek_play(self, sec: float):
        """双击时间线空白区域：跳转播放头并开始播放。"""
        # 边界检查：无帧时静默忽略
        if not self._compositor.frames:
            return

        # 焦点守卫（与窗口级快捷键一致）
        if not self._is_editor_active_and_safe():
            return

        # 设置播放头位置（TimelineWidget 已在信号发射前更新 _playhead_s）
        self._timeline.playhead = sec

        # 延迟播放启动，确保信号处理完成后再操作播放器
        QTimer.singleShot(0, lambda: self._start_playback_at(sec))

    def _start_playback_at(self, sec: float):
        """在指定秒数开始播放。"""
        # 确保播放器存在
        if not self._playback:
            self._create_playback_controller()
        elif not self._playback.is_paused:
            # 如果正在播放，先停止
            self._playback.pause()

        start_frame = int(sec * self._compositor.fps)
        self._playback.play(start_frame)
        self._btn_play.setText("⏸")
        self._btn_play.setToolTip("暂停")



    def _create_playback_controller(self):
        from ui.audio_preview_player import AudioPreviewPlayer
        from ui.playback_controller import PlaybackController

        audio_result = (
            self._recorded_data.get("audio") if self._recorded_data else None
        )
        if hasattr(self._timeline, "set_waveform_provider"):
            self._timeline.set_waveform_provider(self._track_audio_provider)
        samplerate = int(getattr(
            audio_result, "samplerate", DEFAULT_SAMPLE_RATE))
        # 预览音频以视频时长为界截断（与导出语义一致）：
        # 超长 region（如超出视频的 BGM）不驱动慢放，避免音频时钟拖长播放
        total_frames = getattr(self._compositor, "total_output_frames", 0) or 0
        video_duration = (
            total_frames / max(self._compositor.fps, 1)
            if total_frames else None
        )
        self._playback = PlaybackController(
            self._preview,
            self._compositor,
            audio_player=AudioPreviewPlayer(
                self._audio_regions, samplerate, duration=video_duration),
        )
        self._preview.set_fps(int(self._compositor.fps))
        self._playback.set_on_frame_changed(self._update_frame_counter)

    def _bind_thumbnail_provider(self):
        """将 compositor 帧解码绑定为时间线缩略图提供者。"""
        comp = self._compositor
        frames = getattr(comp, "frames", []) or []

        def provider(source_time_s):
            if not frames:
                return None
            try:
                if comp.clips is not None:
                    idx = comp._source_index_at(source_time_s)
                else:
                    idx = comp._nearest_source_index(source_time_s)
                if idx is None or not (0 <= idx < len(frames)):
                    return None
                frame = frames[idx]
                data = frame.data if hasattr(frame, "data") else None
                if data is None:
                    return None
                import numpy as np
                from PyQt5.QtGui import QImage, QPixmap
                rgb = np.ascontiguousarray(data[:, :, ::-1])
                h, w, _ = rgb.shape
                qimage = QImage(rgb.data, w, h, 3 * w,
                                QImage.Format_RGB888)
                return QPixmap.fromImage(qimage)
            except Exception:
                return None

        if hasattr(self._timeline, "set_thumbnail_provider"):
            self._timeline.set_thumbnail_provider(provider)

    def _on_rewind(self):
        if self._playback:
            self._playback.rewind()
            self._update_frame_counter(self._playback.current_frame)

    def _on_step_back(self):
        if self._playback:
            self._playback.step_backward()
            self._update_frame_counter(self._playback.current_frame)

    def _on_step_fwd(self):
        if self._playback:
            self._playback.step_forward()
            self._update_frame_counter(self._playback.current_frame)

    def _on_fast_forward(self):
        if not self._playback:
            return
        self._playback.fast_forward()
        if not self._playback.is_paused:
            self._btn_play.setText("⏸")

    def _update_frame_counter(self, idx: int):
        total = self._playback.total_frames
        self._frame_label.setText(f"{idx + 1} / {total}")
        # 同步时间线播放头
        sec = idx / self._compositor.fps
        self._timeline.playhead = sec
        self._time_label.setText(
            f"{MainWindow._format_time(sec)} / "
            f"{MainWindow._format_time(self._timeline.duration)}"
        )
        self._timeline_scroll.ensureVisible(
            self._timeline._time_to_x(sec), 0, 120, 0
        )

    @staticmethod
    def _format_time(seconds: float) -> str:
        milliseconds = max(0, round(seconds * 1000))
        minutes, remainder = divmod(milliseconds, 60_000)
        whole_seconds, milliseconds = divmod(remainder, 1000)
        return f"{minutes:02d}:{whole_seconds:02d}.{milliseconds:03d}"

    def _on_timeline_seek(self, sec: float):
        if not self._playback:
            return
        if self._timeline._drag_state == "playhead":
            # 拖拽中仅更新计数器，避免逐像素全帧合成；release 时统一定位
            self._update_frame_counter(int(sec * self._compositor.fps))
            return
        idx = int(sec * self._compositor.fps)
        self._playback.seek(idx)
        self._update_frame_counter(idx)

    def _on_playhead_drag_started(self):
        if self._playback:
            self._playback.pause()

    def _on_playhead_drag_finished(self, sec: float):
        if not self._playback:
            return
        idx = int(sec * self._compositor.fps)
        self._playback.seek(idx)
        self._update_frame_counter(idx)

    def _on_zoom_double_clicked(self, time_s: float, existing_clip=None):
        ratio = self.config.zoom_rect_ratio
        w = int(self._compositor.width * ratio)
        h = int(self._compositor.height * ratio)
        rect = [
            (self._compositor.width - w) // 2,
            (self._compositor.height - h) // 2,
            w,
            h,
        ]
        clip = existing_clip
        if clip is None:
            zoom_track_index = next((
                index for index, track in enumerate(self._timeline.tracks)
                if track.type == "zoom"
            ), None)
            if zoom_track_index is None:
                return
            requested_clip = Clip(
                type="zoom", start=time_s,
                end=min(time_s + 2.0, self._timeline.duration),
                content="手动缩放",
                rect=rect,
                transition_duration=0.4,
            )
            clip = self._timeline.add_clip(zoom_track_index, requested_clip)
        elif not clip.rect:
            clip.rect = rect

        self._editing_zoom_clip = clip
        self._compositor.load_manual_zoom_clips(
            [c for t in self._timeline.tracks if t.type == "zoom"
             for c in t.clips if c.rect])
        if self._playback:
            self._playback.seek(self._playback.current_frame)
        self._preview.show_zoom_rect(clip.rect,
                                     self._compositor.width, self._compositor.height)
        try:
            self._preview.overlay.rect_changed.disconnect()
        except TypeError:
            pass
        self._preview.overlay.rect_changed.connect(self._on_zoom_rect_changed)
        self._timeline.update()

    def _on_zoom_clip_selected(self, clip):
        self._on_zoom_double_clicked(clip.start, clip)

    def _on_zoom_rect_changed(self, x, y, w, h):
        """预览框被拖拽后，更新当前 zoom clip 的 rect"""
        zoom_clips = [
            c for track in self._timeline.tracks if track.type == "zoom"
            for c in track.clips
        ]
        if self._editing_zoom_clip not in zoom_clips:
            self._editing_zoom_clip = None
            self._preview.hide_zoom_rect()
            return
        self._editing_zoom_clip.rect = [x, y, w, h]
        self._compositor.load_manual_zoom_clips(
            [c for t in self._timeline.tracks if t.type == "zoom"
             for c in t.clips if c.rect])
        if self._playback:
            self._playback.seek(self._playback.current_frame)

    def _on_clips_changed(self):
        """时间线 clip 变化后（拖拽/删除/拆分/撤销）同步 zoom clips 到 compositor"""
        self._compositor.load_manual_zoom_clips(
            [c for t in self._timeline.tracks if t.type == "zoom"
             for c in t.clips if c.rect])
        video_clips = [c for t in self._timeline.tracks if t.type == "video"
                       for c in t.clips]
        all_clip_ends = [
            clip.end
            for track in self._timeline.tracks
            for clip in track.clips
        ]
        self._timeline.duration = max(all_clip_ends, default=0.1)
        self._compositor.load_clips(video_clips, self._timeline.duration)
        # 先同步 audio_regions，再重建播放器（播放器消费 regions，顺序不能反）
        self._sync_audio_regions()
        if self._playback:
            current_frame = self._playback.current_frame
            self._playback.stop()
            self._create_playback_controller()
            self._playback.seek(current_frame)
        zoom_clips = [
            c for t in self._timeline.tracks if t.type == "zoom"
            for c in t.clips
        ]
        if self._editing_zoom_clip not in zoom_clips:
            self._editing_zoom_clip = None
            self._preview.hide_zoom_rect()


    def _on_timeline_selection_changed(self):
        """选中变化：同步 Inspector 显示。"""
        info = self._timeline.get_selected_audio_clip()
        if info is None:
            self._inspector.clear()
            return
        ti, ci, clip = info
        self._inspector.show_clip(ti, ci, clip)

    def _on_clip_volume_changing(self, ti: int, ci: int, new_volume: float):
        """timeline mini slider 拖动中：同步 Inspector 数值。
        mouseReleaseEvent 已 emit clips_changed → 重建 playback，此处无需重绘。
        """
        self._inspector.update_volume_display(ti, ci, new_volume)

    def _on_inspector_volume_changing(self, ti: int, ci: int, new_volume: float):
        """Inspector slider/mute/preset 拖动中：改 clip.volume + 重绘 timeline。"""
        if ti < 0 or ti >= len(self._timeline.tracks) \
                or ci < 0 or ci >= len(self._timeline.tracks[ti].clips):
            return
        clip = self._timeline.tracks[ti].clips[ci]
        clip.volume = max(0.0, min(new_volume, 2.0))
        self._timeline.update()

    def _on_inspector_volume_committed(self, ti: int, ci: int,
                                       old_volume: float, new_volume: float):
        """Inspector 拖动结束：入撤销栈（clip.volume 已由 changing 改过）。
        push_command 会 emit clips_changed → _on_clips_changed 重建 playback。
        """
        if abs(old_volume - new_volume) < 0.001:
            return
        cmd = ChangeVolumeCommand(ti, ci, old_volume, new_volume)
        self._timeline.push_command(cmd)

    def _enable_playback_controls(self, enabled: bool):
        self._btn_rewind.setEnabled(enabled)
        self._btn_step_back.setEnabled(enabled)
        self._btn_play.setEnabled(enabled)
        self._btn_step_fwd.setEnabled(enabled)
        self._btn_ff.setEnabled(enabled)

    # ── 裁剪 ──────────────────────────────────────────────

    def _on_crop_toggled(self, active: bool):
        """裁剪模式开关"""
        if not self._compositor.frames:
            self._btn_crop.setChecked(False)
            return

        if active:
            if not self._crop_overlay:
                self._crop_overlay = CropOverlay(self._preview._label)
                self._preview.add_overlay(self._crop_overlay)
                self._crop_overlay.crop_changed.connect(self._on_crop_changed)
            self._crop_overlay.set_crop(0.0, 0.0, 1.0, 1.0)
            self._crop_active = True
        else:
            if self._crop_overlay:
                self._crop_overlay.clear_crop()
            self._compositor.set_crop(None)
            self._crop_active = False

    def _on_crop_changed(self, x, y, w, h):
        """裁剪区域变更时更新合成器"""
        if w >= 1.0 and h >= 1.0:
            self._compositor.set_crop(None)
        else:
            self._compositor.set_crop(CropRegion(x=x, y=y, width=w, height=h))
        # 刷新当前帧
        if self._playback:
            self._playback.seek(self._playback.current_frame)

    # ── 项目 ──────────────────────────────────────────────

    def _on_project_deleted(self, path: str):
        """删除项目目录并刷新画廊"""
        try:
            self._project_manager.delete_project(path)
            self._refresh_home_page()
        except Exception as exc:
            self._show_notification("删除项目失败", str(exc), "error")

    def _on_project_renamed(self, path: str, new_name: str):
        """重命名项目并刷新画廊"""
        try:
            self._project_manager.rename_project(path, new_name)
            self._refresh_home_page()
        except Exception as exc:
            self._show_notification("重命名项目失败", str(exc), "error")

    def _on_save_project(self):
        """保存当前项目编辑状态"""
        if not self._project_dir:
            QMessageBox.warning(self, "保存失败", "当前没有打开的项目。\n请先录制一个新项目，或从首页打开已有项目。")
            return
        try:
            project = self._project_manager.open_project(self._project_dir)
            self._collect_project_state(project)
            project.save(str(Path(self._project_dir) / "project.json"))
            self.update_status("✓ 项目已保存")
            self._show_notification("保存成功", f"已保存到: {self._project_dir}", "success")
        except Exception as exc:
            self._show_notification("保存项目失败", str(exc), "error")

    def _on_about(self):
        QMessageBox.about(
            self, "关于 Recordly",
            f"Recordly v{QApplication.applicationVersion()}\n\n"
            "开源演示视频录制与编辑工具\n\n"
            "作者：devcxl\n"
            "GitHub：https://github.com/devcxl/recordly")

    def _on_undo(self):
        if hasattr(self, '_timeline'):
            self._timeline.undo()
            self._on_timeline_selection_changed()  # undo 音量后同步 Inspector

    def _on_redo(self):
        if hasattr(self, '_timeline'):
            self._timeline.redo()
            self._on_timeline_selection_changed()
