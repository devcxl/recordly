# 项目全面审查报告 2026-09-01

> 审查对象：`master @ 0982b37`（v1.3.0 后，issue #141 全部修复完成）
> 审查方法：静态代码扫描 + 依赖/配置交叉核对 + CI 状态核验 + 测试套件实跑
> 测试基线：691 passed / 1 skipped

---

## 一、总体结论

**未发现新的安全问题**。issue #141 的 10 项发现全部修复并经 CI 复验；本次审查确认
subprocess 调用、路径处理、并发、项目加载、临时文件等安全面干净。
剩余问题均为**结构性技术债与小瑕疵**（见第三节），无高风险项。

---

## 二、已验证健康项

| 项目 | 结论 | 证据 |
|------|------|------|
| 版本一致性 | ✅ 全部 1.3.0 | pyproject / recordly.spec CFBundle / debian changelog / PKGBUILD / main.py setApplicationVersion / appdata.xml |
| subprocess 安全 | ✅ 无 shell=True | exporter（ffmpeg Popen/run_async）、audio_capture（ffmpeg）、project_manager（ffmpeg 缩略图）、main_window（ffprobe 时长）全为参数列表 |
| 路径安全 | ✅ | delete_project resolve 守卫、create_project/ProjectSession 消毒 + resolve 校验、缩略图越界拒绝、媒体路径 realpath 校验 |
| 并发 | ✅ 产品代码正确 | #2 锁内快照 / #6 指针锁；8-31 CI 复验（ba8a680）确认跨快照断言差异为测试问题而非产品缺陷 |
| 项目加载 | ✅ | #3 深度类型/范围校验，损坏文件加载即拒绝 |
| 临时文件 | ✅ | #4 run() finally 清理 + 启动清扫 recordly-*.frames |
| 依赖一致性 | ✅ | pyproject / AUR depends / debian Depends 主要运行时依赖对齐（opencv headless vs python-opencv 属打包层差异，均已验证可运行） |
| CI 状态 | ✅ 全绿 | 最近 Test（6m35s）+ Build Packages（2m54s）success；历史失败（8-29）由 ba8a680 修复 |
| 忽略文件 | ✅ | .venv / .test-venv（内部 .gitignore）/ .opencode / .aur/pkg 均正确忽略，无敏感文件入库 |
| 测试 | ✅ | 691 passed / 1 skipped，覆盖录制/合成/导出/命令层/UI/并发回归 |

---

## 三、技术债与小瑕疵（按优先级）

### P2：设计层面

1. **main_window.py 1904 行单类**（issue #141 唯一剩余项，仍在增长）
   录制/播放/导出/裁剪/项目管理/补录/快捷键全在一个类。建议按 app/controllers
   拆分（RecordingController/ExportController/ProjectSession 已有雏形）。

2. **跨模块私有成员访问 6 处**
   - `comp._frames`：app/main_window.py:1770、1774、1795、1810、1815
   - `comp._clips`：app/main_window.py:1153
   - `compositor._frames`：ui/preview_widget.py:426
   `Compositor` 缺少公共只读 API（`frame_count` / `frames` 只读属性）。
   当前实现稳定，风险低，但阻碍后续演进。

### P3：小瑕疵

3. **test.yml 依赖列表与 pyproject 漂移**
   CI 手写 `pip install PyQt5 pynput mss sounddevice Pillow numpy ffmpeg-python
   opencv-python-headless pytest`，缺 `python-xlib` / `future`（conftest mock 了
   pynput 所以测试仍绿）。建议改为 `pip install -e .[test]` 消除漂移。

4. **recorder._screen_session_started 标志语义不清**
   `set_target_fps` 依赖它决定是否重建 screen，但 `stop_recording` 从不重置；
   `start_recording` 总是新建 ScreenCapture 掩盖了该缺陷——属死逻辑，可清理。

5. **CI 耗时 6m35s**
   test.yml 是 3 OS × 2 Python 全矩阵（6 job）。项目为纯桌面客户端，
   可考虑收敛矩阵（如 ubuntu 双版本 + win/mac 单版本）或将 Linux job 作为主验证。

6. **docs/review 累积 6 篇**
   属知识资产（评审/核对记录），无问题；可考虑索引页整理。

---

## 四、已确认无问题（排除项）

- **滤镜图注入**（#1）：compose_audio 内存合成，无用户数据进 filtergraph
- **音量范围**：compose_audio 输入现经 #3 深度校验（volume 0-2）；timeline/inspector 拖动均 clamp [0, 2]
- **ffprobe 路径参数**：无 shell 执行，filepath 来自已校验路径
- **appdata 双 release 条目**：1.3.0 + 1.2.2 正常累积
- **git 历史**：无敏感信息、无大二进制文件入库（.opencode 等已忽略）

---

## 五、建议后续动作（按性价比）

1. `test.yml` 改为 `pip install -e .[test]`（5 分钟，消除依赖漂移）
2. Compositor 补 `frame_count`/`frames` 只读属性（1 小时，清 6 处私有访问）
3. 清理 recorder `_screen_session_started` 死逻辑
4. main_window 拆分：单独排期（高风险大重构，建议分步：先抽音频/项目 restore 段）