# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

_SPEC_DIR = Path(SPECPATH).resolve()

_ASSET_BASES = (
    _SPEC_DIR / "assets",
    _SPEC_DIR / "web" / "staticfiles",
)

_datas = []

for _asset_base in _ASSET_BASES:
    if not _asset_base.exists():
        continue

    for _asset_file in _asset_base.rglob("*"):
        if _asset_file.is_file():
            _datas.append((
                str(_asset_file),
                str(_asset_file.relative_to(_SPEC_DIR).parent)
            ))

a = Analysis(
    [str(_SPEC_DIR / "desktop" / "locker.py")],
    pathex=[str(_SPEC_DIR / "desktop")],
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
    name="MyTkinterApp",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)