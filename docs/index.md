---
layout: home

hero:
  name: "Recordly"
  text: "专为软件演示与教程打造的录屏剪辑神器"
  tagline: "告别枯燥的原画录屏。光标高亮跟随、镜头智能平滑放大、人声系统音分轨、讲错一键补录。无需复杂专业剪辑，录完即可直接出片。100% 免费开源，隐私数据完全保留在你的电脑上。"
  image:
    src: /logo.svg
    alt: Recordly Logo
  actions:
    - theme: brand
      text: 立即免费下载 (全平台)
      link: "#download"
    - theme: alt
      text: 15 分钟新手教程
      link: /guide/
    - theme: alt
      text: 浏览特色功能
      link: /features
    - theme: alt
      text: GitHub 源码
      link: https://github.com/devcxl/recordly

features:
  - title: 智能镜头推近放大
    details: 观众看不清细小的代码和按钮？在时间线上添加缩放块，画面自动以平滑运镜放大焦点区域，突出关键步骤。
  - title: 影视级光标平滑与涟漪
    details: 告别鼠标狂晃和跳帧。鼠标移动轨迹自动平滑插值，点击自带醒目扩散波纹，操作逻辑一目了然。
  - title: 独立双轨音频与降噪
    details: 麦克风人声与电脑系统声音分开录制，互不干扰。在时间线上自由调整音量比例，不需要的声道一键静音。
  - title: 嘴瓢说错？原地一键补录
    details: 录制完发现某句话没讲好？不用推倒重来。右键时间线上的麦克风片段选择「补录音频」，录完直接原位替换。
  - title: 演示专用的轻量时间线
    details: 裁剪多余废话、片段吸附对齐、0.25x-2.0x 随意变速快进。所有编辑操作均支持无限次撤销与重做。
  - title: 4K 视频与流畅 GIF 预设
    details: 内置 16:9 横屏、9:16 手机竖屏、4:3 以及专为 GitHub README 与博客打造的低体积流畅 GIF 导出。
---

<AppMockup lang="zh" />

<DownloadCards lang="zh" />

## 适合谁使用？

<div class="persona-grid">
  <div class="persona-card">
    <div class="persona-role">开源作者与独立开发者</div>
    <div class="persona-goal">打造吸引眼球的 GitHub 项目门面</div>
    <div class="persona-desc">
      为 GitHub README 快速生成体积小巧、帧率流畅的操作演示 GIF，或为新版本发布录制 1 分钟快速上手视频。
    </div>
  </div>
  <div class="persona-card">
    <div class="persona-role">产品经理与体验设计师</div>
    <div class="persona-goal">告别长篇文字，用视频直观汇报</div>
    <div class="persona-desc">
      快速录制原型交互流程与新功能演示，通过清晰的光标波纹和局部放大，让跨部门沟通和用户反馈高效顺畅。
    </div>
  </div>
  <div class="persona-card">
    <div class="persona-role">技术讲师与教育博主</div>
    <div class="persona-goal">分步骤录制专业编程实操教程</div>
    <div class="persona-desc">
      双音轨录音保证人声与系统音质纯净；说错了随时原位重录旁白；代码细节自动推近放大，学生看课更省心。
    </div>
  </div>
  <div class="persona-card">
    <div class="persona-role">技术支持与项目顾问</div>
    <div class="persona-goal">让客户与团队秒懂排错指引</div>
    <div class="persona-desc">
      不再一张张截图打红圈。录制一段 30 秒的精准操作录像发给客户或同事，问题复现与使用答疑一步解决。
    </div>
  </div>
</div>

## 录完即出片的三步工作流

<div class="workflow-grid">
  <div class="workflow-card">
    <div class="workflow-step">步骤 01</div>
    <div class="workflow-title">开始录制</div>
    <div class="workflow-desc">
      一键启动，窗口自动收起至系统托盘，不遮挡工作区。后台静默同步记录屏幕画面、麦克风旁白、系统音频与高精度鼠标坐标。
    </div>
  </div>
  <div class="workflow-card">
    <div class="workflow-step">步骤 02</div>
    <div class="workflow-title">直观精修</div>
    <div class="workflow-desc">
      停止录制后自动开启编辑器。拖拽裁剪多余的起手动作，为重点代码框选缩放镜头，讲错的语句直接原位补录一段音频。
    </div>
  </div>
  <div class="workflow-card">
    <div class="workflow-step">步骤 03</div>
    <div class="workflow-title">一键导出</div>
    <div class="workflow-desc">
      选择 16:9 横屏、9:16 移动竖屏或动图 GIF，支持 GPU 硬件加速高速渲染，立即分享到官网、文档、B站或社交媒体。
    </div>
  </div>
</div>

## 为什么选择 Recordly？

市场上主流录屏与剪辑工具各有所长，但 Recordly 针对「软件演示」场景做了彻底的剪枝与优化：

<div class="comparison-table-wrapper">
  <table class="comparison-table">
    <thead>
      <tr>
        <th>对比维度</th>
        <th class="highlight-col">Recordly</th>
        <th>OBS Studio</th>
        <th>Screen Studio</th>
        <th>普通系统自带录屏</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>收费模式</td>
        <td class="highlight-col">完全免费 (MIT 开源)</td>
        <td>完全免费 (GPL)</td>
        <td>昂贵的一次性/订阅收费</td>
        <td>免费</td>
      </tr>
      <tr>
        <td>支持平台</td>
        <td class="highlight-col">Windows / macOS / Linux</td>
        <td>Windows / macOS / Linux</td>
        <td>仅限 macOS</td>
        <td>各自系统内置</td>
      </tr>
      <tr>
        <td>剪辑上手门槛</td>
        <td class="highlight-col">专为演示设计，零基础秒上手</td>
        <td>无内置剪辑，需学习剪映/PR</td>
        <td>专为演示设计，上手简单</td>
        <td>无剪辑或仅粗暴截断</td>
      </tr>
      <tr>
        <td>光标美化与点击特效</td>
        <td class="highlight-col">自动平滑跟踪与点击扩散波纹</td>
        <td>需自行寻找并配置插件</td>
        <td>原生自动平滑美化</td>
        <td>无特效，容易看不清</td>
      </tr>
      <tr>
        <td>智能镜头推近缩放</td>
        <td class="highlight-col">拖拽框选，自动平滑镜头过渡</td>
        <td>需复杂图层放大滤镜</td>
        <td>自动点击识别放大</td>
        <td>无，只能原画输出</td>
      </tr>
      <tr>
        <td>双音频分轨与补录</td>
        <td class="highlight-col">人声与系统音分轨，支持原地补录</td>
        <td>调音台支持分轨，无补录</td>
        <td>支持分轨，无自由补录</td>
        <td>通常混成单轨或二选一</td>
      </tr>
      <tr>
        <td>数据与隐私安全</td>
        <td class="highlight-col">100% 离线运行，全部存本地</td>
        <td>本地运行</td>
        <td>本地运行</td>
        <td>本地运行</td>
      </tr>
    </tbody>
  </table>
</div>

## 纯粹、透明、隐私优先

- **零水印与零时间限制**：无论是录制 30 秒的快捷操作，还是录制 2 小时的完整课程，绝不添加强制水印，绝无录制时长限制。
- **100% 离线与隐私保护**：你的录屏、音频和工程文件全部保存在本地 `~/Recordly/projects/` 目录下，绝不向任何云端服务器上传，商业机密与代码完全安全。
- **开源社区驱动**：完全基于开源协议发布，代码透明，欢迎所有人参与使用、反馈建议与共同完善。
