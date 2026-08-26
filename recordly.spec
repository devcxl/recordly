# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_submodules

# 自动收集易被遗漏的子模块（避免手写 hiddenimports 与上游版本漂移）
auto_hidden = (
    collect_submodules('pynput')
    + collect_submodules('sounddevice')
    + collect_submodules('PIL')
    + collect_submodules('numpy')
    + collect_submodules('Xlib')
    + collect_submodules('cv2')
    + collect_submodules('ffmpeg')
)

# 已知容易被静态分析忽略的模块
static_hidden = [
    'PyQt5.QtCore',
    'PyQt5.QtGui',
    'PyQt5.QtWidgets',
    'PyQt5.sip',
    'json',
]

hiddenimports = sorted(set(auto_hidden + static_hidden))

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
            'CFBundleVersion': '1.2.0',
            'CFBundleShortVersionString': '1.2.0',
            'NSMicrophoneUsageDescription': 'Recordly needs microphone access to record audio.',
            'NSScreenCaptureUsageDescription': 'Recordly needs screen recording permission to record your screen.',
            'NSHighResolutionCapable': 'True',
        },
    )