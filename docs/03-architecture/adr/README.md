# 架构决策记录（ADR）

决策历史（不可变）。ADR 一旦合并即冻结，仅允许新增记录并通过显式引用取代旧决策，绝不回头改写。

## 索引

| 文件 | 决策主题 |
|---|---|
| [`005-home-editor-dual-view.md`](005-home-editor-dual-view.md) | ADR-005：双页面架构（首页 + 编辑器） |
| [`006-data-persistence-json.md`](006-data-persistence-json.md) | ADR-006：录制数据持久化到 Project JSON |
| [`007-project-session-recording-export-controllers.md`](007-project-session-recording-export-controllers.md) | ADR-007：ProjectSession + RecordingController + ExportController 架构提取 |
| [`2026-07-13-project-management.md`](2026-07-13-project-management.md) | 项目管理功能架构决策（目录扫描 vs SQLite） |
| [`2026-07-17-timeline-trim-source-sync.md`](2026-07-17-timeline-trim-source-sync.md) | 时间线边缘拖拽 source 同步与宏命令 |
| [`2026-07-19-editor-shortcut-registry.md`](2026-07-19-editor-shortcut-registry.md) | 编辑器快捷键注册表与 QSettings 持久化 |
| [`2026-07-19-playhead-click-behavior.md`](2026-07-19-playhead-click-behavior.md) | 播放头点击行为：事件路由与信号设计 |
| [`2026-07-19-timeline-interaction-routing-and-snapping.md`](2026-07-19-timeline-interaction-routing-and-snapping.md) | 时间线快捷键路由、吸附坐标与缩放块建模 |
| [`2026-07-19-undo-redo-shortcuts.md`](2026-07-19-undo-redo-shortcuts.md) | 撤销/重做快捷键 QShortcut + 命令描述独立于 UI |
| [`2026-08-10-dual-audio-tracks-re-record.md`](2026-08-10-dual-audio-tracks-re-record.md) | 双音频轨道编辑与麦克风补录 |

## 命名说明

- 早期记录沿用 `NNN-<kebab-title>.md` 编号（内部含 ADR-005/006/007）。
- 后续记录以日期前缀命名，正文内含 ADR 编号。
- 按 Cabbage 规范，已合并的 ADR **禁止重命名**；新增决策使用 `ADR-<000N>-<kebab-title>.md` 格式继续编号。