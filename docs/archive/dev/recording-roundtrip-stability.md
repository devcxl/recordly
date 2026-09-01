# 开发文档: 新录制项目往返链路稳定性

**Project:** Recordly 核心稳定性与架构治理
**Slug:** recording-roundtrip-stability
**Issue:** #63
**类型:** fullstack
**Batch:** 1
**依赖:** 无

## 1. 目标

保证修复后创建的新录制项目可以完整保存，并在应用重启后正常预览、播放音频和导出。

## 2. 范围

- 修复录制收尾读取 `RecordingController` 的属性错误。
- 保存光标事件时转换为相对录制时间。
- 打开新格式项目时从 `SourceInfo` 指向的 WAV 文件恢复混合音频。
- GIF 导出按用户选择的 FPS 降采样，同时保持原始时长。
- 仅在项目成功加载帧后启用播放、裁剪和导出控件。

不实现现有损坏项目的索引或元数据恢复。

## 3. TDD 行为切片

### 3.1 自动保存

先增加录制收尾回归测试，断言生成 `frames.idx`，并且 `project.json` 包含非空 `source`、正确 `frame_count` 和时间线；随后修复属性访问。

### 3.2 重开音频与光标

增加保存后重新加载测试：WAV 被恢复为 `AudioResult`，光标事件时间戳从零附近开始并随播放推进。实现只读取当前项目声明的音频文件，不猜测旧项目资源。

### 3.3 GIF FPS

增加 FFmpeg 图测试：原始 rawvideo 输入保持 compositor FPS，滤镜按导出 FPS 降采样，输出时长不改变。

### 3.4 控件状态

打开无帧项目时保持播放、裁剪和导出控件禁用；有效项目加载后再启用。

## 4. 验证

```bash
.venv/bin/python -m pytest tests/test_main_window.py tests/test_exporter.py -q
.venv/bin/python -m pytest -q
```

## 5. 风险

- WAV 双轨混合必须保留采样率和声道信息。
- GIF 不能仅修改 FFmpeg 输入帧率，否则会改变输出时长。
- 光标时间基变更只应用于新保存项目；不引入旧项目迁移启发式。
