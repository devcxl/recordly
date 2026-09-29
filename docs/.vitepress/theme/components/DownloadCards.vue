<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'

const props = withDefaults(
  defineProps<{
    lang?: 'zh' | 'en'
  }>(),
  {
    lang: 'zh',
  }
)

type PlatformKey = 'windows' | 'macos' | 'debian' | 'arch' | 'source'

const userPlatform = ref<PlatformKey | 'other'>('windows')
const copiedIndex = ref<string | null>(null)

function detectPlatform(): PlatformKey | 'other' {
  if (typeof navigator === 'undefined') return 'windows'
  const ua = navigator.userAgent.toLowerCase()
  if (ua.includes('win')) return 'windows'
  if (ua.includes('mac')) return 'macos'
  if (ua.includes('arch')) return 'arch'
  if (ua.includes('ubuntu') || ua.includes('debian')) return 'debian'
  if (ua.includes('linux')) return 'debian'
  return 'windows'
}

onMounted(() => {
  userPlatform.value = detectPlatform()
})

const texts = computed(() => {
  return props.lang === 'en'
    ? {
        title: 'Download & Installation',
        subtitle: 'Available for Windows, macOS, Arch Linux, Debian/Ubuntu, and Python source.',
        recommended: 'Recommended for your device',
        copy: 'Copy',
        copied: 'Copied',
        viewAll: 'View all releases on GitHub',
        releaseNote: 'Requires FFmpeg on Linux/macOS/source runs.',
        platforms: {
          windows: {
            name: 'Windows',
            desc: 'Windows 10 / 11 (64-bit)',
            format: 'Standalone Executable',
            actionText: 'Download recordly.exe',
            link: 'https://github.com/devcxl/recordly/releases/latest',
            instruction: 'Download and run recordly.exe directly.',
            type: 'download',
          },
          macos: {
            name: 'macOS',
            desc: 'macOS 12+ (Intel & Apple Silicon)',
            format: 'Zip Archive / App Bundle',
            actionText: 'Download recordly-macos.zip',
            link: 'https://github.com/devcxl/recordly/releases/latest',
            instruction: 'Unzip and drag Recordly.app to /Applications.',
            type: 'download',
          },
          debian: {
            name: 'Debian / Ubuntu',
            desc: 'Debian 11+, Ubuntu 22.04+ (x86_64)',
            format: 'DEB Package',
            actionText: 'Download DEB Package',
            link: 'https://github.com/devcxl/recordly/releases/latest',
            instruction: 'sudo dpkg -i recordly_*.deb',
            type: 'command',
          },
          arch: {
            name: 'Arch Linux',
            desc: 'Arch Linux / Manjaro (x86_64)',
            format: 'Pacman Package (.pkg.tar.zst)',
            actionText: 'Download Pacman Package',
            link: 'https://github.com/devcxl/recordly/releases/latest',
            instruction: 'sudo pacman -U recordly-*.pkg.tar.zst',
            type: 'command',
          },
          source: {
            name: 'Python / Source',
            desc: 'Python 3.10+ & FFmpeg',
            format: 'PIP / Git Repository',
            actionText: 'View Source on GitHub',
            link: 'https://github.com/devcxl/recordly',
            instruction: 'git clone https://github.com/devcxl/recordly.git && cd recordly && pip install -e .',
            type: 'command',
          },
        },
      }
    : {
        title: '下载与安装',
        subtitle: '支持 Windows、macOS、Arch Linux、Debian/Ubuntu 及 Python 源码运行。',
        recommended: '推荐当前系统',
        copy: '复制指令',
        copied: '已复制',
        viewAll: '在 GitHub 查看全部 Releases 历史版本',
        releaseNote: '系统需具备 FFmpeg 运行环境（分发包或系统级安装）。',
        platforms: {
          windows: {
            name: 'Windows',
            desc: 'Windows 10 / 11 (64位)',
            format: '独立绿色可执行程序',
            actionText: '下载 recordly.exe',
            link: 'https://github.com/devcxl/recordly/releases/latest',
            instruction: '下载后直接双击 recordly.exe 运行即可。',
            type: 'download',
          },
          macos: {
            name: 'macOS',
            desc: 'macOS 12+ (Intel 与 Apple Silicon)',
            format: 'ZIP 压缩包 / App',
            actionText: '下载 recordly-macos.zip',
            link: 'https://github.com/devcxl/recordly/releases/latest',
            instruction: '解压后将 Recordly.app 拖入「应用程序」文件夹。',
            type: 'download',
          },
          debian: {
            name: 'Debian / Ubuntu',
            desc: 'Debian 11+ / Ubuntu 22.04+ (x86_64)',
            format: 'DEB 安装包',
            actionText: '下载 DEB 安装包',
            link: 'https://github.com/devcxl/recordly/releases/latest',
            instruction: 'sudo dpkg -i recordly_*.deb',
            type: 'command',
          },
          arch: {
            name: 'Arch Linux',
            desc: 'Arch Linux / Manjaro (x86_64)',
            format: 'Pacman 原生包 (.pkg.tar.zst)',
            actionText: '下载 Pacman 安装包',
            link: 'https://github.com/devcxl/recordly/releases/latest',
            instruction: 'sudo pacman -U recordly-*.pkg.tar.zst',
            type: 'command',
          },
          source: {
            name: '源码运行',
            desc: 'Python 3.10+ 与 FFmpeg 环境',
            format: 'PIP 可编辑安装',
            actionText: '查看 GitHub 源码',
            link: 'https://github.com/devcxl/recordly',
            instruction: 'git clone https://github.com/devcxl/recordly.git && cd recordly && pip install -e .',
            type: 'command',
          },
        },
      }
})

