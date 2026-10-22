"""Admin API tests — read-only endpoints, fake DB/storage, no live services."""

from __future__ import annotations

import logging
import uuid

import pytest
from fastapi.testclient import TestClient

from app import config, db, storage
from app.main import app
from tests.test_auth import VALID_ENV, FakeUserStore
from tests.test_documents import (
    FakeDocStore,
    FakeStorage,
    make_user,
    token_for,
    upload,
)


@pytest.fixture()
def env(monkeypatch: pytest.MonkeyPatch, tmp_path):
    # Never read the real backend/.env in tests.
    monkeypatch.setattr(config, "ENV_FILE", tmp_path / ".env")
    for name in (
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "ADMIN_EMAIL",
        "OPENROUTER_API_KEY",
        "SESSION_EXPIRY_MINUTES",
        "MAX_UPLOAD_BYTES",
        "STORAGE_QUOTA_BYTES",
    ):
        monkeypatch.delenv(name, raising=False)
    for name, value in VALID_ENV.items():
        monkeypatch.setenv(name, value)
    config.get_settings.cache_clear()
    yield monkeypatch
    config.get_settings.cache_clear()


@pytest.fixture()
def world(env):
    users = FakeUserStore()
    docs = FakeDocStore()
    files = FakeStorage()
    for name, target in (
        ("get_user_by_email", users.get_user_by_email),
        ("create_user", users.create_user),
        ("get_user_by_id", users.get_user_by_id),
        ("create_session", users.create_session),
        ("get_session", users.get_session),
        ("delete_session", users.delete_session),
        ("create_document", docs.create_document),
        ("get_document", docs.get_document),
        ("list_documents", docs.list_documents),
        ("update_filename", docs.update_filename),
        ("delete_document", docs.delete_document),
        ("sum_usage_and_count", docs.sum_usage_and_count),
        ("list_users", lambda: list(users.users.values())),
        ("list_documents_admin", lambda: list(docs.docs.values())),
        ("get_document_admin", lambda document_id: docs.docs.get(document_id)),
    ):
        env.setattr(db, name, target)
    env.setattr(storage, "upload_object", files.upload_object)
    env.setattr(storage, "download_object", files.download_object)
    env.setattr(storage, "delete_object", files.delete_object)
    return users, docs, files


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def make_admin(users: FakeUserStore, email: str = "admin@example.com") -> dict:
    user = make_user(users, email)
    user["is_admin"] = True  # fake store keeps the row by reference
    return user


# --- authorization ---


def test_admin_routes_require_authentication(client: TestClient, world) -> None:
    for path in ("/admin/users", "/admin/documents", f"/admin/documents/{uuid.uuid4()}"):
        response = client.get(path)
        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"


def test_admin_routes_reject_authenticated_non_admin(client: TestClient, world) -> None:
    users, _docs, _files = world
    user = make_user(users, "normal@example.com")
    headers = token_for(user)
    for path in ("/admin/users", "/admin/documents", f"/admin/documents/{uuid.uuid4()}"):
        response = client.get(path, headers=headers)
        assert response.status_code == 403
        assert response.json()["detail"] == "Administrator access required"


def test_query_parameter_cannot_escalate_privileges(client: TestClient, world) -> None:
    users, _docs, _files = world
    user = make_user(users, "normal@example.com")
    response = client.get(
        "/admin/users", headers=token_for(user), params={"is_admin": "true"}
    )
    assert response.status_code == 403


def test_admin_status_is_read_from_database_on_every_request(
    client: TestClient, world
) -> None:
    users, _docs, _files = world
    admin = make_admin(users)
    headers = token_for(admin)

    assert client.get("/admin/users", headers=headers).status_code == 200

    admin["is_admin"] = False  # demotion applies immediately to the same session
    assert client.get("/admin/users", headers=headers).status_code == 403

    admin["is_admin"] = True
    assert client.get("/admin/users", headers=headers).status_code == 200


# --- GET /admin/users ---


def test_admin_users_returns_only_safe_fields(client: TestClient, world) -> None:
    users, _docs, _files = world
    admin = make_admin(users)
    registered = make_user(users, "student@example.com")

    response = client.get("/admin/users", headers=token_for(admin))
    assert response.status_code == 200
    body = response.json()
    by_email = {row["email"]: row for row in body}

    assert set(by_email) == {"admin@example.com", "student@example.com"}
    assert by_email["admin@example.com"]["is_admin"] is True
    assert by_email["student@example.com"]["is_admin"] is False
    assert by_email["student@example.com"]["id"] == registered["id"]
    for row in body:
        assert set(row) == {"id", "email", "is_admin", "created_at"}
        assert "password_hash" not in row


# --- GET /admin/documents ---


