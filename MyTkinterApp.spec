# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

_SPEC_DIR = Path(sys.argv[0]).resolve().parent if getattr(sys, "argv", None) and sys.argv[0] else Path(".").resolve()
_ASSET_BASES = (_SPEC_DIR / "assets", _SPEC_DIR / "web" / "staticfiles")
_datas = []
for _asset_base in _ASSET_BASES:
    for _asset_file in _asset_base.rglob("*"):
        if _asset_file.is_file():
            _datas.append((str(_asset_file), str(_asset_file.relative_to(_SPEC_DIR))))


a = Analysis(
    ['desktop/locker.py'],
    pathex=[],
    binaries=[],
    datas=_datas,
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
    a.binaries,
    a.datas,
    [],
    name='MyTkinterApp',
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
)