function copyText(key: string, text: string) {
  if (navigator && navigator.clipboard) {
    navigator.clipboard.writeText(text).then(() => {
      copiedIndex.value = key
      setTimeout(() => {
        copiedIndex.value = null
      }, 2000)
    })
  }
}
</script>

<template>
  <div class="download-container" id="download">
    <div class="download-header">
      <h2 class="download-title">{{ texts.title }}</h2>
      <p class="download-subtitle">{{ texts.subtitle }}</p>
    </div>

    <div class="cards-grid">
      <!-- Windows Card -->
      <div
        class="platform-card"
        :class="{ 'card-recommended': userPlatform === 'windows' }"
      >
        <div class="card-badge" v-if="userPlatform === 'windows'">
          {{ texts.recommended }}
        </div>
        <div class="card-top">
          <div class="platform-icon">WIN</div>
          <div>
            <div class="platform-name">{{ texts.platforms.windows.name }}</div>
            <div class="platform-desc">{{ texts.platforms.windows.desc }}</div>
          </div>
        </div>
        <div class="platform-format">{{ texts.platforms.windows.format }}</div>
        <div class="card-instruction">{{ texts.platforms.windows.instruction }}</div>
        <div class="card-actions">
          <a
            class="btn-primary"
            :href="texts.platforms.windows.link"
            target="_blank"
            rel="noreferrer"
          >
            {{ texts.platforms.windows.actionText }}
          </a>
        </div>
      </div>

      <!-- macOS Card -->
      <div
        class="platform-card"
        :class="{ 'card-recommended': userPlatform === 'macos' }"
      >
        <div class="card-badge" v-if="userPlatform === 'macos'">
          {{ texts.recommended }}
        </div>
        <div class="card-top">
          <div class="platform-icon">MAC</div>
          <div>
            <div class="platform-name">{{ texts.platforms.macos.name }}</div>
            <div class="platform-desc">{{ texts.platforms.macos.desc }}</div>
          </div>
        </div>
        <div class="platform-format">{{ texts.platforms.macos.format }}</div>
        <div class="card-instruction">{{ texts.platforms.macos.instruction }}</div>
        <div class="card-actions">
          <a
            class="btn-primary"
            :href="texts.platforms.macos.link"
            target="_blank"
            rel="noreferrer"
          >
            {{ texts.platforms.macos.actionText }}
          </a>
        </div>
      </div>

      <!-- Debian / Ubuntu Card -->
      <div
        class="platform-card"
        :class="{ 'card-recommended': userPlatform === 'debian' }"
      >
        <div class="card-badge" v-if="userPlatform === 'debian'">
          {{ texts.recommended }}
        </div>
        <div class="card-top">
          <div class="platform-icon">DEB</div>
          <div>
            <div class="platform-name">{{ texts.platforms.debian.name }}</div>
            <div class="platform-desc">{{ texts.platforms.debian.desc }}</div>
          </div>
        </div>
        <div class="platform-format">{{ texts.platforms.debian.format }}</div>
        <div class="code-box">
          <code>{{ texts.platforms.debian.instruction }}</code>
          <button
            class="btn-copy"
            @click="copyText('deb', texts.platforms.debian.instruction)"
          >
            {{ copiedIndex === 'deb' ? texts.copied : texts.copy }}
          </button>
        </div>
        <div class="card-actions">
          <a
            class="btn-secondary"
            :href="texts.platforms.debian.link"
            target="_blank"
            rel="noreferrer"
          >
            {{ texts.platforms.debian.actionText }}
          </a>
        </div>
      </div>

      <!-- Arch Linux Card -->
      <div
        class="platform-card"
        :class="{ 'card-recommended': userPlatform === 'arch' }"
      >
        <div class="card-badge" v-if="userPlatform === 'arch'">
          {{ texts.recommended }}
        </div>
        <div class="card-top">
          <div class="platform-icon">ARCH</div>
          <div>
            <div class="platform-name">{{ texts.platforms.arch.name }}</div>
            <div class="platform-desc">{{ texts.platforms.arch.desc }}</div>
          </div>
        </div>
        <div class="platform-format">{{ texts.platforms.arch.format }}</div>
        <div class="code-box">
          <code>{{ texts.platforms.arch.instruction }}</code>
          <button
            class="btn-copy"
            @click="copyText('arch', texts.platforms.arch.instruction)"
          >
            {{ copiedIndex === 'arch' ? texts.copied : texts.copy }}
          </button>
        </div>
        <div class="card-actions">
          <a
            class="btn-secondary"
            :href="texts.platforms.arch.link"
            target="_blank"
            rel="noreferrer"
          >
            {{ texts.platforms.arch.actionText }}
          </a>
        </div>
      </div>

      <!-- Source Run Card -->
      <div class="platform-card card-source">
        <div class="card-top">
          <div class="platform-icon">PY</div>
          <div>
            <div class="platform-name">{{ texts.platforms.source.name }}</div>
            <div class="platform-desc">{{ texts.platforms.source.desc }}</div>
          </div>
        </div>
        <div class="platform-format">{{ texts.platforms.source.format }}</div>
        <div class="code-box">
          <code>{{ texts.platforms.source.instruction }}</code>
          <button
            class="btn-copy"
            @click="copyText('source', texts.platforms.source.instruction)"
          >
            {{ copiedIndex === 'source' ? texts.copied : texts.copy }}
          </button>
        </div>
        <div class="card-actions">
          <a
            class="btn-secondary"
            :href="texts.platforms.source.link"
            target="_blank"
            rel="noreferrer"
          >
            {{ texts.platforms.source.actionText }}
          </a>
        </div>
      </div>
    </div>

    <div class="download-footer">
      <p class="download-note">{{ texts.releaseNote }}</p>
      <a
        class="link-all-releases"
        href="https://github.com/devcxl/recordly/releases"
        target="_blank"
        rel="noreferrer"
      >
        {{ texts.viewAll }} &rarr;
      </a>
    </div>
  </div>