def test_admin_documents_lists_all_owners_with_email(client: TestClient, world) -> None:
    users, _docs, _files = world
    admin = make_admin(users)
    student = make_user(users, "student@example.com")

    upload(client, token_for(admin), "admin-notes.txt")
    upload(client, token_for(student), "student-report.txt")

    response = client.get("/admin/documents", headers=token_for(admin))
    assert response.status_code == 200
    by_name = {row["filename"]: row for row in response.json()}

    assert set(by_name) == {"admin-notes.txt", "student-report.txt"}
    assert by_name["student-report.txt"]["owner_email"] == "student@example.com"
    assert by_name["student-report.txt"]["user_id"] == student["id"]
    assert set(by_name["student-report.txt"]) == {
        "id", "user_id", "owner_email", "filename", "file_type",
        "file_size_bytes", "created_at", "updated_at",
    }
    assert "storage_path" not in by_name["student-report.txt"]


def test_admin_documents_owner_email_is_null_when_owner_row_is_missing(
    client: TestClient, world
) -> None:
    users, docs, files = world
    admin = make_admin(users)
    orphan = docs.create_document(
        {
            "id": str(uuid.uuid4()),
            "user_id": str(uuid.uuid4()),  # no matching user row
            "filename": "orphan.txt",
            "storage_path": "missing/owner",
            "file_type": "text/plain",
            "file_size_bytes": 5,
        }
    )
    files.upload_object(orphan["storage_path"], b"hello", "text/plain")

    response = client.get("/admin/documents", headers=token_for(admin))
    assert response.status_code == 200
    assert response.json()[0]["owner_email"] is None


# --- GET /admin/documents/{id} ---


def test_admin_download_returns_file_bytes(client: TestClient, world) -> None:
    users, docs, _files = world
    admin = make_admin(users)
    student = make_user(users, "student@example.com")
    created = upload(client, token_for(student), "report.txt", b"hello").json()

    response = client.get(
        f"/admin/documents/{created['id']}", headers=token_for(admin)
    )
    assert response.status_code == 200
    assert response.content == b"hello"
    assert response.headers["content-type"].startswith("text/plain")
    assert 'filename="report.txt"' in response.headers["content-disposition"]


def test_admin_download_returns_404_for_unknown_or_malformed_ids(
    client: TestClient, world
) -> None:
    users, _docs, _files = world
    admin = make_admin(users)
    headers = token_for(admin)

    assert client.get(f"/admin/documents/{uuid.uuid4()}", headers=headers).status_code == 404
    malformed = client.get("/admin/documents/not-a-uuid", headers=headers)
    assert malformed.status_code == 404
    assert malformed.json()["detail"] == "Document not found"


def test_admin_download_writes_audit_log(client: TestClient, world, caplog) -> None:
    users, _docs, _files = world
    admin = make_admin(users)
    student = make_user(users, "student@example.com")
    created = upload(client, token_for(student), "audited.txt").json()

    caplog.set_level(logging.INFO, logger="app.routers.admin")
    response = client.get(
        f"/admin/documents/{created['id']}", headers=token_for(admin)
    )
    assert response.status_code == 200
    message = next(
        record.getMessage()
        for record in caplog.records
        if "admin document download" in record.getMessage()
    )
    assert str(admin["id"]) in message
    assert created["id"] in message
    assert "timestamp_utc=" in message
    assert message.rstrip().endswith("Z")


def test_admin_download_storage_failure_is_a_controlled_500(
    client: TestClient, world
) -> None:
    users, _docs, files = world
    admin = make_admin(users)
    student = make_user(users, "student@example.com")
    created = upload(client, token_for(student), "report.txt").json()
    files.fail_download = True

    response = client.get(
        f"/admin/documents/{created['id']}", headers=token_for(admin)
    )
    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to download document"


def test_failed_admin_download_does_not_write_success_audit_log(
    client: TestClient, world, caplog
) -> None:
    users, _docs, files = world
    admin = make_admin(users)
    student = make_user(users, "student@example.com")
    created = upload(client, token_for(student), "report.txt").json()
    files.fail_download = True

    caplog.set_level(logging.INFO, logger="app.routers.admin")
    response = client.get(
        f"/admin/documents/{created['id']}", headers=token_for(admin)
    )
    assert response.status_code == 500
    assert not any(
        "admin document download" in record.getMessage()
        for record in caplog.records
    )


# --- regression: user routes stay owner-scoped ---


def test_normal_document_routes_remain_owner_scoped(client: TestClient, world) -> None:
    users, _docs, _files = world
    student = make_user(users, "student@example.com")
    other = make_user(users, "other@example.com")
    created = upload(client, token_for(student), "private.txt").json()

    response = client.get(
        f"/documents/{created['id']}", headers=token_for(other)
    )
    assert response.status_code == 404
