"""Recordly 主窗口 — Fluent Design 重构"""

from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
    QFileDialog, QApplication, QListWidget, QMessageBox,
    QLabel, QProgressDialog,
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from PyQt5.QtGui import QPixmap, QPainter, QColor, QKeySequence, QIcon

from qfluentwidgets import (
    FluentWindow, FluentIcon, NavigationItemPosition,
    PrimaryPushButton, PushButton, ToolButton,
    InfoBar, InfoBarPosition,
    Action, CaptionLabel,
)
from qfluentwidgets import FluentIcon as FI

from app.config import AppConfig
from core.recorder import Recorder
from core.compositor import Compositor
from core.exporter import ExportWorker, ExportSettings
from core.project import Clip, Track
from ui.preview_widget import PreviewWidget
from ui.timeline import TimelineWidget


class MainWindow(FluentWindow):
    """主窗口，管理录制/预览/导出的生命周期"""

    recording_started = pyqtSignal()
    recording_stopped = pyqtSignal()
    export_requested = pyqtSignal(str)

    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self._is_recording = False
        self._recorder = Recorder()
        self._compositor = Compositor(1920, 1080, config.default_fps)
        self._recorded_data = None
        self._export_thread = None
        self._export_worker = None
        self._playback = None
        self._setup_window()
        self._setup_interfaces()
        self._setup_navigation()
        self._setup_tray()
        self._check_deps()
        self._update_ui_state()

        # 信号连接
        self.recording_started.connect(self._on_recording_started)
        self.recording_stopped.connect(self._on_recording_stopped)

    # ── 窗口 ──────────────────────────────────────────────

    def _setup_window(self):
        self.setWindowTitle("Recordly v1.0")
        self.resize(1280, 800)
        screen = QApplication.primaryScreen().geometry()
        self.move(
            (screen.width() - self.width()) // 2,
            (screen.height() - self.height()) // 2,
        )
        self.setStyleSheet("""
            #editorToolbar {
                background: #1e1e1e;
                border-bottom: 1px solid #323232;
            }
            #editorStatusBar {
                background: #1e1e1e;
                border-top: 1px solid #323232;
            }
        """)

    def closeEvent(self, event):
        """点击关闭 → 隐藏到托盘，不退出"""
        event.ignore()
        self.hide()
        self._tray.showMessage(
            "Recordly", "应用已最小化到系统托盘",
            self._tray.icon(), 2000,
        )

    DEPENDENCIES: list[dict] = [
        {"name": "FFmpeg", "cmd": "ffmpeg", "hint": "请安装 FFmpeg: https://ffmpeg.org/download.html"},
    ]

    def _check_deps(self):
        import shutil
        missing = [d for d in self.DEPENDENCIES if not shutil.which(d["cmd"])]
        if not missing:
            return
        msgs = "\n".join(f"  • {d['name']}: {d['hint']}" for d in missing)
        QMessageBox.warning(self, "缺少系统依赖",
                            f"以下依赖未安装，部分功能不可用:\n\n{msgs}")

    # ── 界面 ──────────────────────────────────────────────

    def _setup_interfaces(self):
        self._setup_editor_interface()
        self._setup_project_interface()

    def _setup_editor_interface(self):
        self._editor_interface = QWidget()
        self._editor_interface.setObjectName("editorInterface")
        layout = QVBoxLayout(self._editor_interface)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._setup_editor_toolbar(layout)
        self._setup_editor_central(layout)
        self._setup_editor_statusbar(layout)

        self._timeline.setFocusPolicy(Qt.StrongFocus)

    def _setup_editor_toolbar(self, layout):
        tb = QWidget()
        tb.setObjectName("editorToolbar")
        tb.setFixedHeight(52)
        hbox = QHBoxLayout(tb)
        hbox.setContentsMargins(16, 8, 16, 8)
        hbox.setSpacing(8)

        # 录制控制
        self._btn_record = PrimaryPushButton(FluentIcon.VIDEO, "录制")
        self._btn_stop_rec = PushButton(FluentIcon.CANCEL_MEDIUM, "停止")
        self._btn_record.clicked.connect(self._toggle_record)
        self._btn_stop_rec.clicked.connect(self._toggle_record)
        self._btn_stop_rec.setEnabled(False)
        hbox.addWidget(self._btn_record)
        hbox.addWidget(self._btn_stop_rec)
        hbox.addSpacing(16)

        # 播放控制
        self._btn_rewind = ToolButton(FluentIcon.SKIP_BACK)
        self._btn_rewind.setToolTip("后退 10 帧")
        self._btn_step_back = ToolButton(FluentIcon.CARE_LEFT_SOLID)
        self._btn_step_back.setToolTip("上一帧")
        self._btn_play = ToolButton(FluentIcon.PLAY)
        self._btn_play.setToolTip("播放")
        self._btn_step_fwd = ToolButton(FluentIcon.CARE_RIGHT_SOLID)
        self._btn_step_fwd.setToolTip("下一帧")
        self._btn_ff = ToolButton(FluentIcon.SKIP_FORWARD)
        self._btn_ff.setToolTip("快进")

        self._btn_rewind.clicked.connect(self._on_rewind)
        self._btn_step_back.clicked.connect(self._on_step_back)
        self._btn_play.clicked.connect(self._on_play_toggle)
        self._btn_step_fwd.clicked.connect(self._on_step_fwd)
        self._btn_ff.clicked.connect(self._on_fast_forward)

        self._btn_rewind.setEnabled(False)
        self._btn_step_back.setEnabled(False)
        self._btn_play.setEnabled(False)
        self._btn_step_fwd.setEnabled(False)
        self._btn_ff.setEnabled(False)

        hbox.addWidget(self._btn_rewind)
        hbox.addWidget(self._btn_step_back)
        hbox.addWidget(self._btn_play)
        hbox.addWidget(self._btn_step_fwd)
        hbox.addWidget(self._btn_ff)
        hbox.addSpacing(8)

        # 帧计数器
        self._frame_label = QLabel("0 / 0")
        self._frame_label.setStyleSheet("color: #999; font-size: 12px;")
        hbox.addWidget(self._frame_label)
        hbox.addSpacing(16)

        # 导出
        self._btn_export = ToolButton(FluentIcon.SHARE)
        self._btn_export.setToolTip("导出")
        self._btn_export.clicked.connect(self._on_export)
        self._btn_export.setEnabled(False)
        hbox.addWidget(self._btn_export)
        hbox.addStretch()

        layout.addWidget(tb)

    def _setup_editor_central(self, layout):
        splitter = QSplitter(Qt.Vertical)
        self._preview = PreviewWidget()
        self._preview.setMinimumSize(640, 480)

        self._timeline = TimelineWidget()

        splitter.addWidget(self._preview)
        splitter.addWidget(self._timeline)
        splitter.setSizes([480, 200])
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter, 1)

    def _setup_editor_statusbar(self, layout):
        sb = QWidget()
        sb.setObjectName("editorStatusBar")
        sb.setFixedHeight(28)
        hbox = QHBoxLayout(sb)
        hbox.setContentsMargins(16, 0, 16, 0)
        self._status_label = CaptionLabel("● 准备就绪")
        hbox.addWidget(self._status_label)
        hbox.addStretch()
        layout.addWidget(sb)

    def _on_open_settings(self):
        from ui.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self.config, self)
        if dialog.exec_() == SettingsDialog.Accepted:
            self._compositor.fps = self.config.default_fps
            if hasattr(self, '_cursor_effect'):
                self._cursor_effect.cursor_size = self.config.cursor_size
                self._cursor_effect.cursor_theme = self.config.cursor_theme
                self._cursor_effect.enabled["trail"] = self.config.trail_enabled
            self._compositor.set_preview_quality(self.config.preview_quality)

    def _setup_project_interface(self):
        self._project_interface = QWidget()
        self._project_interface.setObjectName("projectInterface")
        layout = QVBoxLayout(self._project_interface)
        layout.setContentsMargins(0, 0, 0, 0)
        self._file_list = QListWidget()
        self._file_list.setStyleSheet("""
            QListWidget {
                background: transparent; border: none;
                color: white; font-size: 13px;
            }
            QListWidget::item { padding: 8px 20px; }
            QListWidget::item:hover {
                background: rgba(255,255,255,0.08);
            }
            QListWidget::item:selected {
                background: rgba(255,255,255,0.12);
            }
        """)
        layout.addWidget(self._file_list)

    # ── 导航 ──────────────────────────────────────────────

    def _setup_navigation(self):
        self.addSubInterface(
            self._editor_interface, FluentIcon.EDIT, "编辑")
        self.addSubInterface(
            self._project_interface, FluentIcon.FOLDER, "项目文件")
        self.navigationInterface.addItem(
            routeKey="settings",
            icon=FluentIcon.SETTING,
            text="设置",
            onClick=self._on_open_settings,
            selectable=False,
            position=NavigationItemPosition.BOTTOM,
        )

    # ── 系统托盘 ──────────────────────────────────────────

    def _setup_tray(self):
        from PyQt5.QtWidgets import QSystemTrayIcon, QMenu

        px = QPixmap(32, 32)
        px.fill(Qt.transparent)
        with QPainter(px) as p:
            p.setBrush(QColor("#0078D4"))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(4, 4, 24, 24, 4, 4)
            p.setPen(QColor("white"))
            p.setFont(self.font())
            p.drawText(px.rect(), Qt.AlignCenter, "R")
        icon = QIcon(px)
        self._tray = QSystemTrayIcon(icon, self)
        self._tray.setToolTip("Recordly")

        menu = QMenu()
        self._tray_record_act = menu.addAction("⬤ 开始录制", self._toggle_record)
        self._tray_stop_act = menu.addAction("■ 停止录制", self._toggle_record)
        self._tray_stop_act.setEnabled(False)
        menu.addSeparator()
        menu.addAction("显示窗口", self.showNormal)
        menu.addAction("退出", QApplication.quit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _on_tray_activated(self, reason):
        from PyQt5.QtWidgets import QSystemTrayIcon
        if reason == QSystemTrayIcon.DoubleClick:
            self.showNormal()
            self.raise_()

    # ── 录制 ──────────────────────────────────────────────

    def _toggle_record(self):
        if self._is_recording:
            self._is_recording = False
            self.recording_stopped.emit()
        else:
            self._is_recording = True
            self.recording_started.emit()
        self._update_ui_state()

    def _on_recording_started(self):
        self._recorder.start_recording()
        self.update_status("● 录制中...")

    def _on_recording_stopped(self):
        self._recorded_data = self._recorder.stop_recording()
        if self._recorded_data and self._recorded_data.get("frames"):
            self._compositor.load_frames(self._recorded_data["frames"])
            self._compositor.load_cursor_events(
                self._recorded_data.get("cursor_events", []),
                self._recorded_data.get("clicks", []),
            )
            from core.cursor_effects import CursorEffect
            self._cursor_effect = CursorEffect(
                cursor_size=self.config.cursor_size,
                cursor_theme=self.config.cursor_theme,
            )
            self._compositor.register_effect("cursor", self._cursor_effect)
            if not self.config.trail_enabled:
                self._cursor_effect.enabled["trail"] = False
            self._btn_export.setEnabled(True)
            self._enable_playback_controls(True)
            total = len(self._compositor._frames)
            self._frame_label.setText(f"1 / {total}")
            from ui.preview_widget import PlaybackController
            self._playback = PlaybackController(self._preview, self._compositor)
            self._playback.set_on_frame_changed(self._update_frame_counter)
            self._playback.seek(0)
            self._populate_timeline()
            self._timeline.playhead_changed.connect(self._on_timeline_seek)
            self._timeline.zoom_double_clicked.connect(self._on_zoom_double_clicked)
        self.update_status("● 录制完成")

    def _populate_timeline(self):
        """录制结束后在时间线中创建视频、音频、缩放轨道"""
        frames = self._compositor._frames
        if not frames:
            return
        duration = len(frames) / self._compositor.fps
        tracks = []
        tracks.append(Track(type="video", name="视频", clips=[
            Clip(type="video", start=0, end=duration,
                 content=f"屏幕录制 {self._compositor.width}x{self._compositor.height}"),
        ]))

        tracks.append(Track(type="audio", name="音频", clips=[
            Clip(type="audio", start=0, end=duration, content="麦克风"),
        ]))

        clicks = self._recorded_data.get("clicks", [])
        cursor_events = self._recorded_data.get("cursor_events", [])
        base_time = frames[0].timestamp
        from core.camera import build_camera
        camera = build_camera(clicks, self._compositor.fps,
                              self._compositor.width,
                              self._compositor.height, duration,
                              cursor_events, base_time)
        self._compositor.load_camera(camera)

        zoom_segs = camera.zoomed_segments if camera else []
        zoom_clips = [Clip(type="zoom", start=s, end=e, content="缩放")
                      for s, e in zoom_segs]
        tracks.append(Track(type="zoom", name="缩放", clips=zoom_clips))

        self._timeline.set_tracks(tracks)
        self._timeline.duration = duration

    # ── 状态更新 ──────────────────────────────────────────

    def _update_ui_state(self):
        rec = self._is_recording
        self._btn_record.setEnabled(not rec)
        self._btn_stop_rec.setEnabled(rec)
        self._btn_export.setEnabled(not rec)
        self._tray_record_act.setEnabled(not rec)
        self._tray_stop_act.setEnabled(rec)
        self.update_status("● 录制中..." if rec else "● 准备就绪")

    def set_recording_state(self, recording: bool):
        self._is_recording = recording
        self._update_ui_state()

    def update_status(self, text: str):
        self._status_label.setText(text)

    def show_preview(self, pixmap: QPixmap):
        self._preview.show_frame(pixmap)

    def _on_play_toggle(self):
        if not self._recorded_data:
            return
        if not self._playback:
            from ui.preview_widget import PlaybackController
            self._playback = PlaybackController(self._preview, self._compositor)
            self._playback.set_on_frame_changed(self._update_frame_counter)
            start_frame = int(self._timeline.playhead * self._compositor.fps)
            self._playback.play(start_frame)
            self._btn_play.setIcon(FluentIcon.CANCEL)
            self._btn_play.setToolTip("暂停")
        elif not self._playback._playing:
            self._playback.play(self._playback._current_frame)
            self._btn_play.setIcon(FluentIcon.CANCEL)
            self._btn_play.setToolTip("暂停")
        elif self._playback.is_paused:
            self._playback.pause()
            self._btn_play.setIcon(FluentIcon.CANCEL)
            self._btn_play.setToolTip("暂停")
        else:
            self._playback.pause()
            self._btn_play.setIcon(FluentIcon.PLAY)
            self._btn_play.setToolTip("继续播放")

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
            self._btn_play.setIcon(FluentIcon.CANCEL)

    def _update_frame_counter(self, idx: int):
        total = self._playback.total_frames
        self._frame_label.setText(f"{idx + 1} / {total}")
        # 同步时间线播放头
        sec = idx / self._compositor.fps
        self._timeline.playhead = sec

    def _on_timeline_seek(self, sec: float):
        if not self._playback:
            return
        idx = int(sec * self._compositor.fps)
        self._playback.seek(idx)
        self._update_frame_counter(idx)

    def _on_zoom_double_clicked(self, time_s: float):
        ratio = self.config.zoom_rect_ratio
        w = int(self._compositor.width * ratio)
        h = int(self._compositor.height * ratio)
        cx = self._compositor.width // 2
        cy = self._compositor.height // 2
        clip = Clip(type="zoom", start=time_s, end=min(time_s + 2.0, self._timeline.duration),
                    content="手动缩放", rect=[cx - w // 2, cy - h // 2, w, h])
        for track in self._timeline.tracks:
            if track.type == "zoom":
                track.clips.append(clip)
                break
        self._compositor.load_manual_zoom_clips(
            [c for t in self._timeline.tracks if t.type == "zoom"
             for c in t.clips if c.rect])
        self._preview.show_zoom_rect(clip.rect,
                                     self._compositor.width, self._compositor.height)
        try:
            self._preview.overlay.rect_changed.disconnect()
        except TypeError:
            pass
        self._preview.overlay.rect_changed.connect(self._on_zoom_rect_changed)
        self._timeline.update()

    def _on_zoom_rect_changed(self, x, y, w, h):
        """预览框被拖拽后，更新当前 zoom clip 的 rect"""
        for track in self._timeline.tracks:
            if track.type == "zoom" and track.clips:
                track.clips[-1].rect = [x, y, w, h]
        self._compositor.load_manual_zoom_clips(
            [c for t in self._timeline.tracks if t.type == "zoom"
             for c in t.clips if c.rect])

    def _enable_playback_controls(self, enabled: bool):
        self._btn_rewind.setEnabled(enabled)
        self._btn_step_back.setEnabled(enabled)
        self._btn_play.setEnabled(enabled)
        self._btn_step_fwd.setEnabled(enabled)
        self._btn_ff.setEnabled(enabled)

    # ── 导出 ──────────────────────────────────────────────

    def _on_export(self):
        if not self._recorded_data:
            InfoBar.warning(
                title="无法导出",
                content="请先录制一段视频",
                orient=Qt.Horizontal, isClosable=True,
                position=InfoBarPosition.TOP_RIGHT, duration=3000, parent=self,
            )
            return
        path, fmt = QFileDialog.getSaveFileName(
            self, "导出视频", self.config.recordings_dir,
            "MP4 (*.mp4);;GIF (*.gif)")
        if not path:
            return
        is_gif = path.lower().endswith(".gif")
        if not path.lower().endswith((".mp4", ".gif")):
            QMessageBox.warning(self, "导出失败", "请指定文件名并选择 MP4 或 GIF 格式")
            return
        settings = ExportSettings(
            output_path=path,
            format="gif" if is_gif else "mp4",
            fps=self.config.default_fps,
            bitrate=self.config.default_bitrate,
        )
        self._btn_export.setEnabled(False)

        audio = self._recorded_data.get("audio")
        audio_data = audio.data if audio else None

        # 创建工作线程
        self._export_worker = ExportWorker(self._compositor, audio_data, settings)
        self._export_thread = QThread(self)
        self._export_worker.moveToThread(self._export_thread)

        self._export_thread.started.connect(self._export_worker.run)
        self._export_worker.finished.connect(self._on_export_finished)
        self._export_worker.finished.connect(self._export_thread.quit)
        self._export_worker.finished.connect(self._export_worker.deleteLater)
        self._export_thread.finished.connect(self._export_thread.deleteLater)

        # 进度对话框
        self._progress = QProgressDialog("正在导出视频...", "取消", 0, 100, self)
        self._progress.setWindowTitle("导出")
        self._progress.setWindowModality(Qt.WindowModal)
        self._progress.setAutoClose(True)
        self._progress.setAutoReset(True)
        self._progress.setStyleSheet("""
            QProgressDialog { background: #1e1e1e; color: white; min-width: 360px; }
            QProgressBar {
                border: 1px solid #323232; border-radius: 4px;
                background: #2d2d2d; text-align: center; color: white;
            }
            QProgressBar::chunk { background: #0078D4; border-radius: 3px; }
            QLabel { color: #ccc; font-size: 13px; }
            QPushButton { color: white; background: #323232; border: none;
                          padding: 4px 16px; border-radius: 4px; }
            QPushButton:hover { background: #424242; }
        """)

        self._export_worker.progress.connect(self._progress.setValue)
        self._progress.canceled.connect(self._cancel_export)

        self._export_thread.start()

    def _cancel_export(self):
        if self._export_worker:
            self._export_worker.cancel()

    def _on_export_finished(self, result):
        self._progress.close()
        self._btn_export.setEnabled(True)
        self._export_thread = None
        self._export_worker = None

        if result.success:
            self.update_status("● 导出完成")
            InfoBar.success(
                title="导出完成",
                content=f"视频已保存到:\n{result.path}\n({result.size_bytes/1024/1024:.1f}MB)",
                orient=Qt.Horizontal, isClosable=True,
                position=InfoBarPosition.TOP_RIGHT, duration=5000, parent=self,
            )
        else:
            self.update_status("● 导出失败")
            InfoBar.error(
                title="导出失败",
                content=result.error or "未知错误",
                orient=Qt.Horizontal, isClosable=True,
                position=InfoBarPosition.TOP_RIGHT, duration=5000, parent=self,
            )

    # ── 菜单操作 ──────────────────────────────────────────

    def _on_new_project(self):
        self.update_status("● 新建项目...")

    def _on_open_project(self):
        self.update_status("● 打开项目...")

    def _on_save_project(self):
        self.update_status("● 保存项目...")

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _on_about(self):
        QMessageBox.about(self, "关于 Recordly",
            "Recordly v1.0\n\n开源演示视频录制与编辑工具\n\n基于 PyQt5 + FFmpeg")

    def _on_undo(self):
        if hasattr(self, '_timeline'):
            self._timeline.undo()

    def _on_redo(self):
        if hasattr(self, '_timeline'):
            self._timeline.redo()

    def _on_add_text_track(self):
        from PyQt5.QtWidgets import QInputDialog
        text, ok = QInputDialog.getText(self, "添加文字标注", "输入标注内容:")
        if not ok or not text:
            return
        track = self._make_track("text", text)
        self._timeline.tracks.append(track)
        self._timeline.update()

    def _on_add_camera_track(self):
        from PyQt5.QtWidgets import QInputDialog
        device, ok = QInputDialog.getText(self, "添加画中画", "摄像头设备号 (默认 0):", text="0")
        if not ok:
            return
        track = self._make_track("camera", device or "0")
        self._timeline.tracks.append(track)
        self._timeline.update()

    def _on_delete_selected_track(self):
        idx = self._timeline.selected_index
        if idx >= 0:
            track = self._timeline.tracks[idx]
            if track.clips:
                self._timeline.delete_clip(idx, 0)

    def _make_track(self, type_: str, content: str):
        from core.project import Clip, Track
        return Track(type=type_, name=type_, clips=[
            Clip(type=type_, content=content,
                 start=0.0, end=self._timeline.duration),
        ])

    @property
    def timeline_tracks(self) -> list:
        return getattr(self, '_timeline', None) and self._timeline.tracks or []
