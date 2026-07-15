# Task: 修复新录制项目往返链路

## 任务信息

- **Slug:** recording-roundtrip-stability
- **类型:** fullstack
- **Batch:** 1

## 依赖

无

## 描述

修复后续新录制项目在自动保存、重新打开、预览播放和导出过程中的回归问题。仅保证修复后创建的新项目，不迁移或恢复现有损坏项目。

## 验收标准

- [ ] 录制完成后生成有效的 `frames.idx` 和完整 `project.json`
- [ ] 新项目重新打开后恢复麦克风和系统音频，预览与 MP4 导出均包含音频
- [ ] 新项目重新打开后光标事件与帧使用同一相对时间基
- [ ] GIF 导出使用用户选择的 FPS，并保持视频时长
- [ ] 缺少有效帧的项目不启用播放和导出控件
- [ ] 新增保存→重开→播放/导出回归测试，全量测试通过

## 不在范围内

- 不扫描、迁移或恢复现有损坏项目
- 不新增旧版 `project.json` 兼容逻辑

## 技术方案参考

- `docs/design/recordly-core-stability.md`
- `docs/adr/007-project-session-recording-export-controllers.md`
- `docs/dev/handoff-2026-07-16.md`
