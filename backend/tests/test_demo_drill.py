# backend/tests/test_demo_drill.py: Tests for tests.
"""Demo traffic simulator tests — mocked HTTP client; no real calls.

All tests use httpx.MockTransport to simulate the FastAPI backend.
No real accounts are created, no documents are uploaded, and no
external services are contacted.
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import patch

import httpx
import pytest

from app.scripts.demo_drill import (
    DEFAULT_BASE_URL,
    DEFAULT_MAX_UPLOADS_PER_USER,
    DEFAULT_USER_COUNT,
    DemoAccount,
    DemoDriver,
    main,
)


def _make_handler(routes: dict[tuple[str, str], tuple[int, dict]]) -> httpx.MockTransport:
    """Build an httpx.MockTransport handler from a route table.

    routes maps (method, path) -> (status_code, json_body_or_None).
    """
    def handler(request: httpx.Request) -> httpx.Response:
        key = (request.method, request.url.path)
        if key in routes:
            status, body = routes[key]
            return httpx.Response(status_code=status, json=body)
        return httpx.Response(404, json={"detail": "not found"})
    return httpx.MockTransport(handler)


def _make_driver(
    monkeypatch: pytest.MonkeyPatch,
    routes: dict[tuple[str, str], tuple[int, dict]],
) -> DemoDriver:
    """Create a DemoDriver with a mocked httpx transport."""
    transport = _make_handler(routes)
    driver = DemoDriver(base_url="http://testserver")
    driver.http_client = httpx.Client(base_url="http://testserver", transport=transport)
    return driver


def test_register_account_success():
    """Registering a new account via POST /auth/register succeeds."""
    routes = {
        ("POST", "/auth/register"): (201, {"id": "u1", "email": "demo-drill-1@example.com"}),
    }
    driver = _make_driver(None, routes)
    account = driver._create_account()
    assert account is not None
    assert account.email.startswith("demo-drill-")
    assert account.email.endswith("@demo.ai-digital-locker.test")
    assert account.user_id == "u1"
    assert account.token is None                     


def test_register_account_duplicate_email():
    """Duplicate email registration returns 409 and no account is created."""
    routes = {
        ("POST", "/auth/register"): (409, {"detail": "Email already registered"}),
    }
    driver = _make_driver(None, routes)
    account = driver._create_account()
    assert account is None
    assert len(driver.accounts) == 0


def test_login_account_success():
    """Successful login sets the account's access token."""
    routes = {
        ("POST", "/auth/register"): (201, {"id": "u1", "email": "demo-drill-1@example.com"}),
        ("POST", "/auth/login"): (200, {"access_token": "tok-abc123", "token_type": "bearer", "expires_in": 86400}),
    }
    driver = _make_driver(None, routes)
    account = driver._create_account()
    assert account is not None
    assert driver._login_account(account) is True
    assert account.token == "tok-abc123"


def test_login_account_failure():
    """Failed login leaves token as None."""
    routes = {
        ("POST", "/auth/register"): (201, {"id": "u1", "email": "demo-drill-1@example.com"}),
        ("POST", "/auth/login"): (401, {"detail": "Incorrect email or password"}),
    }
    driver = _make_driver(None, routes)
    account = driver._create_account()
    assert account is not None
    assert driver._login_account(account) is False
    assert account.token is None


def test_upload_document_success():
    """Successful upload adds document to account's tracked list."""
    routes = {
        ("POST", "/auth/register"): (201, {"id": "u1", "email": "demo-drill-1@example.com"}),
        ("POST", "/auth/login"): (200, {"access_token": "tok-abc123", "token_type": "bearer", "expires_in": 86400}),
        ("POST", "/documents"): (201, {"id": "d1", "filename": "report.pdf", "file_type": "application/pdf", "file_size_bytes": 100}),
    }
    driver = _make_driver(None, routes)
    account = driver._create_account()
    assert account is not None
    assert driver._login_account(account) is True
    doc_id = driver._upload_document(account)
    assert doc_id == "d1"
    assert doc_id in account.document_ids


