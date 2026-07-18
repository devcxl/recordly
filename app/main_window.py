"""Recordly 主窗口 — 纯 PyQt5"""

import os
import shutil
import subprocess
import wave
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
    QFileDialog, QApplication, QMessageBox, QToolBar, QAction,
    QStackedWidget, QStatusBar, QPushButton, QToolButton,
    QLabel, QProgressDialog, QScrollArea, QShortcut, QLineEdit,
    QTextEdit, QPlainTextEdit, QAbstractSpinBox, QComboBox,
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QPixmap, QPainter, QColor, QKeySequence, QIcon
from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QDesktopServices

from app.config import AppConfig
from core.compositor import Compositor
from core.exporter import ExportSettings
from core.project import (
    Clip, Track, AudioRegion, CropRegion, Project, SourceInfo,
    sync_audio_regions_from_clips,
)
from core.project_manager import ProjectManager
from ui.preview_widget import PreviewWidget
from ui.timeline import TimelineWidget
from ui.crop_overlay import CropOverlay
from ui.export_dialog import ExportDialog
from ui.home_page import HomePage
from app.project_session import ProjectSession
from app.recording_controller import RecordingController, RecordingState
from app.export_controller import ExportController


def _write_wav(path: str, data, samplerate: int):
    """将 numpy float32 音频数据写入 16-bit PCM WAV 文件"""
    import numpy as np
    arr = np.asarray(data, dtype=np.float32)
    arr = np.clip(arr, -1.0, 1.0)
    if arr.ndim == 1:
        channels = 1
        arr = arr.reshape(-1, 1)
    else:
        channels = arr.shape[1]
    samples = (arr * 32767).astype(np.int16)
    with wave.open(path, "w") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(samplerate)
        wf.writeframes(samples.tobytes())


def _read_wav(path: str):
    """从 WAV 文件读取为 (numpy float32 数组, samplerate, channels)"""
    import numpy as np
    if not os.path.exists(path):
        return None
    with wave.open(path, "r") as wf:
        samplerate = wf.getframerate()
        channels = wf.getnchannels()
        frames = wf.readframes(wf.getnframes())
        samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        if channels > 1:
            samples = samples.reshape(-1, channels)
        return samples, samplerate, channels


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


def _load_project_audio(project_dir: str, source) -> "AudioResult | None":
    """从 project.json source 声明的 WAV 路径恢复混合音频。无音频时返回 None。"""
    from core.audio_capture import AudioResult, mix_audio_results

    mic_audio = None
    sys_audio = None
    if source and source.audio_mic:
        mic_path = _resolve_media_path(project_dir, source.audio_mic)
        result = _read_wav(mic_path)
        if result is not None:
            data, sr, ch = result
            mic_audio = AudioResult(data, sr, ch)
    if source and source.audio_system:
        sys_path = _resolve_media_path(project_dir, source.audio_system)
        result = _read_wav(sys_path)
        if result is not None:
            data, sr, ch = result
            sys_audio = AudioResult(data, sr, ch)

    if mic_audio is None and sys_audio is None:
        return None
    return mix_audio_results(mic_audio, sys_audio)


