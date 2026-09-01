"""导出流程 — MainWindow 拆分之四（issue #143 Step 4）

纯搬移自 app/main_window.py（导出对话框/设置构建/进度展示/结果通知）。
共享 MainWindow 实例状态，通过 Mixin 继承链访问。
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QProgressDialog

from core.exporter import ExportSettings
from ui.export_dialog import ExportDialog


class ExportFlowMixin:
    """导出流程控制器。"""

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
        dialog.set_source_size(self._compositor.width, self._compositor.height)
        dialog.set_free_crop(
            self._compositor.crop_region if self._crop_active else None)
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
        if audio:
            settings.samplerate = audio.samplerate

        self._start_export_progress(settings)

    def _build_export_settings(self, dialog) -> ExportSettings:
        is_gif = dialog.export_format == "gif"
        crop_region = dialog.crop_region  # 裁剪决策由导出对话框接管（含 ✂ 自由裁剪）

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
            audio_regions=self._audio_regions if self._audio_regions else None,
            crop_region=crop_region,
            fill_crop_ratio=dialog.fill_crop_ratio,
            use_gpu=dialog.use_gpu,
        )

    def _start_export_progress(self, settings: ExportSettings):
        self._progress = QProgressDialog("正在导出视频...", "取消", 0, 100, self)
        self._progress.setWindowTitle("导出")
        self._progress.setWindowModality(Qt.WindowModal)
        self._progress.setAutoClose(True)
        self._progress.setAutoReset(True)
        self._progress.canceled.connect(self._cancel_export)

        try:
            self._export_controller.start_export(
                self._compositor, settings)
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
