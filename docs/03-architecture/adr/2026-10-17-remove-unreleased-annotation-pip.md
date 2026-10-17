# ADR：移除未发布的标注与摄像头画中画脚手架

**日期：** 2026-10-17
**状态：** Accepted
**关联：** 分支 `chore/code-cleanliness`；用户文档 `docs/guide/index.md` 的“当前版本未开放”说明

---

## 背景

仓库中存在一套标注/摄像头画中画实现，但从未接入产品入口：

- `ui/annotation_panel.py::AnnotationSettingsPanel` 没有被任何模块导入，也没有窗口挂载点。
- `core/effects.py` 中的 `WebcamOverlay`、`ImageAnnotationEffect`、`FigureAnnotationEffect`、`BlurAnnotationEffect` 没有生产消费者，也没有对应测试。
- `MainWindow` 里原先的文字/摄像头轨道钩子同样没有菜单或信号连接点。
- 用户指南明确说明“文字标注、箭头、摄像头画中画尚未在当前版本开放”，但 README 功能列表仍将其列为可用能力。

这些代码不是已发布能力的内部实现，而是没有 owner 的未来功能脚手架。保留它们会持续制造错误的可用性预期，并增加重构时的无效表面积。

## 决策

1. 删除 `ui/annotation_panel.py`。
2. 从 `core/effects.py` 删除：
   - `WebcamOverlay`
   - `ImageAnnotationEffect`
   - `FigureAnnotationEffect`
   - `BlurAnnotationEffect`
3. 保留 `TextAnnotationEffect` 与 `Annotation`：它们是当前唯一有测试覆盖的 `Effect` 实现，并作为 `Compositor` 效果插件机制的回归样例；模块文档明确标注“未接入 UI”。
4. 保留 `core/project.py` 中的 `AnnotationRegion`、`FigureData`、`Project.annotations` 与 JSON schema 校验：这些是持久化数据契约，删除会改变项目文件兼容性，超出本次死代码清理范围。
5. 保留 `ui/timeline.py` 的 `text` / `annotation` 轨道颜色：它们属于通用轨道渲染数据，现有项目文件可能包含对应轨道。
6. 同步修正 README 中把标注/画中画列为已发布功能的描述，并更新测试数量。

## 为什么不保留

- 没有生产调用者，唯一消费者是文档或历史测试，删除不改变任何可观察的产品行为。
- 四个效果类各自包含未测试的 OpenCV、base64、箭头几何或模糊合成逻辑，维护成本高于收益。
- 面板与效果类共同构成一条未完成的垂直切片；只保留其中一部分会让后续开发者误以为入口存在于别处。

## 重新引入条件

未来恢复标注或摄像头画中画时，应作为完整功能重新立项，而不是复活散落脚手架：

1. 明确产品入口（菜单/工具栏/轨道）与时间线数据流。
2. 重新实现或恢复对应 `Effect` 类，并接入 `Compositor.register_effect`。
3. 增加端到端测试：UI 创建标注 → 项目保存/加载 → 预览与导出一致。
4. 恢复 README 功能声明与用户指南说明。

## 后果与风险

- 优点：删除约 500 行未接入代码和一个无效 UI 模块；README 与用户指南对功能可用性的描述一致。
- 风险：如果未来计划直接复用旧实现，需要从版本历史恢复；本 ADR 已记录恢复条件。
- 兼容性：`project.json` 中的 `annotations` 字段与校验逻辑保持不变，旧项目仍可正常加载。
- 依赖：`opencv-python-headless` 仍需保留，用于视频帧编解码与屏幕捕获，不因本次删除而移除。