class MainWindow(QMainWindow):
    """主窗口，管理录制/预览/导出的生命周期"""

    recording_started = pyqtSignal()
    recording_stopped = pyqtSignal()
    export_requested = pyqtSignal(str)

    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self._project_session: ProjectSession | None = None
        self._recording_controller = RecordingController(config)
        self._compositor = Compositor(1920, 1080, config.default_fps)
        self._recorded_data = None
        self._audio_regions = []
        self._export_controller = ExportController(self)
        self._progress = None
        self._playback = None
        self._editing_zoom_clip = None
        self._crop_overlay = None
        self._crop_active = False
        os.makedirs(config.projects_dir, exist_ok=True)
        self._project_manager = ProjectManager(config.projects_dir)

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

    def _setup_window(self):
        self.setWindowTitle("Recordly v1.0")
        self.resize(1280, 800)
        screen = QApplication.primaryScreen().geometry()
        self.move(
            (screen.width() - self.width()) // 2,
            (screen.height() - self.height()) // 2,
        )
        self.setStyleSheet("""
            #mainToolbar {
                background: #1e1e1e;
                border-bottom: 1px solid #323232;
                padding: 4px 12px;
                spacing: 6px;
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

    # ── 通知 ──────────────────────────────────────────────

    def _show_notification(self, title: str, content: str, level: str = "info"):
        """显示通知：info 用状态栏，warning/error 用 QMessageBox"""
        if level == "info":
            self.statusBar().showMessage(f"{title}: {content}", 5000)
        elif level == "success":
            self.statusBar().showMessage(f"✓ {title}: {content}", 5000)
        elif level == "warning":
            QMessageBox.warning(self, title, content)
        elif level == "error":
            QMessageBox.critical(self, title, content)

    # ── 界面 ──────────────────────────────────────────────

    def _setup_interfaces(self):
        self._setup_editor_interface()
        self._setup_home_page()

    def _setup_editor_interface(self):
        self._editor_interface = QWidget()
        self._editor_interface.setObjectName("editorInterface")
        layout = QVBoxLayout(self._editor_interface)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._setup_editor_central(layout)
        self._setup_editor_statusbar(layout)

        self._timeline.setFocusPolicy(Qt.StrongFocus)

    def _setup_editor_central(self, layout):
        splitter = QSplitter(Qt.Vertical)
        self._preview = PreviewWidget()
        self._preview.setMinimumSize(640, 480)

        self._timeline = TimelineWidget()
        self._timeline_scroll = QScrollArea()
        self._timeline_scroll.setWidget(self._timeline)
        self._timeline_scroll.setWidgetResizable(True)
        self._timeline_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._timeline_scroll.setFrameShape(QScrollArea.NoFrame)

        splitter.addWidget(self._preview)
        splitter.addWidget(self._timeline_scroll)
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
        self._status_label = QLabel("● 准备就绪")
        self._status_label.setStyleSheet("color: #999;")
        hbox.addWidget(self._status_label)
        hbox.addStretch()
        layout.addWidget(sb)

    def _on_open_settings(self):
        from ui.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self.config, self)
        if dialog.exec_() == SettingsDialog.Accepted:
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

    def _setup_home_page(self):
        self._home_page = HomePage(self._project_manager, self)
        self._home_page.record_requested.connect(self._on_home_record)
        self._home_page.open_project_requested.connect(self._on_home_open_project)
        self._home_page.project_opened.connect(self._on_open_project)
        self._home_page.project_deleted.connect(self._on_project_deleted)
        self._home_page.project_renamed.connect(self._on_project_renamed)
        self._refresh_home_page()

    # ── 导航 ──────────────────────────────────────────────

    def _setup_navigation(self):
        self._setup_menus()
        self._setup_toolbar()
        self._setup_central_widget()
        self._setup_space_shortcut()
        self._setup_undo_redo_shortcuts()

    def _setup_space_shortcut(self):
        self._space_shortcut = QShortcut(
            QKeySequence(Qt.Key_Space), self)
        self._space_shortcut.setContext(Qt.WindowShortcut)
        self._space_shortcut.setAutoRepeat(False)
        self._space_shortcut.activated.connect(self._on_space_shortcut)

    def _on_space_shortcut(self):
        if not self._is_editor_active_and_safe():
            return
        self._on_play_toggle()

    def _is_editor_active_and_safe(self) -> bool:
        """编辑器在前台且无文本输入焦点时返回 True。
        提取自 _on_space_shortcut，供所有编辑器级快捷键复用。"""
        if self._stacked_widget.currentWidget() is not self._editor_interface:
            return False
        if QApplication.activeWindow() is not self:
            return False
        if QApplication.activeModalWidget() is not None:
            return False
        if QApplication.activePopupWidget() is not None:
            return False
        if isinstance(QApplication.focusWidget(), (
            QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox, QComboBox,
        )):
            return False
        return True

    def _setup_undo_redo_shortcuts(self):
        self._shortcut_undo = QShortcut(QKeySequence("Ctrl+Z"), self)
        self._shortcut_undo.setContext(Qt.WindowShortcut)
        self._shortcut_undo.setAutoRepeat(False)
        self._shortcut_undo.activated.connect(self._maybe_undo)

        self._shortcut_redo = QShortcut(QKeySequence("Ctrl+Shift+Z"), self)
        self._shortcut_redo.setContext(Qt.WindowShortcut)
        self._shortcut_redo.setAutoRepeat(False)
        self._shortcut_redo.activated.connect(self._maybe_redo)

        self._shortcut_redo_alt = QShortcut(QKeySequence("Ctrl+Y"), self)
        self._shortcut_redo_alt.setContext(Qt.WindowShortcut)
        self._shortcut_redo_alt.setAutoRepeat(False)
        self._shortcut_redo_alt.activated.connect(self._maybe_redo)

    def _maybe_undo(self):
        if self._is_editor_active_and_safe():
            self._on_undo()

    def _maybe_redo(self):
        if self._is_editor_active_and_safe():
            self._on_redo()

    def _setup_menus(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("文件")
        self._menu_save = file_menu.addAction("保存", self._on_save_project)
        self._menu_export = file_menu.addAction("导出", self._on_export)
        self._menu_back_home = file_menu.addAction("返回首页", self._switch_to_home)
        file_menu.addSeparator()
        self._menu_settings = file_menu.addAction("设置", self._on_open_settings)
        file_menu.addSeparator()
        file_menu.addAction("退出", QApplication.quit)

        self._setup_edit_menu(menubar)

        help_menu = menubar.addMenu("帮助")
        help_menu.addAction("反馈", lambda: QDesktopServices.openUrl(
            QUrl("https://github.com/devcxl/recordly/issues/new")))
        help_menu.addAction("关于", self._on_about)

    def _setup_edit_menu(self, menubar):
        edit_menu = menubar.addMenu("编辑")
        self._undo_action = QAction("撤销", self)
        self._undo_action.triggered.connect(self._on_undo)
        edit_menu.addAction(self._undo_action)

        self._redo_action = QAction("重做", self)
        self._redo_action.triggered.connect(self._on_redo)
        edit_menu.addAction(self._redo_action)

    def _setup_toolbar(self):
        self._toolbar = QToolBar("工具")
        self._toolbar.setObjectName("mainToolbar")
        self._toolbar.setMovable(False)
        self._toolbar.setFloatable(False)
        self.addToolBar(self._toolbar)

        self._add_undo_redo_toolbar_buttons()
        self._add_playback_toolbar_buttons()
        self._toolbar.addSeparator()

        self._frame_label = QLabel("0 / 0")
        self._frame_label.setStyleSheet("color: #999; font-size: 12px;")
        self._toolbar.addWidget(self._frame_label)

        self._time_label = QLabel("00:00.000 / 00:00.000")
        self._time_label.setStyleSheet("color: #999; font-size: 12px;")
        self._toolbar.addWidget(self._time_label)
        self._toolbar.addSeparator()

        self._add_toolbar_action_buttons()

    def _add_undo_redo_toolbar_buttons(self):
        self._btn_undo = QToolButton()
        self._btn_undo.setText("↩")
        self._btn_undo.setToolTip("撤销 (Ctrl+Z)")
        self._btn_undo.setEnabled(False)
        self._btn_undo.clicked.connect(self._on_undo)

        self._btn_redo = QToolButton()
        self._btn_redo.setText("↪")
        self._btn_redo.setToolTip("重做 (Ctrl+Shift+Z)")
        self._btn_redo.setEnabled(False)
        self._btn_redo.clicked.connect(self._on_redo)

        for btn in [self._btn_undo, self._btn_redo]:
            btn.setStyleSheet("font-size: 16px;")
            self._toolbar.addWidget(btn)

        self._toolbar.addSeparator()

    def _add_playback_toolbar_buttons(self):
        self._btn_rewind = QToolButton()
        self._btn_rewind.setText("⏪")
        self._btn_rewind.setToolTip("后退 10 帧")
        self._btn_step_back = QToolButton()
        self._btn_step_back.setText("◀")
        self._btn_step_back.setToolTip("上一帧")
        self._btn_play = QToolButton()
        self._btn_play.setText("▶")
        self._btn_play.setToolTip("播放")
        self._btn_step_fwd = QToolButton()
        self._btn_step_fwd.setText("⏭")
        self._btn_step_fwd.setToolTip("下一帧")
        self._btn_ff = QToolButton()
        self._btn_ff.setText("⏩")
        self._btn_ff.setToolTip("快进")

        self._btn_rewind.clicked.connect(self._on_rewind)
        self._btn_step_back.clicked.connect(self._on_step_back)
        self._btn_play.clicked.connect(self._on_play_toggle)
        self._btn_step_fwd.clicked.connect(self._on_step_fwd)
        self._btn_ff.clicked.connect(self._on_fast_forward)

        for btn in [self._btn_rewind, self._btn_step_back,
                     self._btn_play, self._btn_step_fwd, self._btn_ff]:
            btn.setEnabled(False)

        for btn in [self._btn_rewind, self._btn_step_back, self._btn_play,
                     self._btn_step_fwd, self._btn_ff]:
            btn.setStyleSheet("font-size: 16px;")
            self._toolbar.addWidget(btn)

    def _add_toolbar_action_buttons(self):
        self._btn_export = QToolButton()
        self._btn_export.setText("📤")
        self._btn_export.setToolTip("导出")
        self._btn_export.clicked.connect(self._on_export)
        self._btn_export.setEnabled(False)
        self._btn_export.setStyleSheet("font-size: 16px;")
        self._toolbar.addWidget(self._btn_export)

        self._btn_crop = QToolButton()
        self._btn_crop.setText("✂")
        self._btn_crop.setToolTip("裁剪模式")
        self._btn_crop.setCheckable(True)
        self._btn_crop.toggled.connect(self._on_crop_toggled)
        self._btn_crop.setEnabled(False)
        self._btn_crop.setStyleSheet("font-size: 16px;")
        self._toolbar.addWidget(self._btn_crop)

        self._btn_add_audio = QToolButton()
        self._btn_add_audio.setText("🎵")
        self._btn_add_audio.setToolTip("添加额外音频")
        self._btn_add_audio.clicked.connect(self._on_add_audio)
        self._btn_add_audio.setEnabled(False)
        self._btn_add_audio.setStyleSheet("font-size: 16px;")
        self._toolbar.addWidget(self._btn_add_audio)

    def _setup_central_widget(self):
        self._stacked_widget = QStackedWidget()
        self._stacked_widget.addWidget(self._home_page)
        self._stacked_widget.addWidget(self._editor_interface)
        self.setCentralWidget(self._stacked_widget)

        self.setStatusBar(QStatusBar())
        self._toolbar.setVisible(False)
        self._update_menu_visibility()

    # ── 页面管理 ──────────────────────────────────────────

    def _switch_to_home(self):
        """切换到首页"""
        self._toolbar.setVisible(False)
        self._home_page.refresh_projects()
        self._stacked_widget.setCurrentWidget(self._home_page)
        self._update_menu_visibility()

    def _switch_to_editor(self):
        """切换到编辑器"""
        self._toolbar.setVisible(True)
        self._stacked_widget.setCurrentWidget(self._editor_interface)
        self._update_menu_visibility()

    def _update_menu_visibility(self):
        """按当前页面显示/隐藏菜单项"""
        is_editor = self._stacked_widget.currentWidget() == self._editor_interface
        self._menu_save.setVisible(is_editor)
        self._menu_export.setVisible(is_editor)
        self._menu_back_home.setVisible(is_editor)
        self._menu_settings.setVisible(not is_editor)

    def _refresh_undo_redo_state(self):
        """根据 can_undo/can_redo 同步菜单项和工具栏按钮状态"""
        if not hasattr(self, '_undo_action'):
            return
        tl = self._timeline
        can_undo = tl.can_undo
        can_redo = tl.can_redo
        undo_desc = tl.undo_description
        redo_desc = tl.redo_description

        self._undo_action.setEnabled(can_undo)
        self._undo_action.setText(f"撤销 {undo_desc}\tCtrl+Z" if undo_desc else "撤销\tCtrl+Z")

        self._redo_action.setEnabled(can_redo)
        self._redo_action.setText(f"重做 {redo_desc}\tCtrl+Shift+Z" if redo_desc else "重做\tCtrl+Shift+Z")

        self._btn_undo.setEnabled(can_undo)
        self._btn_undo.setToolTip(
            f"撤销 {undo_desc} (Ctrl+Z)" if undo_desc else "撤销 (Ctrl+Z)")

        self._btn_redo.setEnabled(can_redo)
        self._btn_redo.setToolTip(
            f"重做 {redo_desc} (Ctrl+Shift+Z)" if redo_desc else "重做 (Ctrl+Shift+Z)")

    def _refresh_home_page(self):
        """刷新首页项目列表"""
        self._home_page.refresh_projects()

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

    # ── 首页交互 ──────────────────────────────────────────

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
            self._populate_timeline()
            self._create_playback_controller()
            self._playback.seek(0)
            self._connect_timeline_signals()
        self.update_status("● 录制完成")
        self._finalize_project()
        # 立即切换到编辑器
        self._switch_to_editor()
        self.showNormal()
        self.raise_()

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
            mic_audio = self._recorded_data.get("mic_audio")
            if mic_audio is not None and len(mic_audio.data) > 0:
                mic_path = "audio_mic.wav"
                _write_wav(str(project_dir / mic_path), mic_audio.data, mic_audio.samplerate)
            sys_audio = self._recorded_data.get("system_audio")
            if sys_audio is not None and len(sys_audio.data) > 0:
                system_path = "audio_system.wav"
                _write_wav(str(project_dir / system_path), sys_audio.data, sys_audio.samplerate)

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

    def _connect_timeline_signals(self):
        """重复录制时保持时间线信号单次连接。"""
        pairs = (
            (self._timeline.playhead_changed, self._on_timeline_seek),
            (self._timeline.zoom_double_clicked, self._on_zoom_double_clicked),
            (self._timeline.zoom_add_requested, self._on_zoom_double_clicked),
            (self._timeline.zoom_clip_selected, self._on_zoom_clip_selected),
            (self._timeline.clips_changed, self._on_clips_changed),
            (self._timeline.clips_changed, self._refresh_undo_redo_state),
            (self._timeline.status_message, self.update_status),
            (self._timeline.playhead_seek_play, self._on_playhead_seek_play),
        )
        for signal, slot in pairs:
            try:
                signal.disconnect(slot)
            except TypeError:
                pass
            signal.connect(slot)

    def _populate_timeline(self):
        """录制结束后在时间线中创建视频、音频、缩放轨道"""
        frames = self._compositor.frames
        if not frames:
            return
        duration = self._get_recording_duration()
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
                              cursor_events, base_time,
                              self._compositor.monitor_left,
                              self._compositor.monitor_top)
        self._compositor.load_camera(camera)

        zoom_clips = camera.build_zoom_clips() if camera else []
        tracks.append(Track(type="zoom", name="缩放", clips=zoom_clips))

        self._timeline.set_tracks(tracks)
        self._timeline.duration = duration
        self._compositor.load_clips(tracks[0].clips)
        self._compositor.load_manual_zoom_clips(zoom_clips)
        if self._audio_regions:
            self._update_audio_timeline()

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

    def _get_recording_duration(self) -> float:
        duration = getattr(self._compositor, "source_duration", 0.0)
        if duration > 0:
            return duration
        return len(self._compositor.frames) / self._compositor.fps

    # ── 状态更新 ──────────────────────────────────────────

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

    def show_preview(self, pixmap: QPixmap):
        self._preview.show_frame(pixmap)

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

        # 焦点守卫（与 _on_space_shortcut 一致，_is_editor_active_and_safe 尚未提取）
        if self._stacked_widget.currentWidget() is not self._editor_interface:
            return
        if QApplication.activeWindow() is not self:
            return
        if QApplication.activeModalWidget() is not None:
            return
        if QApplication.activePopupWidget() is not None:
            return
        if isinstance(QApplication.focusWidget(), (
            QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox, QComboBox,
        )):
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
        from ui.preview_widget import PlaybackController

        video_clips = [
            clip for track in self._timeline.tracks if track.type == "video"
            for clip in track.clips
        ]
        audio_result = (
            self._recorded_data.get("audio") if self._recorded_data else None
        )
        self._playback = PlaybackController(
            self._preview,
            self._compositor,
            audio_result=audio_result,
            video_clips=video_clips,
        )
        self._preview.set_fps(int(self._compositor.fps))
        self._playback.set_on_frame_changed(self._update_frame_counter)

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
        self._timeline.duration = max(
            (clip.end for clip in video_clips), default=0.1)
        self._compositor.load_clips(video_clips)
        if self._playback:
            current_frame = self._playback.current_frame
            self._playback.stop()
            self._create_playback_controller()
            self._playback.seek(current_frame)
        audio_clips = [
            c for t in self._timeline.tracks if t.type == "audio_extra"
            for c in t.clips
        ]
        self._audio_regions = sync_audio_regions_from_clips(
            audio_clips, self._audio_regions)
        zoom_clips = [
            c for t in self._timeline.tracks if t.type == "zoom"
            for c in t.clips
        ]
        if self._editing_zoom_clip not in zoom_clips:
            self._editing_zoom_clip = None
            self._preview.hide_zoom_rect()

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

    # ── 导出 ──────────────────────────────────────────────

    def _on_export(self):
        if self._export_controller.is_exporting:
            return
        if not self._recorded_data and not self._compositor.frames:
            self._show_notification(
                "无法导出", "请先录制一段视频或打开一个项目", "warning",
            )
            return
        dialog = ExportDialog(
            self, self.config.recordings_dir,
            self._compositor.fps, self.config.default_bitrate,
        )
        if dialog.exec_() != ExportDialog.Accepted:
            return
        if not dialog.output_path:
            self._show_notification(
                "未选择保存路径", "请选择文件保存位置", "warning",
            )
            return

        settings = self._build_export_settings(dialog)
        self._btn_export.setEnabled(False)
        self._menu_export.setEnabled(False)

        recorded = self._recorded_data or {}
        audio = recorded.get("audio")
        audio_data = audio.data if audio else None
        if audio:
            settings.samplerate = audio.samplerate

        self._start_export_progress(audio_data, settings)

    def _build_export_settings(self, dialog) -> ExportSettings:
        is_gif = dialog.export_format == "gif"
        crop_region = self._compositor.crop_region if self._crop_active else None

        if dialog.is_custom_resolution:
            export_width = dialog.custom_width
            export_height = dialog.custom_height
            export_max_height = None
        else:
            export_width = 0
            export_height = 0
            export_max_height = dialog.resolution_max_height

        return ExportSettings(
            output_path=dialog.output_path,
            format=dialog.export_format,
            aspect_ratio=dialog.aspect_ratio,
            quality=dialog.quality,
            fps=dialog.gif_fps_value if is_gif else dialog.mp4_fps_value,
            bitrate=dialog.bitrate_value,
            loop=dialog.gif_loop_value,
            width=export_width,
            height=export_height,
            max_height=export_max_height,
            extra_audio=self._audio_regions if self._audio_regions else None,
            crop_region=crop_region,
            use_gpu=dialog.use_gpu,
        )

    def _start_export_progress(self, audio_data, settings: ExportSettings):
        self._progress = QProgressDialog("正在导出视频...", "取消", 0, 100, self)
        self._progress.setWindowTitle("导出")
        self._progress.setWindowModality(Qt.WindowModal)
        self._progress.setAutoClose(True)
        self._progress.setAutoReset(True)
        self._progress.canceled.connect(self._cancel_export)

        try:
            self._export_controller.start_export(
                self._compositor, audio_data, settings)
        except Exception as exc:
            self._progress.close()
            self._progress.deleteLater()
            self._progress = None
            self._btn_export.setEnabled(True)
            self._menu_export.setEnabled(True)
            self._show_notification("导出失败", str(exc), "error")

    def _on_export_progress(self, value: int):
        if self._progress is not None:
            self._progress.setValue(value)

    def _cancel_export(self):
        self._export_controller.cancel()

    def _on_export_finished(self, result):
        if self._progress is not None:
            self._progress.close()
            self._progress.deleteLater()
            self._progress = None
        self._btn_export.setEnabled(True)
        self._menu_export.setEnabled(True)

        if result.success:
            self.update_status("● 导出完成")
            self._show_notification(
                "导出完成",
                f"视频已保存到:\n{result.path}\n({result.size_bytes/1024/1024:.1f}MB)",
                "success",
            )
        else:
            self.update_status("● 导出失败")
            self._show_notification(
                "导出失败",
                result.error or "未知错误",
                "error",
            )

    # ── 额外音频 ────────────────────────────────────────────

    def _on_add_audio(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "添加额外音频轨道", "",
            "音频文件 (*.mp3 *.wav *.aac *.m4a *.flac *.ogg)")
        if not path:
            return

        duration_s = self._get_audio_duration(path)
        if duration_s <= 0:
            self._show_notification(
                "无法读取音频",
                f"无法获取文件时长: {os.path.basename(path)}",
                "warning",
            )
            return

        playhead_ms = int(self._timeline.playhead * 1000)
        duration_ms = min(
            int(duration_s * 1000),
            max(0, int(self._timeline.duration * 1000) - playhead_ms),
        )
        if duration_ms <= 0:
            return

        region = AudioRegion(
            id=str(uuid4()),
            start_ms=playhead_ms,
            end_ms=playhead_ms + duration_ms,
            source_start_ms=0,
            source_end_ms=duration_ms,
            audio_path=path,
            volume=1.0,
            name=os.path.basename(path),
        )
        self._audio_regions.append(region)
        self._update_audio_timeline()

        self._show_notification(
            "已添加音频",
            f"{region.name} ({duration_s:.1f}s)",
            "success",
        )

    def _get_audio_duration(self, filepath: str) -> float:
        try:
            result = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_entries',
                 'format=duration', '-of',
                 'default=noprint_wrappers=1:nokey=1', filepath],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
        except Exception:
            pass
        return 0.0

    def _update_audio_timeline(self):
        self._timeline.set_tracks([
            t for t in self._timeline.tracks if t.type != "audio_extra"
        ])

        if self._audio_regions:
            clips = []
            for r in self._audio_regions:
                clips.append(Clip(
                    id=r.id,
                    type="audio_extra",
                    content=r.name,
                    start=r.start_ms / 1000.0,
                    end=r.end_ms / 1000.0,
                    source_start=r.source_start_ms / 1000.0,
                    source_end=(
                        r.source_end_ms / 1000.0
                        if r.source_end_ms is not None else None
                    ),
                    source_path=r.audio_path,
                    volume=r.volume,
                ))
            track = Track(type="audio_extra", name="额外音频", clips=clips)
            self._timeline.tracks.append(track)

        self._timeline._update_height()
        self._timeline.update()

    # ── 菜单操作 ──────────────────────────────────────────

    def _on_new_project(self):
        self.update_status("● 新建项目...")

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

        self._restore_cursor_events(comp, project)
        self._restore_video_frames(comp, project, project_dir)
        mixed_audio = self._restore_project_audio(project_dir, project.source)
        self._build_recorded_data_from_project(comp, mixed_audio)
        self._restore_timeline_and_playback(comp, project)
        self._restore_editor_ui(comp, project)

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
        has_content = bool(comp._frames) or mixed_audio is not None
        if has_content:
            self._recorded_data = {
                "audio": mixed_audio,
                "frames": comp._frames,
                "cursor_events": comp._cursor_events,
                "clicks": comp._click_events,
            }

    def _restore_timeline_and_playback(self, comp, project):
        self._timeline.set_tracks(project.timeline)
        self._timeline.duration = project.duration
        for track in project.timeline:
            if track.type == "video":
                comp.load_clips(track.clips)
            elif track.type == "zoom":
                comp.load_manual_zoom_clips(track.clips)

        if comp._frames:
            self._create_playback_controller()
            self._playback.seek(0)
            self._connect_timeline_signals()

        self._audio_regions = project.audio_regions[:]
        if self._audio_regions:
            self._update_audio_timeline()

    def _restore_editor_ui(self, comp, project):
        if project.crop_region:
            comp.set_crop(project.crop_region)
            self._crop_active = True
            self._btn_crop.setChecked(True)

        has_frames = len(comp._frames) > 0
        self._btn_export.setEnabled(has_frames)
        self._btn_crop.setEnabled(has_frames)
        self._btn_add_audio.setEnabled(has_frames)
        self._enable_playback_controls(has_frames)
        total = len(comp._frames)
        self._frame_label.setText(f"1 / {max(total, 1)}")

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

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _on_about(self):
        QMessageBox.about(self, "关于 Recordly",
            "Recordly v1.0.4\n\n"
            "开源演示视频录制与编辑工具\n\n"
            "作者：devcxl\n"
            "GitHub：https://github.com/devcxl/recordly")

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
        return Track(type=type_, name=type_, clips=[
            Clip(type=type_, content=content,
                 start=0.0, end=self._timeline.duration),
        ])

    @property
    def timeline_tracks(self) -> list:
        return getattr(self, '_timeline', None) and self._timeline.tracks or []
