# desktop/tests/test_session.py: Tests for tests.
"""Session persistence tests: tmp paths only, no real %APPDATA% usage."""
import json
import time
from pathlib import Path

from app.session import Session, SessionStore, default_session_path


def make_session(ttl=3600):
    return Session("secret-token", "ana@example.com", time.time() + ttl)


def test_round_trip(tmp_path: Path):
    store = SessionStore(tmp_path / "session.json")
    store.save(make_session())
    loaded = store.load()
    assert loaded is not None
    assert loaded.email == "ana@example.com"
    assert loaded.access_token == "secret-token"


def test_missing_file_returns_none(tmp_path: Path):
    assert SessionStore(tmp_path / "absent.json").load() is None


def test_corrupt_file_returns_none_and_is_tolerated(tmp_path: Path):
    path = tmp_path / "session.json"
    path.write_text("{not json", encoding="utf-8")
    assert SessionStore(path).load() is None
                                                                             


def test_wrong_shape_returns_none(tmp_path: Path):
    path = tmp_path / "session.json"
    path.write_text(json.dumps({"token": "x"}), encoding="utf-8")
    assert SessionStore(path).load() is None


def test_expired_session_is_cleared(tmp_path: Path):
    path = tmp_path / "session.json"
    store = SessionStore(path)
    store.save(make_session(ttl=-10))
    assert store.load() is None
    assert not path.exists()           


def test_clear_removes_file(tmp_path: Path):
    path = tmp_path / "session.json"
    store = SessionStore(path)
    store.save(make_session())
    store.clear()
    store.clear()              
    assert not path.exists()


def test_token_never_in_repr_or_str(tmp_path: Path):
    session = make_session()
    assert "secret-token" not in repr(session)
    assert "secret-token" not in str(session)


def test_atomic_save_leaves_no_temp_files(tmp_path: Path):
    store = SessionStore(tmp_path / "session.json")
    store.save(make_session())
    leftovers = [p for p in tmp_path.iterdir() if p.suffix == ".tmp"]
    assert leftovers == []


def test_default_path_lives_under_appdata(monkeypatch):
    monkeypatch.setenv("APPDATA", r"C:\Users\test\AppData\Roaming")
    path = default_session_path()
    assert path.name == "session.json"
    assert path.parent.name == "AiDigitalLocker"
    assert "AppData" in str(path)
