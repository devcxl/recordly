---
id: T4
title: "Timeline 配置化快捷键、音频切割与右段拖动回归"
type: frontend
depends_on:
  - T1
acceptance:
  - "TimelineWidget 通过 ShortcutRegistry 路由全部 8 个时间线 action；自定义键生效且默认旧键不再触发，未匹配事件继续交给父类。"
  - "X 对按轨道、片段索引顺序找到的第一个非 zoom 覆盖片段切割，支持 video、audio、audio_extra，边界和 zoom 不切割。"
  - "所有 _split_clip 成功后选中右半段；右段主体可选中并向左或向右拖动，释放后仅入一个 MoveClipCommand，undo/redo 和 source 字段正确。"
  - "nudge_selected() 保留已拆分或变速片段的 source_start/source_end，不修改命令数据结构。"
files:
  - "ui/timeline.py"
  - "tests/test_timeline.py"
issue_number: 109
---

## 目标

将 Timeline 的硬编码键盘分支改为注册表驱动，同时完成音频切割、切割后右段选择/拖动和 nudge source 同步的可回归行为。

## 实现边界

- TimelineWidget 内持有默认 `ShortcutRegistry`，并公开 `set_shortcut_registry(registry)` 以供 T5 注入 MainWindow 的共享对象；组件单独使用时继续使用默认绑定。
- 规范化 `QKeyEvent` 为 PortableText，只匹配 `scope="timeline"` 的 action；映射到已有或提取出的明确行为方法，不将 Timeline 快捷键升级为全局 event filter。
- `_find_playhead_video()` 重命名为 `_find_playhead_clip()`，按轨道、片段索引顺序扫描，跳过 track 或 clip 为 `zoom` 的项，使用严格开区间；无目标提示“播放头下无片段”。
- `_split_clip()` 仅在 `SplitClipCommand` 成功执行后选中 `clip_index + 1`；不改 `_hit_test`、`_hit_edge`、`MoveClipCommand` 或 `SplitClipCommand` 数据结构，也不引入重叠检测。
- 提取 `nudge_selected(delta)`，构造 `MoveClipCommand` 时显式传入 old/new source 字段。

## 协作契约

- `set_shortcut_registry(registry)` 接收 T3 的共享 T1 注册表，不拥有其持久化，也不直接读取 `AppConfig` 或 QSettings。
- T5 负责在 MainWindow 构造及设置保存后调用该 setter；本任务的独立 GUI 测试可直接注入测试注册表。

## 验收与验证

1. 测试覆盖 12 个 timeline 相关默认/自定义路由、焦点边界、无匹配事件透传和已拆分/变速片段 nudge source 不变。
2. 覆盖 video、audio、audio_extra、轨道/片段优先级、zoom 排除、边缘不切、无目标无状态变化、S 切音频及切割 source/undo/redo。
3. 覆盖切割后右段自动选中、主体点击高亮、左右拖动、一次 `MoveClipCommand`、undo/redo 和 source 保持。
4. 执行：`QT_QPA_PLATFORM=offscreen pytest -q tests/test_timeline.py`。

## Worktree

- 分支：`feat/recordly-timeline-configurable-shortcuts`
- 可与 T2/T3 并行，仅依赖 T1；不修改 MainWindow 的组合根连接。

## 预估

4 小时。主要风险是共享边缘被 resize 命中；验收只覆盖右段主体点击，保持已有边缘语义。