def test_upload_document_failure():
    """Failed upload returns None and doesn't add document."""
    routes = {
        ("POST", "/auth/register"): (201, {"id": "u1", "email": "demo-drill-1@example.com"}),
        ("POST", "/auth/login"): (200, {"access_token": "tok-abc123", "token_type": "bearer", "expires_in": 86400}),
        ("POST", "/documents"): (500, {"detail": "Failed to store file"}),
    }
    driver = _make_driver(None, routes)
    account = driver._create_account()
    assert account is not None
    assert driver._login_account(account) is True
    doc_id = driver._upload_document(account)
    assert doc_id is None
    assert len(account.document_ids) == 0


def test_list_documents():
    """Listing documents makes a GET request."""
    routes = {
        ("POST", "/auth/register"): (201, {"id": "u1", "email": "demo-drill-1@example.com"}),
        ("POST", "/auth/login"): (200, {"access_token": "tok-abc123", "token_type": "bearer", "expires_in": 86400}),
        ("POST", "/documents"): (201, {"id": "d1", "filename": "report.pdf", "file_type": "application/pdf", "file_size_bytes": 100}),
        ("GET", "/documents"): (200, [{"id": "d1", "filename": "report.pdf", "file_type": "application/pdf", "file_size_bytes": 100}]),
    }
    driver = _make_driver(None, routes)
    account = driver._create_account()
    assert account is not None
    assert driver._login_account(account) is True
    driver._upload_document(account)
    driver._list_documents(account)                    


def test_download_document():
    """Downloading a document owned by the account succeeds."""
    routes = {
        ("POST", "/auth/register"): (201, {"id": "u1", "email": "demo-drill-1@example.com"}),
        ("POST", "/auth/login"): (200, {"access_token": "tok-abc123", "token_type": "bearer", "expires_in": 86400}),
        ("POST", "/documents"): (201, {"id": "d1", "filename": "report.pdf", "file_type": "application/pdf", "file_size_bytes": 100}),
        ("GET", "/documents/d1"): (200, {"content": "PDF content here"}),
    }
    driver = _make_driver(None, routes)
    account = driver._create_account()
    assert account is not None
    assert driver._login_account(account) is True
    doc_id = driver._upload_document(account)
    assert doc_id is not None
    driver._download_document(account, doc_id)                    


def test_rename_document():
    """Renaming a document owned by the account succeeds."""
    routes = {
        ("POST", "/auth/register"): (201, {"id": "u1", "email": "demo-drill-1@example.com"}),
        ("POST", "/auth/login"): (200, {"access_token": "tok-abc123", "token_type": "bearer", "expires_in": 86400}),
        ("POST", "/documents"): (201, {"id": "d1", "filename": "old.pdf", "file_type": "application/pdf", "file_size_bytes": 100}),
        ("PATCH", "/documents/d1"): (200, {"id": "d1", "filename": "new.pdf", "file_type": "application/pdf", "file_size_bytes": 100}),
    }
    driver = _make_driver(None, routes)
    account = driver._create_account()
    assert account is not None
    assert driver._login_account(account) is True
    doc_id = driver._upload_document(account)
    assert doc_id is not None
    driver._rename_document(account, doc_id)                    


def test_delete_document():
    """Deleting a document removes it from account's tracking."""
    routes = {
        ("POST", "/auth/register"): (201, {"id": "u1", "email": "demo-drill-1@example.com"}),
        ("POST", "/auth/login"): (200, {"access_token": "tok-abc123", "token_type": "bearer", "expires_in": 86400}),
        ("POST", "/documents"): (201, {"id": "d1", "filename": "report.pdf", "file_type": "application/pdf", "file_size_bytes": 100}),
        ("DELETE", "/documents/d1"): (204, None),
    }
    driver = _make_driver(None, routes)
    account = driver._create_account()
    assert account is not None
    assert driver._login_account(account) is True
    doc_id = driver._upload_document(account)
    assert doc_id is not None
    assert doc_id in account.document_ids
    driver._delete_document(account, doc_id)
    assert doc_id not in account.document_ids


