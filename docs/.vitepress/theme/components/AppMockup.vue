<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    lang?: 'zh' | 'en'
  }>(),
  {
    lang: 'zh',
  }
)

const texts = computed(() => {
  return props.lang === 'en'
    ? {
        title: 'Recordly Editor - demo_showcase.project',
        toolbar: {
          undo: 'Undo',
          redo: 'Redo',
          play: '00:04:18 / 00:12:30',
          crop: 'Crop',
          audio: '+ Audio',
          export: 'Export Video',
        },
        preview: {
          zoomBadge: 'Camera Zoom: 180% (Smooth Focus)',
          cursorBadge: 'Click Ripple + Smoothing Active',
        },
        tracks: {
          video: 'Video Track',
          mic: 'Mic Voiceover (Independent)',
          system: 'System Audio (Stereo)',
          zoom: 'Smart Zoom Focus',
        },
      }
    : {
        title: 'Recordly 编辑器 - 软件演示视频.project',
        toolbar: {
          undo: '撤销',
          redo: '重做',
          play: '00:04:18 / 00:12:30',
          crop: '画面裁剪',
          audio: '+ 添加音频',
          export: '导出视频',
        },
        preview: {
          zoomBadge: '智能镜头缩放：180% 平滑推近',
          cursorBadge: '光标高亮跟随 + 点击波纹激活',
        },
        tracks: {
          video: '视频画面轨',
          mic: '麦克风旁白轨（支持原位补录）',
          system: '电脑系统声音轨（独立立体声）',
          zoom: '镜头智能缩放轨（关键焦点）',
        },
      }
})
</script>

<template>
  <div class="mockup-wrapper">
    <div class="mockup-window">
      <!-- Window Titlebar -->
      <div class="window-titlebar">
        <div class="window-controls">
          <span class="control-dot close"></span>
          <span class="control-dot minimize"></span>
          <span class="control-dot maximize"></span>
        </div>
        <div class="window-title">{{ texts.title }}</div>
        <div class="window-spacer"></div>
      </div>

      <!-- App Toolbar -->
      <div class="window-toolbar">
        <div class="toolbar-left">
          <span class="tool-btn">{{ texts.toolbar.undo }}</span>
          <span class="tool-btn">{{ texts.toolbar.redo }}</span>
          <span class="tool-time">{{ texts.toolbar.play }}</span>
        </div>
        <div class="toolbar-right">
          <span class="tool-btn">{{ texts.toolbar.crop }}</span>
          <span class="tool-btn">{{ texts.toolbar.audio }}</span>
          <span class="tool-btn export-btn">{{ texts.toolbar.export }}</span>
        </div>
      </div>

      <!-- Video Preview Canvas -->
      <div class="preview-canvas">
        <div class="canvas-screen">
          <!-- Mock Cursor & Focus -->
          <div class="mock-focus-box">
            <span class="focus-tag">{{ texts.preview.zoomBadge }}</span>
          </div>
          <div class="mock-cursor-point">
            <div class="cursor-ripple"></div>
            <div class="cursor-arrow"></div>
          </div>
          <div class="canvas-badge-bottom">
            {{ texts.preview.cursorBadge }}
          </div>
        </div>
      </div>

      <!-- Multi-Track Timeline -->
      <div class="timeline-container">
        <!-- Ruler -->
        <div class="timeline-ruler">
          <span>00:00</span>
          <span>00:02</span>
          <span>00:04</span>
          <span>00:06</span>
          <span>00:08</span>
          <span>00:10</span>
          <span>00:12</span>
        </div>

        <!-- Video Track -->
        <div class="track-row">
          <div class="track-label">{{ texts.tracks.video }}</div>
          <div class="track-clips">
            <div class="clip clip-video" style="width: 32%;">Intro.clip</div>
            <div class="clip clip-video" style="width: 48%;">Feature_Demo.clip</div>
            <div class="clip clip-video" style="width: 18%;">Outro.clip</div>
          </div>
        </div>

        <!-- Mic Track -->
        <div class="track-row">
          <div class="track-label">{{ texts.tracks.mic }}</div>
          <div class="track-clips">
            <div class="clip clip-mic" style="width: 32%;">
              <div class="mock-waveform"></div>
            </div>
            <div class="clip clip-mic clip-retake" style="width: 25%;">
              <span>Re-recorded</span>
            </div>
            <div class="clip clip-mic" style="width: 41%;">
              <div class="mock-waveform"></div>
            </div>
          </div>
        </div>

        <!-- System Audio Track -->
        <div class="track-row">
          <div class="track-label">{{ texts.tracks.system }}</div>
          <div class="track-clips">
            <div class="clip clip-system" style="width: 78%;">
              <div class="mock-waveform-alt"></div>
            </div>
          </div>
        </div>

        <!-- Zoom Track -->
        <div class="track-row">
          <div class="track-label">{{ texts.tracks.zoom }}</div>
          <div class="track-clips">
            <div class="clip clip-zoom" style="left: 20%; width: 28%;">
              <span>180% Zoom (Editor Area)</span>
            </div>
            <div class="clip clip-zoom" style="left: 60%; width: 22%;">
              <span>200% Zoom (Code Block)</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.mockup-wrapper {
  margin: 32px 0 48px;
  width: 100%;
}

