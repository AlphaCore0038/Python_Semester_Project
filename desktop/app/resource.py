# desktop/app/resource.py: Asset path resolution for source and packaged PyInstaller runs.
"""Resolve desktop assets in both source and packaged PyInstaller runs."""

from __future__ import annotations

import sys
from pathlib import Path

                                                        
_REPO_ROOT = Path(__file__).resolve().parents[2]

_SOURCE_DIRS = (
    _REPO_ROOT / "assets",
    _REPO_ROOT / "web" / "staticfiles",
)

REQUIRED_ASSETS = (
    "document_lock_logo.png",
    "document_lock_logo.ico",
    "gradient_auth.png",
)


def _meipass() -> Path | None:
    """Return the PyInstaller extraction directory when packaged, else None."""
    meipass = getattr(sys, "_MEIPASS", None)
    return Path(meipass) if meipass else None


def find_asset(name: str) -> Path | None:
    """Return the first existing path for an asset name, or None."""
    candidates: list[Path] = []

    meipass = _meipass()
    if meipass is not None:
        candidates.append(meipass / "assets" / name)
        candidates.append(meipass / "web" / "staticfiles" / name)
        candidates.append(meipass / name)

    candidates.extend(base / name for base in _SOURCE_DIRS)

    for path in candidates:
        try:
            if path.is_file():
                return path
        except OSError:
            continue
    return None


def asset_path(name: str) -> Path:
    """Return the path for a required asset, or raise FileNotFoundError."""
    path = find_asset(name)
    if path is None:
        raise FileNotFoundError(f"Missing required desktop asset: {name}")
    return path