def test_delete_document_nonexistent():
    """Deleting a nonexistent document doesn't crash."""
    routes = {
        ("POST", "/auth/register"): (201, {"id": "u1", "email": "demo-drill-1@example.com"}),
        ("POST", "/auth/login"): (200, {"access_token": "tok-abc123", "token_type": "bearer", "expires_in": 86400}),
        ("POST", "/documents"): (201, {"id": "d1", "filename": "report.pdf", "file_type": "application/pdf", "file_size_bytes": 100}),
        ("DELETE", "/documents/nonexistent"): (404, {"detail": "Document not found"}),
    }
    driver = _make_driver(None, routes)
    account = driver._create_account()
    assert account is not None
    assert driver._login_account(account) is True
    doc_id = driver._upload_document(account)
    assert doc_id is not None
    driver._delete_document(account, "nonexistent")
                                                                         
    assert doc_id in account.document_ids


def test_main_requires_run_flag():
    """Running without --run or --dry-run exits with code 2."""
    import sys
    from io import StringIO

    old_stderr = sys.stderr
    sys.stderr = StringIO()
    try:
        result = main([])
    finally:
        sys.stderr = old_stderr
    assert result == 2


def test_main_dry_run_exits_zero():
    """Running with --dry-run exits 0 and makes no network calls."""
    import sys
    from io import StringIO

    old_stderr = sys.stderr
    sys.stderr = StringIO()
    try:
        result = main(["--dry-run"])
    finally:
        sys.stderr = old_stderr
    assert result == 0


def test_main_run_requires_base_url_validation():
    """Running with a non-localhost URL without --allow-remote exits 2."""
    import sys
    from io import StringIO

    old_stderr = sys.stderr
    sys.stderr = StringIO()
    try:
        result = main(["--run", "--base-url", "https://evil.example.com"])
    finally:
        sys.stderr = old_stderr
    assert result == 2


def test_main_run_localhost_ok():
    """Running with localhost URL passes validation."""
    import sys
    from io import StringIO

    old_stderr = sys.stderr
    sys.stderr = StringIO()
    try:
        result = main(["--run", "--base-url", "http://127.0.0.1:8000", "--user-count", "1", "--duration-seconds", "1"])
    finally:
        sys.stderr = old_stderr
                                                                            
    assert result != 2                                     


def test_user_count_validation():
    """User count must be between 1 and 20."""
    import sys
    from io import StringIO

    old_stderr = sys.stderr
    sys.stderr = StringIO()
    try:
        result = main(["--run", "--user-count", "0"])
    finally:
        sys.stderr = old_stderr
    assert result == 2

    old_stderr = sys.stderr
    sys.stderr = StringIO()
    try:
        result = main(["--run", "--user-count", "25"])
    finally:
        sys.stderr = old_stderr
    assert result == 2


def test_cleanup_requires_run():
    """--cleanup requires --run."""
    import sys
    from io import StringIO

    old_stderr = sys.stderr
    sys.stderr = StringIO()
    try:
        result = main(["--cleanup"])
    finally:
        sys.stderr = old_stderr
    assert result == 2


def test_dry_run_and_run_mutually_exclusive():
    """--dry-run and --run are mutually exclusive."""
    import sys
    from io import StringIO

    old_stderr = sys.stderr
    sys.stderr = StringIO()
    try:
        result = main(["--run", "--dry-run"])
    finally:
        sys.stderr = old_stderr
    assert result == 2


def test_demo_account_properties():
    """DemoAccount stores email, password, user_id, and has empty token initially."""
    account = DemoAccount(email="test@example.com", password="secret123", user_id="u1")
    assert account.email == "test@example.com"
    assert account.password == "secret123"
    assert account.user_id == "u1"
    assert account.token is None
    assert account.document_ids == []
    assert account.auth_headers == {}


def test_demo_account_auth_headers_with_token():
    """auth_headers returns Bearer token when token is set."""
    account = DemoAccount(email="test@example.com", password="secret123", user_id="u1")
    account.token = "tok-abc123"
    assert account.auth_headers == {"Authorization": "Bearer tok-abc123"}