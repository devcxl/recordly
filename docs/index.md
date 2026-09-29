---
layout: home

hero:
  name: "Recordly"
  text: "开源桌面录屏与演示剪辑工具"
  tagline: "录制、光标特效、双轨音频、时间线剪辑、NVENC 加速导出，一气呵成。"
  image:
    src: /logo.svg
    alt: Recordly Logo
  actions:
    - theme: brand
      text: 立即下载 (全平台)
      link: "#download"
    - theme: alt
      text: 快速上手指南
      link: /guide/
    - theme: alt
      text: 功能特性
      link: /features
    - theme: alt
      text: GitHub 源码
      link: https://github.com/devcxl/recordly

features:
  - title: 屏幕捕获与全局光标追踪
    details: 基于 mss 的低开销屏幕捕获，全局鼠标轨迹采样，支持点击波纹、高亮光环与平滑跟随特效。
  - title: 独立双轨音频与智能混音
    details: 麦克风与系统声音双通道独立采集，支持时间线波形展示、连续音量滑块调节与后期麦克风补录。
  - title: 演示级时间线剪辑
    details: 专为教程与演示视频设计，支持片段拖拽吸附、0.25x-2.0x 变速、智能缩放区域（Zoom Track）与裁剪。
  - title: 硬件加速与多格式导出
    details: 支持 NVIDIA NVENC GPU 硬件编码加速，一键输出 4K/2K/1080p MP4 及高清 GIF，支持画幅比例自由裁切。
  - title: 录制即建项目与工程安全
    details: 独立工程目录保存原始帧数据与音频，project.json 原子化保存，具备崩溃残留自动清理与会话恢复能力。
  - title: 全平台开箱即用
    details: 提供 Arch Linux (.pkg.tar.zst)、Debian/Ubuntu (.deb)、Windows (.exe) 及 macOS (.zip) 原生打包产物。
---

<DownloadCards lang="zh" />

## 核心工作流程

<div class="workflow-grid">
  <div class="workflow-card">
    <div class="workflow-step">步骤 01</div>
    <div class="workflow-title">录制准备</div>
    <div class="workflow-desc">
      启动后点击开始录制，应用自动最小化至托盘。屏幕画面、麦克风旁白与系统声音双轨同步采集，后台记录高精度光标坐标。
    </div>
  </div>
  <div class="workflow-card">
    <div class="workflow-step">步骤 02</div>
    <div class="workflow-title">时间线剪辑</div>
    <div class="workflow-desc">
      录制完成自动唤起编辑器。在多轨时间线中进行裁剪、拆分、吸附对齐、无级调速、音量增益，或为关键操作添加智能缩放框。
    </div>
  </div>
  <div class="workflow-card">
    <div class="workflow-step">步骤 03</div>
    <div class="workflow-title">导出与分享</div>
    <div class="workflow-desc">
      支持 GPU 硬件编码。选择 16:9、9:16、4:3 或自定义画幅，设定分辨率与码率，秒级导出 MP4 演示视频或循环动图 GIF。
    </div>
  </div>
</div>

## 横向对比

Recordly 专注于「录屏即剪辑、快速产出高质量软件演示」，在轻量性、开箱即用性与跨平台自由度上提供均衡的体验：

<div class="comparison-table-wrapper">
  <table class="comparison-table">
    <thead>
      <tr>
        <th>特性维度</th>
        <th class="highlight-col">Recordly</th>
        <th>OBS Studio</th>
        <th>Screen Studio</th>
        <th>Kap</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>开源与协议</td>
        <td class="highlight-col">免费开源 (MIT)</td>
        <td>免费开源 (GPL v2)</td>
        <td>商业闭源收费</td>
        <td>免费开源 (MIT)</td>
      </tr>
      <tr>
        <td>支持操作系统</td>
        <td class="highlight-col">Linux / Windows / macOS</td>
        <td>Linux / Windows / macOS</td>
        <td>仅 macOS</td>
        <td>仅 macOS</td>
      </tr>
      <tr>
        <td>内置时间线编辑器</td>
        <td class="highlight-col">内置时间线 (裁剪/吸附/变速)</td>
        <td>无 (需外部后期剪辑软件)</td>
        <td>内置时间线</td>
        <td>仅基础裁剪</td>
      </tr>
      <tr>
        <td>光标特效与轨迹</td>
        <td class="highlight-col">原生光标追踪与波纹特效</td>
        <td>需配置第三方插件/滤镜</td>
        <td>原生智能平滑</td>
        <td>基础高亮</td>
      </tr>
      <tr>
        <td>双音轨录制与补录</td>
        <td class="highlight-col">原生双音轨 + 时间线补录</td>
        <td>支持高级调音台 (无补录)</td>
        <td>基础双通道</td>
        <td>仅单通道</td>
      </tr>
      <tr>
        <td>智能缩放聚焦</td>
        <td class="highlight-col">Zoom 轨道区域缩放</td>
        <td>需手动配置场景滤镜</td>
        <td>自动点击智能缩放</td>
        <td>无</td>
      </tr>
      <tr>
        <td>工程文件持久化</td>
        <td class="highlight-col">独立项目目录 (project.json)</td>
        <td>仅保存导出视频文件</td>
        <td>专有工程格式</td>
        <td>无工程概念</td>
      </tr>
    </tbody>
  </table>
</div>

## 技术架构

Recordly 基于清晰的分层设计构建，保障录制稳定性与剪辑性能：

- **GUI 控制层 (PyQt5)**：主窗口、多轨时间线、属性 Inspector、工程网格与配置对话框。
- **纯 Python 引擎层 (Core Engine)**：与 Qt 完全解耦，包含屏幕捕获、音频双轨混音、鼠标轨迹采样与崩溃恢复。
- **图像与媒体管线**：基于 Pillow 与 NumPy 实现高性能离线帧处理，通过 FFmpeg 原生封装支持 NVENC GPU 加速。
- **可维护性保障**：项目代码覆盖完整单元测试与集成测试，架构决策均沉淀为不可变 ADR 记录。
