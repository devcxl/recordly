# 技术调研与改造方案：导出坐标一致性

**日期:** 2026-07-16
**状态:** Proposed

## 1. 问题

用户反馈：2K 屏幕录制导出为 1080P 或 720P 后，鼠标轨迹与缩放窗口的位置看起来不准确，并期望鼠标、点击效果和缩放区域随输出分辨率等比例缩小。

## 2. 已证实事实

### 2.1 当前坐标链路

```text
pynput 全局桌面坐标
  → 减去 MSS monitor left/top
  → SourcePx（录制帧坐标）
  → Zoom/Crop 变换
  → 同宽高比路径直接缩放到导出分辨率
  → 在目标坐标系绘制 cursor/click/trail
```

关键实现：

- `core/pointer_tracker.py`：采集全局鼠标坐标。
- `core/screen_capture.py`：通过 MSS 获取 monitor rect 和录制帧。
- `core/compositor.py`：减 `monitor_offset`，执行 zoom/crop，并将坐标缩放到输出尺寸。
- `core/exporter.py`：同宽高比 MP4 直接请求目标尺寸 RGB；其他路径保留 resize fallback。

### 2.2 同宽高比降分辨率没有二次坐标错误

确定性像素标记验证：源画布 `2560×1440`，鼠标位于 `(1920,1080)`。

| 导出尺寸 | 预期位置 | 实际位置 |
|---------|---------|---------|
| 1920×1080 | `(1440,810)` | `(1440,810)` |
| 1280×720 | `(960,540)` | `(960,540)` |

加入 zoom 后，目标点同样正确落在 1080P 的 `(960,540)` 和 720P 的 `(640,360)`。

**结论：不能在 exporter 中再次缩放 cursor events 或 zoom rect。** Compositor 已将画面和效果坐标统一变换到目标坐标系；再次处理会造成双重缩放。

### 2.3 当前测试存在覆盖缺口

全量测试结果：`360 passed, 1 skipped`。现有测试已覆盖目标尺寸 RGB、移动光标串并行逐帧一致性和 MP4 FPS 时长，但仍未覆盖：

- 2K 源坐标到 1080P/720P 成片像素位置；
- Windows 125%/150% DPI；
- 混合 DPI 多显示器；
- CPU/NVENC/GIF 三条导出路径的一致性。

## 3. 待验证根因

### 3.1 首要怀疑：Windows DPI 坐标空间不一致

当前 `main.py` 未在创建 Qt 窗口及初始化 pynput/MSS 前显式设置 Per-Monitor DPI Awareness。

pynput 官方文档指出，Windows 高 DPI 模式下鼠标监听与其他 API 可能处于不同坐标空间。MSS 的 monitor rect 也受进程 DPI Awareness 及初始化顺序影响。Recordly 当前直接使用：

```text
source_x = pynput_global_x - mss_monitor_left
source_y = pynput_global_y - mss_monitor_top
```

该公式只在两者使用同一物理像素坐标空间时成立。若 DPI Awareness 或初始化顺序导致 pynput 与 MSS 落入不同坐标空间，鼠标、自动 zoom 和点击波纹会一起偏移；125%/150% 缩放只是需要重点验证的触发条件，不代表必然出现偏移。

这仍是**待实机验证的首要假设**，不是已确认根因。

参考：

- pynput: <https://pynput.readthedocs.io/en/latest/mouse.html#ensuring-consistent-coordinates-between-listener-and-controller-on-windows>
- Microsoft DPI Awareness: <https://learn.microsoft.com/en-us/windows/win32/hidpi/setting-the-default-dpi-awareness-for-a-process>

### 3.2 独立缺陷：不同宽高比导出会非等比拉伸

当 source aspect ratio 与导出 aspect ratio 不同时，当前 exporter 将完整合成帧直接 resize 到目标尺寸。画面和鼠标仍然相对对齐，但都会被非等比拉伸。这是内容布局缺陷，不是鼠标相对画面的坐标偏移。

### 3.3 次要误差

- zoom 与 crop 连续执行两次 `int()` 截断，第一次误差还可能被后续 crop 比例放大，误差上界取决于 zoom/crop scale。
- `_transform_point()` 会为 viewport 外的鼠标返回负坐标或超界坐标；这是有效的不可见状态，渲染器应裁掉该效果，不能把它吸附到画面边缘。
- `Recorder` 硬编码 `monitor_id=1`，无法保证录制显示器与用户实际操作显示器一致。

## 4. 目标坐标模型

统一定义四个坐标空间：

```text
DesktopPhysicalPx → SourcePx → ViewportPx → OutputPx
```

### 4.1 DesktopPhysicalPx → SourcePx

```text
sx = source_width  / capture_monitor_width
sy = source_height / capture_monitor_height

source_x = (desktop_x - monitor_left) * sx
source_y = (desktop_y - monitor_top)  * sy
```

前提：`desktop_x/y` 与 monitor rect 都在 Per-Monitor DPI Aware 的物理像素空间。

### 4.2 SourcePx → ViewportPx

zoom/crop 合并为一次仿射变换，内部保持 float，最终绘制时再取整：

