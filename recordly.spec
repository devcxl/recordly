# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_submodules

# pynput 在 Linux 上 import 会连 X server；用 --collect-all 替代 collect_submodules，
# 避免 build 环境无 X server 时 collect 静默失败。
pynput_hidden = [
    'pynput',
    'pynput.mouse',
    'pynput.mouse._xorg',
    'pynput.mouse._base',
    'pynput.mouse._dummy',
    'pynput.keyboard',
    'pynput.keyboard._xorg',
    'pynput.keyboard._base',
    'pynput.keyboard._dummy',
    'pynput._util',
    'pynput._util.xorg',
    'pynput._util.xorg_keysyms',
]

# 自动收集易被遗漏的子模块
auto_hidden = (
    collect_submodules('sounddevice')
    + collect_submodules('PIL')
    + collect_submodules('numpy')
    + collect_submodules('Xlib')
    + collect_submodules('cv2')
    + collect_submodules('ffmpeg')
    # ffmpeg-python 传递依赖：past.builtins.basestring 等
    + collect_submodules('future')
    + collect_submodules('past')
)

static_hidden = [
    'PyQt5.QtCore',
    'PyQt5.QtGui',
    'PyQt5.QtWidgets',
    'PyQt5.sip',
    'json',
    'builtins',  # ffmpeg-python: from builtins import str/object
]

hiddenimports = sorted(set(pynput_hidden + auto_hidden + static_hidden))

datas = [
    ('resources/style.qss', 'resources'),
    ('resources/icons/recordly.svg', 'resources/icons'),
]
if os.path.exists('resources/icons/recordly.icns'):
    datas.append(('resources/icons/recordly.icns', 'resources/icons'))
if os.path.exists('resources/icons/recordly.ico'):
    datas.append(('resources/icons/recordly.ico', 'resources/icons'))

icon_file = None
if sys.platform == 'darwin' and os.path.exists('resources/icons/recordly.icns'):
    icon_file = 'resources/icons/recordly.icns'
elif sys.platform.startswith('linux') and os.path.exists('resources/icons/recordly.svg'):
    icon_file = 'resources/icons/recordly.svg'
elif sys.platform.startswith('win') and os.path.exists('resources/icons/recordly.ico'):
    icon_file = 'resources/icons/recordly.ico'

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'scipy',
        'pandas',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='recordly',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
)

if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='recordly.app',
        icon=icon_file,
        bundle_identifier='io.github.devcxl.recordly',
        info_plist={
            'CFBundleName': 'Recordly',
            'CFBundleDisplayName': 'Recordly',
            'CFBundleIdentifier': 'io.github.devcxl.recordly',
            'CFBundleVersion': '1.3.0',
            'CFBundleShortVersionString': '1.3.0',
            'NSMicrophoneUsageDescription': 'Recordly needs microphone access to record audio.',
            'NSScreenCaptureUsageDescription': 'Recordly needs screen recording permission to record your screen.',
            'NSHighResolutionCapable': 'True',
        },
    )