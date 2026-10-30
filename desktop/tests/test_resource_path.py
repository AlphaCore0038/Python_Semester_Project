"""Tests for desktop asset path resolution."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from app.resource import REQUIRED_ASSETS, asset_path, find_asset


def test_required_assets_exist_in_source():
    for name in REQUIRED_ASSETS:
        path = asset_path(name)
        assert path.is_file(), name
        assert path.suffix == Path(name).suffix, name


def test_find_asset_returns_none_for_missing():
    assert find_asset("does-not-exist.png") is None


def test_asset_path_raises_for_missing():
    with pytest.raises(FileNotFoundError):
        asset_path("does-not-exist.png")


def test_asset_path_uses_source_dirs_when_not_packaged(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    path = asset_path("gradient_auth.png")
    assert path.is_file()
    assert path.name == "gradient_auth.png"


def test_resource_path_prefers_meipass_when_available(tmp_path, monkeypatch: pytest.MonkeyPatch):
    meipass = tmp_path / "meipass"
    packaged = meipass / "assets" / "document_lock_logo.png"
    packaged.parent.mkdir(parents=True)
    packaged.write_bytes(b"\x89PNG fake-package")
    object.__setattr__(sys, "_MEIPASS", str(meipass))
    try:
        assert asset_path("document_lock_logo.png") == packaged
    finally:
        try:
            object.__delattr__(sys, "_MEIPASS")
        except AttributeError:
            pass
