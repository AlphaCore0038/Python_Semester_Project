"""Documents API tests — in-memory fake DB and storage; no real Supabase."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import config, db, storage
from app.main import app
from app.security import hash_password, hash_session_token
from tests.test_auth import VALID_ENV, FakeUserStore


class FakeDocStore:
    def __init__(self) -> None:
        self.docs: dict[str, dict] = {}

    def create_document(self, row: dict) -> dict:
        doc = dict(row)
        doc.setdefault("created_at", "2026-10-20T00:00:00+00:00")
        doc.setdefault("updated_at", "2026-10-20T00:00:00+00:00")
        self.docs[doc["id"]] = doc
        return doc

    def get_document(self, document_id: str, user_id: str) -> dict | None:
        doc = self.docs.get(document_id)
        if doc and doc["user_id"] == user_id:
            return doc
        return None

    def list_documents(
        self,
        user_id: str,
        *,
        search: str | None = None,
        sort: str = "created_at",
        order: str = "desc",
        file_type: str | None = None,
    ) -> list[dict]:
        rows = [d for d in self.docs.values() if d["user_id"] == user_id]
        if search:
            needle = search.lower()
            rows = [r for r in rows if needle in r["filename"].lower()]
        if file_type:
            rows = [r for r in rows if r["file_type"] == file_type]
        rows.sort(key=lambda r: r[sort], reverse=(order == "desc"))
        return rows

    def update_filename(self, document_id: str, user_id: str, filename: str) -> dict | None:
        doc = self.get_document(document_id, user_id)
        if doc is None:
            return None
        doc["filename"] = filename
        doc["updated_at"] = "2026-10-21T00:00:00+00:00"
        return doc

    def delete_document(self, document_id: str, user_id: str) -> bool:
        doc = self.get_document(document_id, user_id)
        if doc is None:
            return False
        del self.docs[document_id]
        return True

    def sum_usage_and_count(self, user_id: str) -> tuple[int, int]:
        rows = [d for d in self.docs.values() if d["user_id"] == user_id]
        return sum(d["file_size_bytes"] for d in rows), len(rows)


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.fail_upload = False
        self.fail_download = False
        self.fail_delete = False
        self.delete_calls: list[str] = []

    def upload_object(self, path: str, data: bytes, content_type: str) -> None:
        if self.fail_upload:
            raise RuntimeError("storage down")
        self.objects[path] = (data, content_type)

    def download_object(self, path: str) -> bytes:
        if self.fail_download or path not in self.objects:
            raise RuntimeError("storage down")
        return self.objects[path][0]

    def delete_object(self, path: str) -> None:
        self.delete_calls.append(path)
        if self.fail_delete:
            raise RuntimeError("storage down")
        self.objects.pop(path, None)


@pytest.fixture()
def env(monkeypatch: pytest.MonkeyPatch):
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
    ):
        env.setattr(db, name, target)
    env.setattr(storage, "upload_object", files.upload_object)
    env.setattr(storage, "download_object", files.download_object)
    env.setattr(storage, "delete_object", files.delete_object)
    return users, docs, files


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def make_user(users: FakeUserStore, email: str) -> dict:
    return users.create_user(email, hash_password("correct-horse-1"))


def token_for(user: dict, ttl_seconds: int = 3600) -> dict[str, str]:
    token = f"test-session-{uuid.uuid4()}"
    expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
    ).isoformat()
    db.create_session(hash_session_token(token), user["id"], expires_at)
    return {"Authorization": f"Bearer {token}"}


def upload(
    client: TestClient,
    headers: dict,
    filename: str = "doc.txt",
    content: bytes = b"hello",
    content_type: str = "text/plain",
) -> dict:
    return client.post(
        "/documents",
        headers=headers,
        files={"file": (filename, content, content_type)},
    )


# --- upload ---

def test_upload_success(client: TestClient, world) -> None:
    users, docs, files = world
    user = make_user(users, "a@example.com")
    response = upload(client, token_for(user), "report.pdf", b"%PDF", "application/pdf")
    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "report.pdf"
    assert body["file_type"] == "application/pdf"
    assert body["file_size_bytes"] == 4
    assert set(body) == {
        "id", "filename", "file_type", "file_size_bytes", "created_at", "updated_at"
    }
    path = f"{user['id']}/{body['id']}"
    assert path in files.objects
    assert files.objects[path] == (b"%PDF", "application/pdf")
    # user_id and storage_path are not exposed in the response
    assert "storage_path" not in response.text
    assert user["id"] not in response.text


def test_upload_requires_auth(client: TestClient) -> None:
    assert upload(client, {}).status_code == 401


def test_upload_rejects_oversize(client: TestClient, world, env) -> None:
    users, _docs, files = world
    env.setenv("MAX_UPLOAD_BYTES", "16")
    config.get_settings.cache_clear()
    user = make_user(users, "a@example.com")
    response = upload(client, token_for(user), content=b"x" * 17)
    assert response.status_code == 413
    assert files.objects == {}


def test_upload_rejects_empty_file(client: TestClient, world) -> None:
    users, _docs, _files = world
    user = make_user(users, "a@example.com")
    assert upload(client, token_for(user), content=b"").status_code == 422


def test_upload_rejects_over_quota_with_trusted_sizes(
    client: TestClient, world, env
) -> None:
    users, docs, files = world
    env.setenv("STORAGE_QUOTA_BYTES", "100")
    config.get_settings.cache_clear()
    user = make_user(users, "a@example.com")
    docs.create_document(
        {
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "filename": "old.bin",
            "storage_path": f"{user['id']}/old",
            "file_type": "application/octet-stream",
            "file_size_bytes": 80,
        }
    )
    response = upload(client, token_for(user), content=b"x" * 21)
    assert response.status_code == 413
    assert len(files.objects) == 0  # nothing new stored


def test_upload_allows_duplicate_filenames(client: TestClient, world) -> None:
    users, docs, _files = world
    user = make_user(users, "a@example.com")
    first = upload(client, token_for(user), "certificate.pdf", b"one")
    second = upload(client, token_for(user), "certificate.pdf", b"two")
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert len(docs.docs) == 2


@pytest.mark.parametrize(
    "filename", ["../evil.txt", "a/b.txt", "a\\b.txt", "", ".", "..", "x" * 256]
)
def test_upload_rejects_invalid_filenames(
    client: TestClient, world, filename: str
) -> None:
    users, _docs, _files = world
    user = make_user(users, "a@example.com")
    assert upload(client, token_for(user), filename=filename).status_code == 422


def test_upload_accepts_unicode_filename(client: TestClient, world) -> None:
    users, _docs, _files = world
    user = make_user(users, "a@example.com")
    response = upload(client, token_for(user), "résumé ✓.pdf", b"x")
    assert response.status_code == 201
    assert response.json()["filename"] == "résumé ✓.pdf"


def test_upload_storage_failure_leaves_no_row(client: TestClient, world) -> None:
    users, docs, files = world
    files.fail_upload = True
    user = make_user(users, "a@example.com")
    assert upload(client, token_for(user)).status_code == 500
    assert docs.docs == {}


def test_upload_insert_failure_triggers_compensating_delete(
    client: TestClient, world, monkeypatch: pytest.MonkeyPatch
) -> None:
    users, docs, files = world
    user = make_user(users, "a@example.com")

    def broken_create(row: dict) -> dict:
        raise RuntimeError("db down")

    monkeypatch.setattr(db, "create_document", broken_create)
    response = upload(client, token_for(user))
    assert response.status_code == 500
    assert docs.docs == {}
    assert files.delete_calls  # compensating cleanup ran
    assert files.objects == {}  # and removed the object


# --- listing ---

def test_list_isolates_users(client: TestClient, world) -> None:
    users, docs, _files = world
    alice = make_user(users, "alice@example.com")
    bob = make_user(users, "bob@example.com")
    docs.create_document(
        {
            "id": str(uuid.uuid4()), "user_id": alice["id"], "filename": "a.txt",
            "storage_path": "x", "file_type": "text/plain", "file_size_bytes": 1,
        }
    )
    docs.create_document(
        {
            "id": str(uuid.uuid4()), "user_id": bob["id"], "filename": "b.txt",
            "storage_path": "y", "file_type": "text/plain", "file_size_bytes": 1,
        }
    )
    response = client.get("/documents", headers=token_for(alice))
    assert response.status_code == 200
    names = [d["filename"] for d in response.json()]
    assert names == ["a.txt"]


def test_list_search_sort_filter(client: TestClient, world) -> None:
    users, docs, _files = world
    user = make_user(users, "a@example.com")
    base = {"user_id": user["id"], "storage_path": "p", "file_size_bytes": 1}
    docs.create_document({**base, "id": str(uuid.uuid4()), "filename": "Internship.pdf", "file_type": "application/pdf"})
    docs.create_document({**base, "id": str(uuid.uuid4()), "filename": "notes.txt", "file_type": "text/plain"})
    docs.create_document({**base, "id": str(uuid.uuid4()), "filename": "internship2.pdf", "file_type": "application/pdf"})
    headers = token_for(user)

    search = client.get("/documents", params={"search": "intern"}, headers=headers)
    assert {d["filename"] for d in search.json()} == {"Internship.pdf", "internship2.pdf"}

    filtered = client.get("/documents", params={"file_type": "text/plain"}, headers=headers)
    assert [d["filename"] for d in filtered.json()] == ["notes.txt"]

    sorted_asc = client.get(
        "/documents", params={"sort": "filename", "order": "asc"}, headers=headers
    )
    assert [d["filename"] for d in sorted_asc.json()] == [
        "Internship.pdf", "internship2.pdf", "notes.txt"
    ]

    assert client.get("/documents", params={"sort": "password_hash"}, headers=headers).status_code == 422
    assert client.get("/documents", params={"order": "sideways"}, headers=headers).status_code == 422
    assert client.get("/documents", params={"file_type": "nope"}, headers=headers).status_code == 422


def test_list_requires_auth(client: TestClient) -> None:
    assert client.get("/documents").status_code == 401


# --- usage ---

def test_usage_is_per_user(client: TestClient, world) -> None:
    users, docs, _files = world
    alice = make_user(users, "alice@example.com")
    bob = make_user(users, "bob@example.com")
    docs.create_document(
        {"id": str(uuid.uuid4()), "user_id": alice["id"], "filename": "a",
         "storage_path": "p1", "file_type": "text/plain", "file_size_bytes": 10}
    )
    docs.create_document(
        {"id": str(uuid.uuid4()), "user_id": bob["id"], "filename": "b",
         "storage_path": "p2", "file_type": "text/plain", "file_size_bytes": 99}
    )
    response = client.get("/documents/usage", headers=token_for(alice))
    assert response.status_code == 200
    assert response.json() == {
        "used_bytes": 10,
        "quota_bytes": 524_288_000,
        "document_count": 1,
    }


# --- download ---

def test_download_owner_gets_bytes(client: TestClient, world) -> None:
    users, _docs, _files = world
    user = make_user(users, "a@example.com")
    created = upload(client, token_for(user), "notes.txt", b"payload", "text/plain").json()
    response = client.get(f"/documents/{created['id']}", headers=token_for(user))
    assert response.status_code == 200
    assert response.content == b"payload"
    assert response.headers["content-type"].startswith("text/plain")
    assert "attachment" in response.headers["content-disposition"]


def test_download_nonexistent_is_404(client: TestClient, world) -> None:
    users, _docs, _files = world
    user = make_user(users, "a@example.com")
    response = client.get(f"/documents/{uuid.uuid4()}", headers=token_for(user))
    assert response.status_code == 404
    assert response.json() == {"detail": "Document not found"}


def test_download_malformed_id_is_404(client: TestClient, world) -> None:
    users, _docs, _files = world
    user = make_user(users, "a@example.com")
    response = client.get("/documents/not-a-uuid", headers=token_for(user))
    assert response.status_code == 404


def test_download_foreign_owned_is_404(client: TestClient, world) -> None:
    users, _docs, _files = world
    alice = make_user(users, "alice@example.com")
    bob = make_user(users, "bob@example.com")
    created = upload(client, token_for(alice), content=b"x").json()
    response = client.get(f"/documents/{created['id']}", headers=token_for(bob))
    assert response.status_code == 404


# --- rename ---

def test_rename_updates_metadata_only(client: TestClient, world) -> None:
    users, _docs, files = world
    user = make_user(users, "a@example.com")
    created = upload(client, token_for(user), "IMG_28371.pdf", b"x").json()
    old_path = f"{user['id']}/{created['id']}"
    response = client.patch(
        f"/documents/{created['id']}",
        json={"filename": "Python_Internship_Certificate.pdf"},
        headers=token_for(user),
    )
    assert response.status_code == 200
    assert response.json()["filename"] == "Python_Internship_Certificate.pdf"
    assert old_path in files.objects  # object never moved


def test_rename_foreign_is_404(client: TestClient, world) -> None:
    users, _docs, _files = world
    alice = make_user(users, "alice@example.com")
    bob = make_user(users, "bob@example.com")
    created = upload(client, token_for(alice), content=b"x").json()
    response = client.patch(
        f"/documents/{created['id']}", json={"filename": "stolen.txt"}, headers=token_for(bob)
    )
    assert response.status_code == 404


@pytest.mark.parametrize("filename", ["bad/name.txt", "..", "", "x" * 256])
def test_rename_rejects_invalid_filenames(
    client: TestClient, world, filename: str
) -> None:
    users, _docs, _files = world
    user = make_user(users, "a@example.com")
    created = upload(client, token_for(user), content=b"x").json()
    response = client.patch(
        f"/documents/{created['id']}", json={"filename": filename}, headers=token_for(user)
    )
    assert response.status_code == 422


# --- delete ---

def test_delete_removes_row_and_object(client: TestClient, world) -> None:
    users, docs, files = world
    user = make_user(users, "a@example.com")
    created = upload(client, token_for(user), content=b"x").json()
    response = client.delete(f"/documents/{created['id']}", headers=token_for(user))
    assert response.status_code == 204
    assert created["id"] not in docs.docs
    assert f"{user['id']}/{created['id']}" not in files.objects


def test_delete_survives_storage_failure(client: TestClient, world) -> None:
    users, docs, files = world
    user = make_user(users, "a@example.com")
    created = upload(client, token_for(user), content=b"x").json()
    files.fail_delete = True
    response = client.delete(f"/documents/{created['id']}", headers=token_for(user))
    assert response.status_code == 204
    assert created["id"] not in docs.docs  # metadata row is source of truth
    assert files.delete_calls  # cleanup was attempted and logged


def test_delete_foreign_is_404(client: TestClient, world) -> None:
    users, _docs, _files = world
    alice = make_user(users, "alice@example.com")
    bob = make_user(users, "bob@example.com")
    created = upload(client, token_for(alice), content=b"x").json()
    assert client.delete(
        f"/documents/{created['id']}", headers=token_for(bob)
    ).status_code == 404


# --- auth coverage for every route ---

@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/documents"),
        ("GET", "/documents/usage"),
        ("GET", f"/documents/{uuid.uuid4()}"),
        ("PATCH", f"/documents/{uuid.uuid4()}"),
        ("DELETE", f"/documents/{uuid.uuid4()}"),
    ],
)
def test_protected_routes_reject_missing_token(
    client: TestClient, method: str, path: str
) -> None:
    response = client.request(method, path, json={"filename": "x.txt"})
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
