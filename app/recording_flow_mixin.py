"""录制流程 — MainWindow 拆分之三（issue #143 Step 3）

纯搬移自 app/main_window.py（录制开始/停止/项目初始化/持久化/清理）。
共享 MainWindow 实例状态，通过 Mixin 继承链访问。
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QMessageBox

from core.cursor_effects import CursorEffect
from core.project import Project, SourceInfo
from app.project_restore_mixin import _write_wav


class RecordingFlowMixin:
    """录制流程控制器。"""

    def _on_home_record(self):
        """首页点击'开始录制' → 确认弹窗 → 创建项目目录 → 最小化 → 开始录制"""
        reply = QMessageBox.question(
            self, "开始录制",
            "将开始屏幕录制。录制时窗口会最小化到系统托盘，"
            "你可以通过托盘图标停止录制。\n\n确定开始？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
        )
        if reply != QMessageBox.Yes:
            return

        # 立即创建项目目录和占位 project.json
        name = f"录制 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        project_dir = str(Path(self.config.projects_dir) / f"{timestamp}_{name}")
        os.makedirs(project_dir, exist_ok=True)

        project = Project()
        project.name = name
        project.save(str(Path(project_dir) / "project.json"))
        self._project_dir = project_dir

        self._project_name = name
        self.showMinimized()
        QTimer.singleShot(500, self._start_recording_from_home)

    def _start_recording_from_home(self):
        """从首页触发的录制（帧数据流式写入项目目录）"""
        try:
            self._recording_controller.start(self._project_dir)
        except Exception as exc:
            self._is_recording = False
            self.set_recording_state(False)
            self.update_status("● 录制启动失败")
            self._show_notification("无法开始录制", str(exc), "error")
            self._cleanup_failed_recording()
            return
        self._update_ui_state()

    def _create_project_for_recording(self):
        """托盘录制时自动创建项目目录"""
        name = f"录制 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        project_dir = str(Path(self.config.projects_dir) / f"{timestamp}_{name}")
        os.makedirs(project_dir, exist_ok=True)
        self._project_name = name
        project = Project()
        project.name = name
        project.save(str(Path(project_dir) / "project.json"))
        self._project_dir = project_dir
        self.showMinimized()

    def _cleanup_failed_recording(self):
        """录制启动失败：删除占位项目，恢复窗口"""
        if self._project_dir:
            try:
                shutil.rmtree(self._project_dir, ignore_errors=True)
            except Exception:
                pass
        self._project_dir = None
        self.showNormal()
        self.raise_()

    def _handle_stop_failure(self):
        """录制停止失败：恢复窗口，处理失败项目"""
        self.showNormal()
        self.raise_()
        project_dir = self._project_dir
        if not project_dir:
            return
        frames_file = Path(project_dir) / "frames.data"
        if frames_file.exists() and frames_file.stat().st_size > 0:
            self.update_status("⚠ 录制异常结束，项目已保留")
        else:
            try:
                shutil.rmtree(project_dir, ignore_errors=True)
            except Exception:
                pass
            self._project_dir = None

    def _on_recording_started(self):
        # 托盘录制：自动创建项目目录
        if not self._project_dir:
            self._create_project_for_recording()
        try:
            self._recording_controller.start(self._project_dir)
        except Exception as exc:
            self.set_recording_state(False)
            self.update_status("● 录制启动失败")
            self._show_notification("无法开始录制", str(exc), "error")
            self._cleanup_failed_recording()
            return
        self.update_status("● 录制中...")

    def _on_recording_stopped(self):
        try:
            self._recorded_data = self._recording_controller.stop()
        except Exception as exc:
            self._recorded_data = None
            self.set_recording_state(False)
            self.update_status("● 录制失败")
            self._show_notification("录制失败", str(exc), "error")
            self._handle_stop_failure()
            return
        if self._recorded_data and self._recorded_data.get("frames"):
            self._compositor.load_frames(self._recorded_data["frames"])
            self._compositor.load_cursor_events(
                self._recorded_data.get("cursor_events", []),
                self._recorded_data.get("clicks", []),
            )
            offset = self._recorded_data.get("monitor_offset", (0, 0))
            self._compositor.set_monitor_offset(offset[0], offset[1])
            from core.cursor_effects import CursorEffect
            self._cursor_effect = CursorEffect(
                cursor_size=self.config.cursor_size,
                cursor_theme=self.config.cursor_theme,
                cursor_style=self.config.cursor_style,
            )
            self._compositor.register_effect("cursor", self._cursor_effect)
            if not self.config.trail_enabled:
                self._cursor_effect.enabled["trail"] = False
            self._btn_export.setEnabled(True)
            self._btn_crop.setEnabled(True)
            self._btn_add_audio.setEnabled(True)
            self._enable_playback_controls(True)
            total = len(self._compositor.frames)
            self._frame_label.setText(f"1 / {total}")
            # 先写 wav（populate 时 source_path 可判定）再建轨，随后同步 regions
            # （保证预览播放器拿到有效音频 → 音频时钟驱动，速度与时长正确）
            self._persist_audio_wavs()
            self._populate_timeline()
            self._sync_audio_regions()
            self._bind_thumbnail_provider()
            self._create_playback_controller()
            self._playback.seek(0)
            self._connect_timeline_signals()
        self.update_status("● 录制完成")
        self._finalize_project()
        # 立即切换到编辑器
        self._switch_to_editor()
        self.showNormal()
        self.raise_()

    def _persist_audio_wavs(self) -> tuple[str, str]:
        """将内存 mic/system 录音写盘，返回 (mic_path, system_path) 相对路径。
        录制后须在 _populate_timeline 之前调用，保证轨道 source_path 可判定。"""
        mic_path = ""
        system_path = ""
        if not self._recorded_data or not self._project_dir:
            return mic_path, system_path
        project_dir = Path(self._project_dir)
        mic_audio = self._recorded_data.get("mic_audio")
        if mic_audio is not None and len(mic_audio.data) > 0:
            mic_path = "audio_mic.wav"
            _write_wav(str(project_dir / mic_path), mic_audio.data,
                       mic_audio.samplerate)
        sys_audio = self._recorded_data.get("system_audio")
        if sys_audio is not None and len(sys_audio.data) > 0:
            system_path = "audio_system.wav"
            _write_wav(str(project_dir / system_path), sys_audio.data,
                       sys_audio.samplerate)
        return mic_path, system_path

    def _finalize_project(self):
        """录制完成后直接保存 project.json（帧数据已在 frames.data 中）"""
        if not self._recorded_data or not self._recorded_data.get("frames"):
            return
        if not self._project_dir:
            return

        try:
            frames = self._recorded_data["frames"]
            project_dir = Path(self._project_dir)
            project = Project()
            project.name = getattr(self, '_project_name',
                                   f"录制 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            project.duration = self._get_recording_duration()
            project.thumbnail_path = ""

            mic_path = ""
            system_path = ""
            mic_path, system_path = self._persist_audio_wavs()

            project.source = SourceInfo(
                video="frames.data",
                audio_mic=mic_path,
                audio_system=system_path,
                duration=project.duration,
                fps=self.config.default_fps,
                width=self._compositor.width,
                height=self._compositor.height,
            )
            project._frame_count = len(frames)
            # 保存帧偏移索引（供重新打开时定位每帧）
            import json
            offsets = self._recording_controller.recorder.screen.frame_offsets
            idx_path = str(Path(self._project_dir) / "frames.idx")
            with open(idx_path, "w") as f:
                json.dump([[o, l] for o, l in offsets], f)
            self._collect_project_state(project)
            project.save(str(Path(self._project_dir) / "project.json"))
            self._refresh_home_page()
            self.update_status("✓ 项目已保存")
        except Exception as exc:
            self._show_notification("保存项目失败", str(exc), "error")

    def _get_recording_duration(self) -> float:
        duration = getattr(self._compositor, "source_duration", 0.0)
        if duration > 0:
            return duration
        return len(self._compositor.frames) / self._compositor.fps

    # ── 状态更新 ──────────────────────────────────────────
