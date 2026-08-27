# -*- mode: python ; coding: utf-8 -*-
# Windows-only PyInstaller spec
# 与 recordly.spec 的区别：icon 使用 .ico（Windows EXE 必需）
from PyInstaller.utils.hooks import collect_submodules

auto_hidden = (
    collect_submodules('pynput')
    + collect_submodules('sounddevice')
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

hiddenimports = sorted(set(auto_hidden + static_hidden))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('resources/style.qss', 'resources'),
        ('resources/icons/recordly.svg', 'resources/icons'),
    ],
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
    icon='resources/icons/recordly.ico',
)