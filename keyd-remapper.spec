# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['pyinstaller_entry.py'],
    pathex=['backend'],
    binaries=[],
    datas=[('backend', 'backend'), ('frontend', 'frontend')],
    hiddenimports=['uvicorn', 'fastapi', 'keyboard_detector', 'keyd_manager', 'firmware_searcher', 'websocket_monitor'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='keyd-remapper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