</template>

<style scoped>
.download-container {
  margin: 48px 0 24px;
  padding: 32px 24px;
  border-radius: 12px;
  background: var(--vp-c-bg-soft);
  border: 1px solid var(--vp-c-divider);
}

.download-header {
  text-align: center;
  margin-bottom: 28px;
}

.download-title {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  color: var(--vp-c-text-1);
  border-top: none;
  padding-top: 0;
}

.download-subtitle {
  margin: 8px 0 0;
  font-size: 14px;
  color: var(--vp-c-text-2);
}

.cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
}

.platform-card {
  position: relative;
  display: flex;
  flex-direction: column;
  padding: 20px;
  background: var(--vp-c-bg);
  border: 1px solid var(--vp-c-divider);
  border-radius: 8px;
  transition: border-color 0.25s, box-shadow 0.25s, transform 0.2s;
}

.platform-card:hover {
  border-color: var(--vp-c-brand-1);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
  transform: translateY(-2px);
}

.card-recommended {
  border-color: var(--vp-c-brand-1);
  box-shadow: 0 0 0 1px var(--vp-c-brand-1);
}

.card-badge {
  position: absolute;
  top: -10px;
  right: 12px;
  background: var(--vp-c-brand-1);
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 12px;
  letter-spacing: 0.5px;
}