.mockup-window {
  border-radius: 12px;
  overflow: hidden;
  background: #1e1e24;
  border: 1px solid var(--vp-c-divider);
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.2);
}

.window-titlebar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  background: #141418;
  border-bottom: 1px solid #2a2a32;
}

.window-controls {
  display: flex;
  gap: 8px;
}

.control-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
}

.control-dot.close {
  background: #ff5f56;
}
.control-dot.minimize {
  background: #ffbd2e;
}
.control-dot.maximize {
  background: #27c93f;
}

.window-title {
  font-size: 12px;
  color: #a0a0b0;
  font-family: var(--vp-font-family-mono);
}

.window-spacer {
  width: 52px;
}

.window-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  background: #1a1a20;
  border-bottom: 1px solid #282832;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.tool-btn {
  font-size: 11px;
  padding: 3px 8px;
  background: #282834;
  color: #cfd0df;
  border-radius: 4px;
}

.tool-time {
  font-size: 11px;
  font-family: var(--vp-font-family-mono);
  color: #ff8a80;
  margin-left: 6px;
}

.export-btn {
  background: var(--vp-c-brand-1);
  color: #fff;
  font-weight: 600;
}

.preview-canvas {
  position: relative;
  background: #0f0f13;
  padding: 24px;
  display: flex;
  justify-content: center;
}

.canvas-screen {
  position: relative;
  width: 100%;
  max-width: 720px;
  height: 220px;
  background: radial-gradient(circle at 60% 40%, #2a2a38 0%, #15151c 100%);
  border-radius: 8px;
  border: 1px solid #323242;
  overflow: hidden;
}

.mock-focus-box {
  position: absolute;
  top: 30px;
  left: 25%;
  width: 46%;
  height: 120px;
  border: 2px dashed #409eff;
  background: rgba(64, 158, 255, 0.08);
  border-radius: 6px;
  padding: 6px;
}

.focus-tag {
  font-size: 11px;
  color: #fff;
  background: #409eff;
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: 500;
}

.mock-cursor-point {
  position: absolute;
  top: 90px;
  left: 48%;
}

.cursor-arrow {
  width: 0;
  height: 0;
  border-left: 7px solid transparent;
  border-right: 7px solid transparent;
  border-bottom: 14px solid #fff;
  transform: rotate(-35deg);
  filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.5));
}

.cursor-ripple {
  position: absolute;
  top: -12px;
  left: -12px;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 2px solid #ef5350;
  background: rgba(239, 83, 80, 0.25);
  animation: pulse-ring 2s infinite;
}

@keyframes pulse-ring {
  0% {
    transform: scale(0.6);
    opacity: 1;
  }
  100% {
    transform: scale(1.6);
    opacity: 0;
  }
}

.canvas-badge-bottom {
  position: absolute;
  bottom: 8px;
  right: 12px;
  font-size: 11px;
  color: #9e9ea8;
  background: rgba(0, 0, 0, 0.5);
  padding: 2px 8px;
  border-radius: 4px;
}

.timeline-container {
  background: #18181f;
  padding: 14px 16px;
  border-top: 1px solid #282834;
}

.timeline-ruler {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  color: #666678;
  font-family: var(--vp-font-family-mono);
  margin-bottom: 8px;
  padding: 0 110px 0 140px;
}

.track-row {
  display: flex;
  align-items: center;
  margin-bottom: 6px;
  height: 32px;
}

.track-label {
  width: 140px;
  font-size: 11px;
  color: #9a9ab0;
  flex-shrink: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.track-clips {
  position: relative;
  flex: 1;
  display: flex;
  gap: 4px;
  height: 100%;
  background: #121217;
  border-radius: 4px;
  padding: 3px;
  overflow: hidden;
}

.clip {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 500;
  border-radius: 3px;
  overflow: hidden;
}

.clip-video {
  background: #2b3b55;
  color: #8bb2ff;
  border: 1px solid #3c547a;
}

.clip-mic {
  background: #234433;
  color: #7ee2b0;
  border: 1px solid #34674c;
}

.clip-retake {
  background: #4a3420;
  color: #ffb74d;
  border: 1px solid #7d5733;
}

.clip-system {
  background: #213c4a;
  color: #4dd0e1;
  border: 1px solid #305e75;
}

.clip-zoom {
  position: absolute;
  top: 3px;
  bottom: 3px;
  background: rgba(255, 152, 0, 0.25);
  color: #ffb74d;
  border: 1px solid #ff9800;
}

.mock-waveform {
  width: 80%;
  height: 10px;
  background: repeating-linear-gradient(
    90deg,
    #7ee2b0,
    #7ee2b0 2px,
    transparent 2px,
    transparent 5px
  );
  opacity: 0.7;
}

.mock-waveform-alt {
  width: 80%;
  height: 10px;
  background: repeating-linear-gradient(
    90deg,
    #4dd0e1,
    #4dd0e1 2px,
    transparent 2px,
    transparent 4px
  );
  opacity: 0.7;
}

@media (max-width: 640px) {
  .track-label {
    width: 90px;
    font-size: 10px;
  }
  .timeline-ruler {
    padding: 0 10px 0 90px;
  }
}
</style>
