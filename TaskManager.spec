# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['src/taskmanager/__main__.py'],
    pathex=[],
    binaries=[],
    datas=[('src/taskmanager/ui/styles/app.qss', 'taskmanager/ui/styles'), ('src/taskmanager/resources/app_icon.png', 'taskmanager/resources'), ('src/taskmanager/resources/app_icon.ico', 'taskmanager/resources')],
    hiddenimports=[],
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
    [],
    exclude_binaries=True,
    name='TaskManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['src/taskmanager/resources/app_icon.ico'],
    # Runtime dir beside the loader. Pass --distpath=build/onedir-collect so
    # dist/ stays the GitHub asset only (see scripts/package_github_asset.py).
    contents_directory='data',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='TaskManager-onedir',
)
