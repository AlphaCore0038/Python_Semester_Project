"""Google Sheets reporting tests — mocked Google API client; no real calls.

Sheets is a secondary reporting layer: every test here verifies metadata flow
and failure tolerance without contacting Google or writing to a spreadsheet.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app import config, db, sheets, storage
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


class FakeSheets:
    """Records sheets calls like the real client, but writes nowhere."""

    def __init__(self) -> None:
        self.rows: dict[str, list] = {}
        self.upsert_calls: list[tuple[str, str | None]] = []
        self.delete_calls: list[str] = []
        self.fail = False

    def report_document(self, document: dict, owner_email: str | None) -> None:
        self.upsert_calls.append((str(document["id"]), owner_email))
        if self.fail:
            raise RuntimeError("sheets down")
        self.rows[str(document["id"])] = list(
            sheets.SheetsClient._row(document, owner_email)
        )

    def delete_document_row(self, document_id: str) -> None:
        self.delete_calls.append(str(document_id))
        if self.fail:
            raise RuntimeError("sheets down")
        self.rows.pop(str(document_id), None)


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
def world(env: pytest.MonkeyPatch):
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
def sheets_report(env: pytest.MonkeyPatch, monkeypatch: pytest.MonkeyPatch):
    report = FakeSheets()
    monkeypatch.setattr(sheets.sheets, "report_document", report.report_document)
    monkeypatch.setattr(
        sheets.sheets, "delete_document_row", report.delete_document_row
    )
    return report


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
):
    return client.post(
        "/documents",
        headers=headers,
        files={"file": (filename, content, content_type)},
    )


# --- row mapping ---


def test_row_mapping_has_eight_columns():
    document = {
        "id": "doc-1",
        "filename": "report.pdf",
        "file_type": "application/pdf",
        "file_size_bytes": 1234,
        "created_at": "2026-10-20T00:00:00+00:00",
        "updated_at": "2026-10-21T00:00:00+00:00",
    }
    row = sheets.SheetsClient._row(document, "alice@example.com")
    assert row == [
        "doc-1",
        "alice@example.com",
        "report.pdf",
        "application/pdf",
        1234,
        "2026-10-20T00:00:00+00:00",
        "2026-10-21T00:00:00+00:00",
        "Cloud",
    ]
    assert len(row) == 8


def test_row_missing_owner_email_degrades_gracefully():
    document = {
        "id": "doc-2",
        "filename": "notes.txt",
        "file_type": "text/plain",
        "file_size_bytes": 5,
        "created_at": "2026-10-20T00:00:00+00:00",
        "updated_at": "2026-10-20T00:00:00+00:00",
    }
    row = sheets.SheetsClient._row(document, None)
    assert row[1] == ""
    assert len(row) == 8


# --- upload ---


def test_upload_creates_sheets_row(client, world, sheets_report):
    users, docs, files = world
    report = sheets_report
    user = make_user(users, "a@example.com")
    response = upload(client, token_for(user), "report.pdf", b"%PDF", "application/pdf")
    assert response.status_code == 201
    document_id = response.json()["id"]
    assert len(report.upsert_calls) == 1
    reported_id, owner_email = report.upsert_calls[0]
    assert reported_id == document_id
    assert owner_email == "a@example.com"
    assert document_id in report.rows
    stored = report.rows[document_id]
    assert stored[0] == document_id
    assert stored[1] == "a@example.com"
    assert stored[2] == "report.pdf"
    assert stored[3] == "application/pdf"
    assert stored[4] == 4
    # No document content or secrets in the payload.
    assert b"%PDF" not in stored
    assert "correct-horse-1" not in str(stored)


def test_upload_works_without_sheets_configured(client, env):
    users = FakeUserStore()
    docs = FakeDocStore()
    for name, target in (
        ("get_user_by_email", users.get_user_by_email),
        ("create_user", users.create_user),
        ("get_user_by_id", users.get_user_by_id),
        ("create_document", docs.create_document),
        ("get_document", docs.get_document),
        ("create_session", users.create_session),
        ("get_session", users.get_session),
        ("delete_session", users.delete_session),
        ("sum_usage_and_count", docs.sum_usage_and_count),
    ):
        env.setattr(db, name, target)
    env.setattr(storage, "upload_object", FakeStorage().upload_object)
    user = make_user(users, "a@example.com")
    # Sheets is not configured and not patched: the real client is a no-op.
    response = upload(client, token_for(user), "report.pdf", b"%PDF", "application/pdf")
    assert response.status_code == 201


def test_upload_api_failure_does_not_break_upload(client, world, sheets_report):
    users, docs, files = world
    report = sheets_report
    report.fail = True
    user = make_user(users, "a@example.com")
    # Sheets raises, but upload must still succeed.
    response = upload(client, token_for(user), "report.pdf", b"%PDF", "application/pdf")
    assert response.status_code == 201
    assert response.json()["id"] in docs.docs


# --- rename ---


def test_rename_updates_existing_row_by_document_id(client, world, sheets_report):
    users, docs, files = world
    report = sheets_report
    user = make_user(users, "a@example.com")
    created = upload(
        client, token_for(user), "IMG_28371.pdf", b"x", "application/pdf"
    ).json()
    document_id = created["id"]
    response = client.patch(
        f"/documents/{document_id}",
        json={"filename": "Python_Internship_Certificate.pdf"},
        headers=token_for(user),
    )
    assert response.status_code == 200
    # Exactly one upsert for upload, one upsert (update) for rename — no duplicate row.
    assert len(report.upsert_calls) == 2
    assert report.upsert_calls[1][0] == document_id
    assert report.rows[document_id][2] == "Python_Internship_Certificate.pdf"


# --- delete ---


def test_delete_removes_sheets_row(client, world, sheets_report):
    users, docs, files = world
    report = sheets_report
    user = make_user(users, "a@example.com")
    created = upload(client, token_for(user), content=b"x").json()
    document_id = created["id"]
    assert document_id in report.rows
    response = client.delete(f"/documents/{document_id}", headers=token_for(user))
    assert response.status_code == 204
    assert document_id in report.delete_calls
    assert document_id not in report.rows


# --- duplicates and idempotency ---


def test_duplicate_filenames_remain_separate_rows(client, world, sheets_report):
    users, docs, files = world
    report = sheets_report
    user = make_user(users, "a@example.com")
    first = upload(client, token_for(user), "certificate.pdf", b"one")
    second = upload(client, token_for(user), "certificate.pdf", b"two")
    assert first.status_code == second.status_code == 201
    id1 = first.json()["id"]
    id2 = second.json()["id"]
    assert id1 != id2
    assert set(report.rows) == {id1, id2}


def test_repeated_sync_is_idempotent(client, world, sheets_report):
    users, docs, files = world
    report = sheets_report
    user = make_user(users, "a@example.com")
    created = upload(client, token_for(user), "notes.txt", b"x").json()
    document_id = created["id"]
    # Report the same document twice.
    row = docs.get_document(document_id, user["id"])
    sheets.sheets.report_document(row, user["email"])
    sheets.sheets.report_document(row, user["email"])
    assert len(report.upsert_calls) == 3  # upload + 2 manual reports
    assert list(report.rows) == [document_id]  # still one row


# --- authorization unchanged ---


def test_sheets_does_not_bypass_auth(client, env):
    users = FakeUserStore()
    for name, target in (
        ("get_user_by_email", users.get_user_by_email),
        ("create_user", users.create_user),
        ("get_user_by_id", users.get_user_by_id),
        ("create_session", users.create_session),
        ("get_session", users.get_session),
        ("delete_session", users.delete_session),
    ):
        env.setattr(db, name, target)
    make_user(users, "a@example.com")
    # No token -> still 401 even though Sheets would be a no-op.
    assert upload(client, {}, "report.pdf", b"x").status_code == 401


# --- worksheet title handling ---


def _make_client_with_service(sheet_title: str, sheet_id: int = 1):
    """Build a SheetsClient with a fake service, bypassing _init."""
    service = MagicMock()
    service.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {
        "values": []
    }
    service.spreadsheets.return_value.values.return_value.update.return_value.execute.return_value = {}
    service.spreadsheets.return_value.batchUpdate.return_value.execute.return_value = {}

    client = sheets.SheetsClient()
    client._initialized = True
    client._sheet_id = sheet_id
    client._sheet_title = sheet_title
    client._service = service
    return client, service


def _document_row(document_id: str = "d1") -> dict:
    return {
        "id": document_id,
        "filename": "report.pdf",
        "file_type": "application/pdf",
        "file_size_bytes": 4,
        "created_at": "2026-10-20T00:00:00+00:00",
        "updated_at": "2026-10-21T00:00:00+00:00",
    }


def test_non_default_worksheet_title_used_for_read_and_update():
    client, service = _make_client_with_service("My Reports", 7)
    # Seed values so the existing document is found and updated in place.
    service.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {
        "values": [
            ["Document ID", "User Email", "Filename", "File Type", "File Size", "Upload Time", "Last Modified", "Storage Mode"],
            ["d1", "a@example.com", "report.pdf", "application/pdf", 4, "t1", "t2", "Cloud"],
        ]
    }
    client._upsert_row(_document_row("d1"), "a@example.com")
    update_call = (
        service.spreadsheets.return_value.values.return_value.update.call_args
    )
    assert update_call.kwargs["range"] == "'My Reports'!2:2"
    get_call = (
        service.spreadsheets.return_value.values.return_value.get.call_args
    )
    assert get_call.kwargs["range"] == "'My Reports'!A:H"


def test_apostrophe_in_worksheet_title_is_escaped():
    client, service = _make_client_with_service("O'Brien's Reports", 3)
    service.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {
        "values": [["d1", "a@example.com", "report.pdf", "application/pdf", 4, "t1", "t2", "Cloud"]]
    }
    client._upsert_row(_document_row("d1"), "a@example.com")
    update_call = (
        service.spreadsheets.return_value.values.return_value.update.call_args
    )
    assert update_call.kwargs["range"] == "'O''Brien''s Reports'!1:1"


def test_delete_uses_discovered_sheet_id():
    client, service = _make_client_with_service("Reports", 42)
    # Seed the sheet values so the row is found.
    service.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {
        "values": [["d1", "a@example.com", "report.pdf", "application/pdf", 4, "t1", "t2", "Cloud"]]
    }
    client._delete_row_by_id("d1")
    batch_call = service.spreadsheets.return_value.batchUpdate.call_args
    body = batch_call.kwargs["body"]
    assert body["requests"][0]["deleteDimension"]["range"]["sheetId"] == 42


def test_empty_config_disables_reporting(monkeypatch):
    monkeypatch.setenv("GOOGLE_SHEET_ID", "")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_FILE", "")
    config.get_settings.cache_clear()
    client = sheets.SheetsClient()
    # Should not attempt any Google API initialization.
    client.report_document(_document_row(), "a@example.com")
    assert client._service is None
    assert client._spreadsheet_id is None
    config.get_settings.cache_clear()


def test_init_failure_is_non_fatal(monkeypatch):
    monkeypatch.setenv("GOOGLE_SHEET_ID", "fake-id")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_FILE", "creds.json")
    config.get_settings.cache_clear()
    client = sheets.SheetsClient()
    # Pretend initialization completed but the service is broken.
    client._initialized = True
    client._sheet_id = 1
    client._sheet_title = "Sheet1"
    broken_service = MagicMock()
    broken_service.spreadsheets.side_effect = Exception("boom")
    client._service = broken_service
    # Must not raise; failure is logged and swallowed.
    client.report_document(_document_row(), "a@example.com")
    config.get_settings.cache_clear()
