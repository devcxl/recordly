"""导出对话框 — 画面裁剪集成与输出尺寸预览的 GUI 回归测试。"""


def _make_dialog(qapp):
    from ui.export_dialog import ExportDialog
    return ExportDialog(default_fps=30, default_bitrate="10M")


class TestCropCombo:
    def test_defaults_to_no_crop(self, qapp):
        dialog = _make_dialog(qapp)
        assert dialog.crop_combo.currentText() == "不裁剪"
        assert dialog.fill_crop_ratio is None
        assert dialog.crop_region is None

    def test_free_crop_disabled_without_region(self, qapp):
        dialog = _make_dialog(qapp)
        assert not dialog.crop_combo.model().item(1).isEnabled()

    def test_free_crop_enabled_via_set_free_crop(self, qapp):
        from core.project import CropRegion
        dialog = _make_dialog(qapp)
        dialog.set_free_crop(CropRegion(x=0.1, y=0.2, width=0.5, height=0.6))
        assert dialog.crop_combo.model().item(1).isEnabled()
        assert dialog.crop_combo.currentText() == "自由裁剪 (✂)"

    def test_crop_region_property_returns_free_region(self, qapp):
        from core.project import CropRegion
        dialog = _make_dialog(qapp)
        region = CropRegion(x=0.1, y=0.2, width=0.5, height=0.6)
        dialog.set_free_crop(region)
        assert dialog.crop_region is region
        # 切回不裁剪 → 不再返回自由裁剪区域
        dialog.crop_combo.setCurrentText("不裁剪")
        assert dialog.crop_region is None

    def test_fill_crop_ratio_property(self, qapp):
        dialog = _make_dialog(qapp)
        dialog.crop_combo.setCurrentText("1:1")
        assert dialog.fill_crop_ratio == "1:1"
        assert dialog.crop_region is None
        dialog.crop_combo.setCurrentText("16:9")
        assert dialog.fill_crop_ratio == "16:9"

    def test_native_excluded_from_crop_combo(self, qapp):
        dialog = _make_dialog(qapp)
        texts = [dialog.crop_combo.itemText(i)
                 for i in range(dialog.crop_combo.count())]
        assert "native" not in texts
        assert "不裁剪" in texts
        assert "自由裁剪 (✂)" in texts
        assert "16:9" in texts and "9:16" in texts and "1:1" in texts


class TestSizePreview:
    def test_preview_hidden_without_source(self, qapp):
        dialog = _make_dialog(qapp)
        assert dialog.size_preview.text() == "输出尺寸: -"

    def test_preview_native_source(self, qapp):
        dialog = _make_dialog(qapp)
        dialog.set_source_size(1920, 1080)
        assert dialog.size_preview.text() == "输出尺寸: 1920 × 1080"

    def test_preview_fill_ratio_crops(self, qapp):
        """1920×1080 + 1:1 crop-to-fill → 1080×1080（不拉伸）"""
        dialog = _make_dialog(qapp)
        dialog.set_source_size(1920, 1080)
        dialog.crop_combo.setCurrentText("1:1")
        assert dialog.size_preview.text() == "输出尺寸: 1080 × 1080"

    def test_preview_free_crop_scales(self, qapp):
        """自由裁剪 0.5×1.0 → 宽度减半"""
        from core.project import CropRegion
        dialog = _make_dialog(qapp)
        dialog.set_source_size(1920, 1080)
        dialog.set_free_crop(CropRegion(x=0.25, y=0.0, width=0.5, height=1.0))
        assert dialog.size_preview.text() == "输出尺寸: 960 × 1080"

    def test_preview_respects_resolution_preset(self, qapp):
        dialog = _make_dialog(qapp)
        dialog.set_source_size(3840, 2160)
        dialog.resolution_combo.setCurrentText("1080p (Full HD)")
        assert dialog.size_preview.text() == "输出尺寸: 1920 × 1080"

    def test_preview_respects_custom_resolution(self, qapp):
        dialog = _make_dialog(qapp)
        dialog.set_source_size(3840, 2160)
        dialog.resolution_combo.setCurrentText("自定义...")
        dialog._custom_width.setValue(640)
        dialog._custom_height.setValue(480)
        assert dialog.size_preview.text() == "输出尺寸: 640 × 480"

    def test_preview_clamps_custom_resolution_to_source(self, qapp):
        """自定义分辨率超出源尺寸时 clamp（与 exporter 一致，不放大）"""
        dialog = _make_dialog(qapp)
        dialog.set_source_size(640, 480)
        dialog.resolution_combo.setCurrentText("自定义...")
        dialog._custom_width.setValue(1920)
        dialog._custom_height.setValue(1080)
        assert dialog.size_preview.text() == "输出尺寸: 640 × 480"

    def test_preview_custom_resolution_with_fill_ratio(self, qapp):
        """自定义分辨率 + fill 裁剪组合：clamp 后按比例裁剪"""
        dialog = _make_dialog(qapp)
        dialog.set_source_size(1920, 1080)
        dialog.resolution_combo.setCurrentText("自定义...")
        dialog._custom_width.setValue(800)
        dialog._custom_height.setValue(600)
        dialog.crop_combo.setCurrentText("1:1")
        # fill 区域基于源 1920×1080 → 宽比例 0.5625 → 800×0.5625=450
        assert dialog.size_preview.text() == "输出尺寸: 450 × 600"


def test_cancel_button_is_visually_deemphasized(qapp):
    """取消按钮使用灰色弱化样式，避免视觉引导误触"""
    dialog = _make_dialog(qapp)
    stylesheet = dialog.cancel_btn.styleSheet()
    assert "background-color" in stylesheet
    assert "#d1d5db" in stylesheet  # 灰色背景
    assert dialog.export_btn.styleSheet() == ""  # 主按钮保持默认强调样式


class TestGpuProbeAsync:
    """issue #141 #9：GPU 探测在后台线程执行，不阻塞对话框构造。"""

    def test_dialog_construction_does_not_block(self, monkeypatch):
        """构造立即返回（gpu_check 初始禁用），探测完成后异步回填。"""
        import time
        from ui.export_dialog import ExportDialog

        calls = []

        def slow_probe():
            calls.append(1)
            time.sleep(0.2)
            return True

        monkeypatch.setattr("core.exporter.is_gpu_available", slow_probe)

        t0 = time.monotonic()
        dialog = ExportDialog()
        elapsed = time.monotonic() - t0

        # 构造不等待探测（0.2s 探测 + 毫秒级构造）
        assert elapsed < 0.15, f"构造被探测阻塞: {elapsed:.3f}s"
        assert dialog.gpu_check.isEnabled() is False
        assert calls == [1]  # 探测线程已启动但 UI 未阻塞等待

    def test_gpu_probe_result_updates_checkbox(self, qapp, monkeypatch):
        """探测完成后 gpu_check 启用（经 Qt 跨线程信号回填）。"""
        import time
        from ui.export_dialog import ExportDialog

        monkeypatch.setattr(
            "core.exporter.is_gpu_available", lambda: True)

        dialog = ExportDialog()
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and not dialog.gpu_check.isEnabled():
            qapp.processEvents()
            time.sleep(0.02)

        assert dialog.gpu_check.isEnabled() is True
        assert dialog.gpu_check.toolTip() == ""
