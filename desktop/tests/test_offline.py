"""Offline copy path tests (spec section 11: local copies only, no sync)."""
from pathlib import Path

from app import offline


def test_copy_path_layout(tmp_path: Path):
    target = offline.copy_path("doc-1", "notes.pdf", root=tmp_path)
    assert target == tmp_path / "doc-1" / "notes.pdf"


def test_has_copy_false_then_true(tmp_path: Path):
    assert not offline.has_copy("doc-1", root=tmp_path)
    target = offline.copy_path("doc-1", "notes.pdf", root=tmp_path)
    target.parent.mkdir(parents=True)
    target.write_bytes(b"data")
    assert offline.has_copy("doc-1", root=tmp_path)


def test_missing_dir_is_not_an_error(tmp_path: Path):
    assert offline.has_copy("never-seen", root=tmp_path) is False


def test_status_survives_cloud_rename(tmp_path: Path):
    """Cloud rename changes the filename, not the document id: the local
    copy (keyed by id) must still be reported."""
    target = offline.copy_path("doc-1", "old-name.pdf", root=tmp_path)
    target.parent.mkdir(parents=True)
    target.write_bytes(b"data")
    assert offline.has_copy("doc-1", root=tmp_path)
    # A save under the new cloud name simply adds a second file.
    offline.copy_path("doc-1", "new-name.pdf", root=tmp_path).write_bytes(b"data")
    assert offline.has_copy("doc-1", root=tmp_path)


def test_default_root_is_under_desktop_offline():
    root = offline.offline_root()
    assert root.name == "offline"
    assert root.parent.name == "desktop"
