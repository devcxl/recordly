---
id: T5
title: "编辑器快捷键组合根接入与端到端回归"
type: frontend
depends_on:
  - T2
  - T3
  - T4
acceptance:
  - "MainWindow 在创建 Timeline 及设置保存后向其注入与窗口级 QShortcut 相同的 ShortcutRegistry。"
  - "修改时间线键位后立即生效且旧键失效；重启后从 QSettings 恢复，窗口级与时间线级绑定均一致。"
  - "完整定向 offscreen 测试和全量测试通过，git diff --check 无空白错误。"
  - "完成规格 8.2 节手工验收并记录结果；仅切音频不改变导出语义的 R1 风险得到确认。"
files:
  - "app/main_window.py"
  - "tests/test_editor_shortcut_integration.py"
  - "tests/test_main_window.py"
issue_number: 110
---

## 目标

在组合根完成 T2、T3、T4 的共享注册表接线，并以端到端 GUI/持久化回归证明配置立即生效、重启保留且既有编辑器保护不退化。

## 实现边界

- 仅在 MainWindow 组合根将 T3 的共享 `ShortcutRegistry` 注入 T4 Timeline：初始化完成后和 SettingsDialog Accepted、T3 重绑后各执行一次 `set_shortcut_registry()`。
- 不重新实现注册表、设置表格、窗口重绑或时间线动作；集成代码限于调用已有公开契约及必要的回归测试。
- 新增 offscreen 端到端测试：将 X 改为 K，保存后 K 切割且 X 不切割；重新创建 AppConfig/MainWindow 后仍为 K；窗口级动作保持 T3 的安全守卫。
- 执行规格 8.2 节五项手工验收，特别记录 R1：本期验证 Timeline 模型/source/undo/redo，不把普通音频切割扩展到导出语义。

## 验收与验证

1. `QT_QPA_PLATFORM=offscreen pytest -q tests/test_shortcuts.py tests/test_config.py tests/test_settings_dialog.py tests/test_timeline.py tests/test_main_window.py tests/test_editor_shortcut_integration.py` 通过。
2. `QT_QPA_PLATFORM=offscreen pytest -q` 通过。
3. `git diff --check` 通过。
4. 按技术方案 8.2 节记录 video/audio/audio_extra 切割、右段左右拖动、改键重启、冲突/恢复默认和输入框/modal/首页守卫的手工结果。

## Worktree

- 分支：`feat/recordly-editor-usability-integration-regression`
- 仅在 T2、T3、T4 均合入本工作树后开始；不得顺带修改命令层、项目 JSON 或导出实现。

## 预估

3 小时。主要风险是配置对象更新而 Timeline 仍持有旧注册表；测试必须显式断言窗口与 Timeline 使用同一实例。
