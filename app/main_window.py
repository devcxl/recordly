"""Recordly 主窗口"""

from PyQt5.QtWidgets import (
    QMainWindow, QToolBar, QAction, QMenuBar,
    QStatusBar, QLabel, QVBoxLayout, QWidget,
    QDockWidget, QListWidget, QApplication, QFileDialog,
    QMessageBox, QProgressDialog, QSystemTrayIcon, QMenu,
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QKeySequence, QPixmap, QIcon, QPainter, QColor

from app.config import AppConfig
from app.constants import DEFAULT_FPS
from core.recorder import Recorder
from core.compositor import Compositor
from core.exporter import Exporter, ExportSettings
from ui.preview_widget import PreviewWidget


class MainWindow(QMainWindow):
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
        self._exporter = Exporter(self)
        self._recorded_data = None
        self._setup_window()
        self._setup_menus()
        self._setup_toolbar()
        self._setup_central()
        self._setup_docks()
        self._setup_statusbar()
        self._setup_signals()
        self._setup_tray()
        self._check_deps()
        self._update_ui_state()

    # ── 窗口 ──────────────────────────────────────────────

    def _setup_window(self):
        self.setWindowTitle("Recordly v1.0")
        self.resize(1280, 800)
        self._center()

    def _center(self):
        screen = QApplication.primaryScreen().geometry()
        self.move(
            (screen.width() - self.width()) // 2,
            (screen.height() - self.height()) // 2,
        )

    DEPENDENCIES: list[dict] = [
        {"name": "FFmpeg", "cmd": "ffmpeg", "hint": "请安装 FFmpeg: https://ffmpeg.org/download.html"},
    ]

    def _check_deps(self):
        """启动时检查系统依赖"""
        import shutil
        missing = [d for d in self.DEPENDENCIES if not shutil.which(d["cmd"])]
        if not missing:
            return
        msgs = "\n".join(f"  • {d['name']}: {d['hint']}" for d in missing)
        QMessageBox.warning(self, "缺少系统依赖",
                            f"以下依赖未安装，部分功能不可用:\n\n{msgs}")

    # ── 菜单 ──────────────────────────────────────────────

    def _setup_menus(self):
        mb = self.menuBar()

        # 文件
        fm = mb.addMenu("文件(&F)")
        def _act(t, s, cb):
            a = QAction(t, self)
            if s:
                a.setShortcut(s)
            a.triggered.connect(cb)
            return a
        fm.addAction(_act("新建项目", QKeySequence.New, self._on_new_project))
        fm.addAction(_act("打开项目", QKeySequence.Open, self._on_open_project))
        fm.addAction(_act("保存项目", QKeySequence.Save, self._on_save_project))
        fm.addSeparator()
        fm.addAction(_act("退出", QKeySequence.Quit, self.close))

        # 录制
        rm = mb.addMenu("录制(&R)")
        self._act_record = _act("开始录制", "Ctrl+R", self._toggle_record)
        self._act_stop = _act("停止录制", "Ctrl+Shift+R", self._toggle_record)
        self._act_stop.setEnabled(False)
        rm.addActions([self._act_record, self._act_stop])

        # 编辑
        em = mb.addMenu("编辑(&E)")
        self._act_undo = _act("撤销", QKeySequence.Undo, self._on_undo)
        self._act_redo = _act("重做", QKeySequence.Redo, self._on_redo)
        em.addActions([self._act_undo, self._act_redo])

        # 轨道
        tm = mb.addMenu("轨道(&T)")
        tm.addAction(_act("添加文字标注", None, self._on_add_text_track))
        tm.addAction(_act("添加画中画", None, self._on_add_camera_track))
        tm.addSeparator()
        tm.addAction(_act("删除选中轨道", "Delete", self._on_delete_selected_track))

        # 视图
        vm = mb.addMenu("视图(&V)")
        vm.addAction(_act("全屏切换", "F11", self._toggle_fullscreen))

        # 帮助
        hm = mb.addMenu("帮助(&H)")
        hm.addAction(_act("关于 Recordly", None, self._on_about))

    def _on_new_project(self):
        self.update_status("新建项目...")

    def _on_open_project(self):
        self.update_status("打开项目...")

    def _on_save_project(self):
        self.update_status("保存项目...")

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _on_about(self):
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.about(self, "关于 Recordly",
            "Recordly v1.0\n\n开源演示视频录制与编辑工具\n\n基于 PyQt5 + FFmpeg")

    def _on_undo(self):
        if hasattr(self, '_timeline'):
            self._timeline.undo()

    def _on_redo(self):
        if hasattr(self, '_timeline'):
            self._timeline.redo()

    # ── 轨道操作 ─────────────────────────────────────────

    def _on_add_text_track(self):
        """添加文字标注轨道"""
        from PyQt5.QtWidgets import QInputDialog
        text, ok = QInputDialog.getText(self, "添加文字标注", "输入标注内容:")
        if not ok or not text:
            return
        track = self._make_track("text", text)
        self._timeline.tracks.append(track)
        self._timeline.update()

    def _on_add_camera_track(self):
        """添加画中画轨道"""
        from PyQt5.QtWidgets import QInputDialog
        device, ok = QInputDialog.getText(self, "添加画中画", "摄像头设备号 (默认 0):", text="0")
        if not ok:
            return
        track = self._make_track("camera", device or "0")
        self._timeline.tracks.append(track)
        self._timeline.update()

    def _on_delete_selected_track(self):
        """删除时间线选中的轨道"""
        idx = self._timeline.selected_index
        if idx >= 0:
            self._timeline.delete_track(idx)

    def _make_track(self, type_: str, content: str):
        """创建一个默认时间范围的轨道"""
        from core.project import Track
        return Track(type=type_, content=content, start=0.0, end=self._timeline.duration)

    @property
    def timeline_tracks(self) -> list:
        """导出用的活动轨道列表"""
        return getattr(self, '_timeline', None) and self._timeline.tracks or []

    # ── 系统托盘 ──────────────────────────────────────────

    def _setup_tray(self):
        """初始化系统托盘图标"""
        # 程序化生成简单图标（无需外部文件）
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
        menu.addAction("显示窗口", self.showNormal)
        menu.addAction("退出", QApplication.quit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.showNormal()
            self.raise_()

    # ── 工具栏 ────────────────────────────────────────────

    def _setup_toolbar(self):
        tb = QToolBar("主工具栏")
        tb.setMovable(False)
        self.addToolBar(tb)

        self._btn_record = QAction("⬤ 录制", self)
        self._btn_stop = QAction("■ 停止", self)
        self._btn_preview = QAction("▶ 预览", self)
        self._btn_export = QAction("⏏ 导出", self)

        self._btn_record.triggered.connect(self._toggle_record)
        self._btn_stop.triggered.connect(self._toggle_record)
        self._btn_export.triggered.connect(self._on_export)

        self._btn_stop.setEnabled(False)
        self._btn_preview.setEnabled(False)
        self._btn_export.setEnabled(False)

        tb.addActions([
            self._btn_record, self._btn_stop,
            self._btn_preview, self._btn_export,
        ])

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
        self.update_status("⬤ 录制中...")

    def _on_recording_stopped(self):
        self._recorded_data = self._recorder.stop_recording()
        if self._recorded_data and self._recorded_data.get("frames"):
            self._compositor.load_frames(self._recorded_data["frames"])
            self._btn_preview.setEnabled(True)
            self._btn_export.setEnabled(True)
        self.update_status("⬤ 录制完成")

    def _on_export(self):
        path, fmt = QFileDialog.getSaveFileName(
            self, "导出视频", self.config.recordings_dir,
            "MP4 (*.mp4);;GIF (*.gif)")
        if not path:
            return
        is_gif = path.lower().endswith(".gif")
        settings = ExportSettings(
            output_path=path,
            format="gif" if is_gif else "mp4",
            fps=self.config.default_fps,
            bitrate=self.config.default_bitrate,
        )
        self.update_status("⏏ 正在导出...")
        self._btn_export.setEnabled(False)

        audio = self._recorded_data.get("audio")
        audio_data = audio.data if audio else None

        if is_gif:
            self._exporter.export_gif(self._compositor, settings)
        else:
            self._exporter.export_mp4(self._compositor, audio_data, settings)

    def _on_export_finished(self, result):
        self._btn_export.setEnabled(True)
        if result.success:
            self.update_status(f"✅ 导出完成: {result.path} "
                               f"({result.size_bytes/1024/1024:.1f}MB)")
            QMessageBox.information(self, "导出完成",
                f"视频已保存到:\n{result.path}")
        else:
            self.update_status(f"❌ 导出失败: {result.error}")
            QMessageBox.warning(self, "导出失败", result.error or "未知错误")

    # ── 中央区域 ──────────────────────────────────────────

    def _setup_central(self):
        from PyQt5.QtWidgets import QVBoxLayout, QSplitter
        from ui.timeline import TimelineWidget

        self._preview = PreviewWidget()
        self._preview.setMinimumSize(640, 480)
        self._timeline = TimelineWidget()

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self._preview)
        splitter.addWidget(self._timeline)
        splitter.setSizes([480, 200])
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)

        # 确保时间线可接收键盘事件
        self._timeline.setFocusPolicy(Qt.StrongFocus)

    # ── 侧面板 ────────────────────────────────────────────

    def _setup_docks(self):
        dock = QDockWidget("项目文件", self)
        dock.setWidget(QListWidget())
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)

    # ── 状态栏 ────────────────────────────────────────────

    def _setup_statusbar(self):
        self._status_label = QLabel("⬤ 准备就绪")
        self.statusBar().addWidget(self._status_label)

    def _setup_signals(self):
        self.recording_started.connect(self._on_recording_started)
        self.recording_stopped.connect(self._on_recording_stopped)
        self._exporter.finished.connect(self._on_export_finished)

    # ── 状态更新 ──────────────────────────────────────────

    def _update_ui_state(self):
        rec = self._is_recording
        self._btn_record.setEnabled(not rec)
        self._btn_stop.setEnabled(rec)
        self._btn_preview.setEnabled(False)
        self._btn_export.setEnabled(not rec)
        self._act_record.setEnabled(not rec)
        self._act_stop.setEnabled(rec)
        self.update_status("● 录制中..." if rec else "● 准备就绪")

    def set_recording_state(self, recording: bool):
        self._is_recording = recording
        self._update_ui_state()

    def update_status(self, text: str):
        self._status_label.setText(text)

    def show_preview(self, pixmap: QPixmap):
        self.preview_label.setPixmap(pixmap)
        self.preview_label.setText("")
