"""API client tests via httpx.MockTransport - no network, no credentials."""
from pathlib import Path

import httpx
import pytest

from app.api_client import (
    ApiClient,
    ApiError,
    describe_api_error,
    DETAIL_QUOTA,
    DETAIL_TOO_LARGE,
)

TOKEN = "test-access-token-abc123"


def make_client(handler):
    return ApiClient("http://backend.test", transport=httpx.MockTransport(handler))


def test_register_posts_json_and_normalizes_nothing_extra():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["body"] = request.content
        return httpx.Response(201, json={"id": "u1", "email": "a@b.co"})

    client = make_client(handler)
    client.register("a@b.co", "password123")
    assert seen["method"] == "POST"
    assert seen["url"].endswith("/auth/register")
    assert b'"password":"password123"' in seen["body"]


def test_login_returns_token_payload_and_401_maps_to_apierror():
    def ok_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "access_token": TOKEN, "token_type": "bearer", "expires_in": 86400,
        })

    data = make_client(ok_handler).login("a@b.co", "password123")
    assert data["access_token"] == TOKEN

    def bad_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "Incorrect email or password"})

    with pytest.raises(ApiError) as excinfo:
        make_client(bad_handler).login("a@b.co", "wrongpass1")
    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "Incorrect email or password"


def test_list_documents_forwards_params_and_bearer_header_not_url():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["params"] = dict(request.url.params)
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json=[])

    client = make_client(handler)
    client.list_documents(TOKEN, search="notes", sort="filename", order="asc",
                          file_type="application/pdf")
    assert seen["params"] == {
        "search": "notes", "sort": "filename", "order": "asc",
        "file_type": "application/pdf",
    }
    assert seen["auth"] == f"Bearer {TOKEN}"
    assert TOKEN not in seen["url"]  # JWT never in a URL


def test_usage_and_me_and_rename_and_delete():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, str(request.url)))
        if request.url.path.endswith("/usage"):
            return httpx.Response(200, json={
                "used_bytes": 10, "quota_bytes": 524288000, "document_count": 1,
            })
        if request.method == "DELETE":
            return httpx.Response(204)
        if request.method == "PATCH":
            return httpx.Response(200, json={"id": "d1", "filename": "new.pdf",
                                             "file_type": "application/pdf",
                                             "file_size_bytes": 1,
                                             "created_at": "2026-01-01T00:00:00Z",
                                             "updated_at": "2026-01-01T00:00:00Z"})
        return httpx.Response(200, json={"id": "u1", "email": "a@b.co",
                                         "is_admin": False, "created_at": "x"})

    client = make_client(handler)
    assert client.usage(TOKEN)["document_count"] == 1
    assert client.me(TOKEN)["id"] == "u1"
    assert client.rename(TOKEN, "d1", "new.pdf")["filename"] == "new.pdf"
    client.delete(TOKEN, "d1")
    assert ("DELETE", "http://backend.test/documents/d1") in seen


def test_upload_sends_multipart_and_maps_413_details(tmp_path: Path):
    payload = tmp_path / "notes.pdf"
    payload.write_bytes(b"%PDF")

    def ok_handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url).endswith("/documents")
        assert request.headers.get("authorization") == f"Bearer {TOKEN}"
        assert b"notes.pdf" in request.content
        return httpx.Response(201, json={"id": "d1", "filename": "notes.pdf"})

    doc = make_client(ok_handler).upload(TOKEN, payload)
    assert doc["id"] == "d1"

    def quota_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(413, json={"detail": DETAIL_QUOTA})

    with pytest.raises(ApiError) as quota:
        make_client(quota_handler).upload(TOKEN, payload)
    assert quota.value.detail == DETAIL_QUOTA
    assert "quota" in describe_api_error(quota.value).lower()

    def size_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(413, json={"detail": DETAIL_TOO_LARGE})

    with pytest.raises(ApiError) as size:
        make_client(size_handler).upload(TOKEN, payload)
    assert "50 MiB" in describe_api_error(size.value)


def test_download_streams_to_file_and_cleans_up_on_failure(tmp_path: Path):
    def ok_handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("authorization") == f"Bearer {TOKEN}"
        assert str(request.url).endswith("/documents/d1")
        return httpx.Response(200, content=b"PDFBYTES")

    dest = tmp_path / "sub" / "out.pdf"
    make_client(ok_handler).download_to_file(TOKEN, "d1", dest)
    assert dest.read_bytes() == b"PDFBYTES"
    assert not list(dest.parent.glob(".dl-*.part"))  # no temp leftovers

    def missing_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "Document not found"})

    bad_dest = tmp_path / "nope.pdf"
    with pytest.raises(ApiError) as excinfo:
        make_client(missing_handler).download_to_file(TOKEN, "d1", bad_dest)
    assert excinfo.value.status_code == 404
    assert not bad_dest.exists()
    assert not list(tmp_path.glob(".dl-*.part"))


def test_network_error_maps_to_status_zero():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    with pytest.raises(ApiError) as excinfo:
        make_client(handler).login("a@b.co", "password123")
    assert excinfo.value.status_code == 0
    assert "Cannot reach the server" in describe_api_error(excinfo.value)


def test_describe_never_leaks_internals():
    assert describe_api_error(RuntimeError("secret-path/stack")) == (
        "Something went wrong. Please try again."
    )
    assert "secret" not in describe_api_error(ApiError(500, "internal detail"))