```text
# 画布 W×H；zoom=(zx,zy,zw,zh)
# crop=(cx,cy,cw,ch)，crop 位于 zoom 后恢复为 W×H 的画布空间
# 没有 zoom 时使用 (0,0,W,H)，没有 crop 时使用 (0,0,W,H)
viewport_left   = zx + cx * zw / W
viewport_top    = zy + cy * zh / H
viewport_width  = zw * cw / W
viewport_height = zh * ch / H

viewport_x = (source_x - viewport_left) * canvas_width  / viewport_width
viewport_y = (source_y - viewport_top)  * canvas_height / viewport_height
```

viewport 矩形本身需要 clamp 到源画布；内容点不 clamp。变换后位于画布外的 cursor、click、trail 直接不绘制。

### 4.3 ViewportPx → OutputPx

默认使用 `fit + letterbox`，禁止非等比 stretch：

```text
scale = min(output_width / canvas_width, output_height / canvas_height)
offset_x = (output_width  - canvas_width  * scale) / 2
offset_y = (output_height - canvas_height * scale) / 2

output_x = viewport_x * scale + offset_x
output_y = viewport_y * scale + offset_y
```

同宽高比导出时 `offset_x = offset_y = 0`。

## 5. 分阶段改造

### Phase A：建立复现与诊断（先做）

目标：确认反馈来自 DPI、显示器选择、异宽高比，还是其他输入。

1. 在 `RECORDLY_DEBUG=1` 时记录一次录制几何信息：
   - OS、DPI Awareness；
   - MSS monitor rect；
   - 首帧实际尺寸；
   - 首个 pynput 坐标；
   - 换算后的 SourcePx；
   - 导出尺寸与 aspect ratio。
2. 增加确定性像素标记回归测试，锁定 2K→1080P/720P。
3. 在 Windows 100%/125%/150% 及混合 DPI 双屏环境复测。

影响范围：

- `core/screen_capture.py`
- `core/recorder.py`
- `tests/test_exporter.py`
- `tests/test_recording_roundtrip.py`

验收：能够用日志明确比较 pointer、monitor rect、source frame 是否处于同一坐标空间。

### Phase B：统一录制输入坐标

仅在 Phase A 证实 DPI/显示器几何不一致后实施。

1. Windows 启动最早期启用 `PER_MONITOR_AWARE_V2`；必须早于 Qt 窗口、pynput listener 和 MSS 实例化。
2. `ScreenCapture` 暴露完整 capture geometry：`left/top/width/height`。
3. 录制结束时把 cursor/click 归一化为 SourcePx，再交给 compositor 与 camera。
4. 新项目持久化 `coordinate_space = "source-pixel-v1"`；SourcePx 项目的 `monitor_offset` 固定为 `(0,0)`。
5. 老项目继续按“全局坐标 + monitor_offset”加载，避免破坏已有项目。
6. 显示器选择不再硬编码 `monitor_id=1`，至少将实际选择写入项目。

影响范围（单批不超过 10 个文件）：

- `main.py`
- `core/screen_capture.py`
- `core/recorder.py`
- `core/project.py`
- `app/main_window.py`
- `tests/test_recorder.py`
- `tests/test_data_persistence.py`
- `tests/test_recording_roundtrip.py`

### Phase C：修复异宽高比输出布局

1. 提取纯函数计算 output viewport。
2. 默认策略采用 `fit + letterbox`，保持全部内容和鼠标形状不失真。
3. `crop-to-fill` 作为后续显式选项，不静默裁剪。
4. CPU、NVENC、GIF 共用同一帧布局函数，删除三处重复 resize 逻辑。
5. `_transform_point()` 使用 float 串联 zoom/crop，最终一次取整；只 clamp viewport/采样矩形，越界 cursor、click、trail 直接裁掉。

影响范围：

- `core/aspect_ratio.py`
- `core/exporter.py`
- `core/compositor.py`
- `tests/test_aspect_ratio.py`
- `tests/test_exporter.py`
- `tests/test_compositor.py`

## 6. 测试矩阵

| 类别 | 场景 | 断言 |
|------|------|------|
| 同宽高比 | 2560×1440 → 1920×1080 | 中心、四角、边缘 marker 与期望误差 ≤1px |
| 同宽高比 | 2560×1440 → 1280×720 | cursor/click/zoom/trail 等比例缩放 |
| Zoom | 2K 源 + 中心/边缘 zoom rect | 焦点位置误差 ≤1px；viewport 外效果被裁掉而非吸附边缘 |
| Crop | zoom + crop 组合 | cursor 与 click 保持重合，累计误差 ≤1px |
| 异宽高比 | 16:9 → 1:1、9:16、4:3 | 无非等比拉伸，letterbox offset 正确 |
| 导出器 | MP4 CPU / NVENC / GIF | 三条路径输出几何一致 |
| DPI | Windows 100%/125%/150% | pointer 与捕获像素位置误差 ≤1px |
| 多屏 | 混合 DPI、负 left/top | monitor-local 坐标正确 |
| 持久化 | 保存→重开→导出 | 新旧 coordinate_space 均保持位置一致 |

## 7. 决策与建议

1. **不要直接修改 exporter 去二次缩放鼠标事件和 zoom rect。** 这会破坏当前正确的同宽高比路径。
2. 先执行 Phase A。没有 Windows 实机几何数据前，不把 DPI 假设写成已确认根因。
3. 若 Phase A 证实 DPI 不一致，优先实施 Phase B；鼠标和 zoom 同时偏移通常说明输入坐标空间有问题。
4. Phase C 是独立质量修复，可以与 DPI 修复分开评审和交付。
