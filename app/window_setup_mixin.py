"""窗口构建与导航 — MainWindow 拆分之一（ADR-007 Step 5）

纯搬移自 app/main_window.py，方法签名与实现体不变。
共享 MainWindow 实例状态，通过 Mixin 继承链访问业务流程方法。
"""

import shutil

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import (
    QColor, QDesktopServices, QIcon, QKeySequence, QPainter, QPixmap,
)
from PyQt5.QtWidgets import (
    QAbstractSpinBox, QAction, QApplication, QComboBox, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QScrollArea,
    QShortcut, QSplitter, QStackedWidget, QStatusBar, QTextEdit,
    QToolBar, QToolButton, QVBoxLayout, QWidget,
)

from app.resources import get_app_icon
from ui.home_page import HomePage
from ui.inspector_panel import InspectorPanel
from ui.preview_widget import PreviewWidget
from ui.timeline import TimelineWidget


class WindowSetupMixin:
    """窗口、编辑器布局、菜单/工具栏/托盘与页面导航。"""

    def _setup_window(self):
        self.setWindowTitle("Recordly v1.0")
        icon = get_app_icon()
        if not icon.isNull():
            self.setWindowIcon(icon)
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
        self._timeline.set_shortcut_registry(self._shortcut_registry)
        self._timeline_scroll = QScrollArea()
        self._timeline_scroll.setWidget(self._timeline)
        self._timeline_scroll.setWidgetResizable(True)
        self._timeline_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._timeline_scroll.setFrameShape(QScrollArea.NoFrame)

        self._inspector = InspectorPanel()

        splitter.addWidget(self._preview)
        splitter.addWidget(self._timeline_scroll)
        splitter.addWidget(self._inspector)
        splitter.setSizes([480, 200, 56])
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)

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
        self._rebind_window_shortcuts()
        self._refresh_undo_redo_state()

    def _rebind_window_shortcuts(self):
        """按当前注册表销毁并重建窗口级快捷键。"""
        for shortcut in getattr(self, "_window_shortcuts", []):
            try:
                shortcut.activated.disconnect()
            except TypeError:
                pass
            shortcut.setEnabled(False)
            shortcut.deleteLater()

        handlers_by_action = {
            "play_pause": self._on_play_toggle,
            "undo": self._on_undo,
            "redo": self._on_redo,
            "redo_alt": self._on_redo,
        }
        actions_by_sequence = {}
        for action in self._shortcut_registry.actions("window"):
            sequence = QKeySequence(
                self._shortcut_registry.binding(action.action_id),
                QKeySequence.PortableText,
            )
            portable_text = sequence.toString(QKeySequence.PortableText)
            if portable_text:
                actions_by_sequence.setdefault(portable_text, []).append(
                    handlers_by_action[action.action_id])

        self._window_shortcuts = []
        for portable_text, handlers in actions_by_sequence.items():
            shortcut = QShortcut(
                QKeySequence(portable_text, QKeySequence.PortableText), self)
            shortcut.setContext(Qt.WindowShortcut)
            shortcut.setAutoRepeat(False)
            shortcut.activated.connect(
                lambda handlers=tuple(handlers): self._dispatch_window_shortcut(
                    handlers))
            self._window_shortcuts.append(shortcut)

    def _dispatch_window_shortcut(self, handlers):
        if not self._is_editor_active_and_safe():
            return
        for handler in handlers:
            handler()

    def _is_editor_active_and_safe(self) -> bool:
        """编辑器在前台且无文本输入焦点时返回 True。
        供所有编辑器级快捷键复用。"""
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
        self._undo_action = QAction(f"撤销\t{self._shortcut_text('undo')}", self)
        self._undo_action.triggered.connect(self._on_undo)
        edit_menu.addAction(self._undo_action)

        self._redo_action = QAction(
            f"重做\t{self._shortcut_text('redo', 'redo_alt')}", self)
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
        self._btn_undo.setToolTip(f"撤销 ({self._shortcut_text('undo')})")
        self._btn_undo.setEnabled(False)
        self._btn_undo.clicked.connect(self._on_undo)

        self._btn_redo = QToolButton()
        self._btn_redo.setText("↪")
        self._btn_redo.setToolTip(
            f"重做 ({self._shortcut_text('redo', 'redo_alt')})")
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
        self._btn_step_fwd.setText("▶")
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

        undo_shortcut = self._shortcut_text("undo")
        redo_shortcut = self._shortcut_text("redo", "redo_alt")

        self._undo_action.setEnabled(can_undo)
        self._undo_action.setText(
            f"撤销 {undo_desc}\t{undo_shortcut}"
            if undo_desc else f"撤销\t{undo_shortcut}")

        self._redo_action.setEnabled(can_redo)
        self._redo_action.setText(
            f"重做 {redo_desc}\t{redo_shortcut}"
            if redo_desc else f"重做\t{redo_shortcut}")

        self._btn_undo.setEnabled(can_undo)
        self._btn_undo.setToolTip(
            f"撤销 {undo_desc} ({undo_shortcut})"
            if undo_desc else f"撤销 ({undo_shortcut})")

        self._btn_redo.setEnabled(can_redo)
        self._btn_redo.setToolTip(
            f"重做 {redo_desc} ({redo_shortcut})"
            if redo_desc else f"重做 ({redo_shortcut})")

    def _shortcut_text(self, *action_ids: str) -> str:
        """返回一个或多个注册表键位的本机显示文本。"""
        return " / ".join(
            QKeySequence(
                self._shortcut_registry.binding(action_id),
                QKeySequence.PortableText,
            ).toString(QKeySequence.NativeText)
            for action_id in action_ids
        )

    def _refresh_home_page(self):
        """刷新首页项目列表"""
        self._home_page.refresh_projects()

    # ── 系统托盘 ──────────────────────────────────────────

    def _setup_tray(self):
        from PyQt5.QtWidgets import QSystemTrayIcon, QMenu

        icon = get_app_icon()
        if icon.isNull():
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