.card-top {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.platform-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: 8px;
  background: var(--vp-c-bg-mute);
  font-size: 13px;
  font-weight: 700;
  color: var(--vp-c-brand-1);
  border: 1px solid var(--vp-c-divider);
}

.platform-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--vp-c-text-1);
}

.platform-desc {
  font-size: 12px;
  color: var(--vp-c-text-2);
}

.platform-format {
  font-size: 12px;
  color: var(--vp-c-brand-2);
  margin-bottom: 12px;
  font-family: var(--vp-font-family-mono);
}

.card-instruction {
  font-size: 13px;
  color: var(--vp-c-text-2);
  margin-bottom: 16px;
  flex: 1;
}

.code-box {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--vp-c-bg-alt);
  padding: 8px 10px;
  border-radius: 6px;
  border: 1px solid var(--vp-c-divider);
  margin-bottom: 14px;
  overflow: hidden;
  gap: 8px;
}

.code-box code {
  font-size: 12px;
  color: var(--vp-c-text-1);
  font-family: var(--vp-font-family-mono);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.btn-copy {
  flex-shrink: 0;
  font-size: 11px;
  padding: 3px 8px;
  border-radius: 4px;
  border: 1px solid var(--vp-c-divider);
  background: var(--vp-c-bg);
  color: var(--vp-c-text-2);
  cursor: pointer;
  transition: all 0.2s;
}

.btn-copy:hover {
  border-color: var(--vp-c-brand-1);
  color: var(--vp-c-brand-1);
}

.card-actions {
  margin-top: auto;
}

.btn-primary {
  display: block;
  text-align: center;
  padding: 10px 16px;
  border-radius: 6px;
  background: var(--vp-c-brand-1);
  color: #fff !important;
  font-size: 13px;
  font-weight: 600;
  text-decoration: none !important;
  transition: background 0.2s;
}

.btn-primary:hover {
  background: var(--vp-c-brand-2);
}

.btn-secondary {
  display: block;
  text-align: center;
  padding: 8px 16px;
  border-radius: 6px;
  border: 1px solid var(--vp-c-divider);
  background: var(--vp-c-bg-mute);
  color: var(--vp-c-text-1) !important;
  font-size: 13px;
  font-weight: 500;
  text-decoration: none !important;
  transition: border-color 0.2s, color 0.2s;
}

.btn-secondary:hover {
  border-color: var(--vp-c-brand-1);
  color: var(--vp-c-brand-1) !important;
}

.download-footer {
  margin-top: 24px;
  text-align: center;
  font-size: 13px;
  color: var(--vp-c-text-2);
}

.download-note {
  margin-bottom: 6px;
}

.link-all-releases {
  font-weight: 500;
  color: var(--vp-c-brand-1);
}

@media (max-width: 640px) {
  .download-container {
    padding: 20px 16px;
  }
  .cards-grid {
    grid-template-columns: 1fr;
  }
}
</style>
