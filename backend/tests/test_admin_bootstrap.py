"""Admin bootstrap script tests — all database access is faked."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from scripts import make_admin


def _user(user_id: str = "u-1", email: str = "admin@example.com", is_admin: bool = False):
    return {"id": user_id, "email": email, "is_admin": is_admin}


@pytest.fixture
def fake_db(monkeypatch: pytest.MonkeyPatch):
    state = {"users": {}, "lookups": [], "promotions": []}

    def lookup(email: str):
        state["lookups"].append(email)
        return state["users"].get(email)

    def promote(user_id: str) -> bool:
        state["promotions"].append(user_id)
        return True

    monkeypatch.setattr(make_admin.db, "get_user_by_email", lookup)
    monkeypatch.setattr(make_admin.db, "set_user_admin", promote)
    return state


def test_promotes_existing_account_using_normalized_email(fake_db) -> None:
    fake_db["users"]["admin@example.com"] = _user()
    code, message = make_admin.promote_admin("  ADMIN@Example.COM ")
    assert code == 0
    assert fake_db["lookups"] == ["admin@example.com"]
    assert fake_db["promotions"] == ["u-1"]
    assert "Promoted admin@example.com" in message


def test_existing_admin_is_an_idempotent_noop(fake_db) -> None:
    fake_db["users"]["admin@example.com"] = _user(is_admin=True)
    code, message = make_admin.promote_admin("admin@example.com")
    assert code == 0
    assert fake_db["promotions"] == []
    assert "already an administrator" in message


def test_missing_account_instructs_owner_to_register_first(fake_db) -> None:
    code, message = make_admin.promote_admin("admin@example.com")
    assert code == 1
    assert "Register that account first" in message
    assert fake_db["promotions"] == []


def test_blank_admin_email_is_rejected_before_any_lookup(fake_db) -> None:
    code, message = make_admin.promote_admin("   ")
    assert code == 1
    assert "ADMIN_EMAIL is not set" in message
    assert fake_db["lookups"] == []


def test_invalid_admin_email_is_rejected_before_any_lookup(fake_db) -> None:
    code, message = make_admin.promote_admin("not-an-email")
    assert code == 1
    assert "not a valid email address" in message
    assert fake_db["lookups"] == []


def test_failed_update_is_not_reported_as_success(fake_db, monkeypatch) -> None:
    fake_db["users"]["admin@example.com"] = _user()
    monkeypatch.setattr(make_admin.db, "set_user_admin", lambda user_id: False)
    code, message = make_admin.promote_admin("admin@example.com")
    assert code == 1
    assert "no updated row" in message


def test_main_rejects_arguments_without_loading_settings(monkeypatch, capsys) -> None:
    def fail_if_called():
        raise AssertionError("load_settings must not run when arguments are given")

    monkeypatch.setattr(make_admin, "load_settings", fail_if_called)
    code = make_admin.main(["--email", "someone@example.com"])
    assert code == 1
    assert "takes no arguments" in capsys.readouterr().out


def test_main_reports_configuration_errors_safely(monkeypatch, capsys) -> None:
    def broken_settings():
        raise RuntimeError("Missing required backend configuration: SUPABASE_URL.")

    monkeypatch.setattr(make_admin, "load_settings", broken_settings)
    code = make_admin.main([])
    out = capsys.readouterr().out
    assert code == 1
    assert "Configuration error" in out
    assert "SUPABASE_URL" in out


def test_main_reports_database_failure_without_leaking_details(
    fake_db, monkeypatch, capsys
) -> None:
    def broken_lookup(email: str):
        raise RuntimeError("leaky database detail")

    monkeypatch.setattr(make_admin.db, "get_user_by_email", broken_lookup)
    monkeypatch.setattr(
        make_admin, "load_settings",
        lambda: SimpleNamespace(admin_email="admin@example.com"),
    )
    code = make_admin.main([])
    out = capsys.readouterr().out
    assert code == 1
    assert "Database error (RuntimeError)" in out
    assert "leaky database detail" not in out
