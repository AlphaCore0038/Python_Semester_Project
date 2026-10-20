"""Regression tests for the Supabase Storage wrapper.

The live bug: upload() was called with content_type=/upsert= kwargs, which
the installed storage3 (2.33.0) does not accept -- it takes a FileOptions
TypedDict as the third argument. These tests pin the real SDK signature and
the exact options dict our wrapper passes.
"""

import inspect

from app import storage


class FakeBucket:
    def __init__(self):
        self.calls = []

    def upload(self, path, data, file_options=None):
        self.calls.append((path, data, file_options))


class FakeStorage:
    def __init__(self, bucket):
        self._bucket = bucket

    def from_(self, name):
        assert name == "documents", "wrapper must target the private documents bucket"
        return self._bucket


class FakeSupabase:
    def __init__(self, bucket):
        self.storage = FakeStorage(bucket)


def test_installed_sdk_upload_signature():
    """The installed SDK must accept file_options and NOT content_type."""
    from storage3._sync.file_api import SyncBucketActionsMixin

    params = inspect.signature(SyncBucketActionsMixin.upload).parameters
    assert "file_options" in params
    assert "content_type" not in params
    assert "upsert" not in params


def test_upload_object_passes_file_options_typedict(monkeypatch):
    bucket = FakeBucket()
    monkeypatch.setattr(storage, "get_supabase", lambda: FakeSupabase(bucket))

    storage.upload_object("user-1/doc-1", b"%PDF", "application/pdf")

    assert bucket.calls == [
        ("user-1/doc-1", b"%PDF", {"content-type": "application/pdf", "upsert": "false"})
    ]


def test_upload_object_upsert_is_string_false(monkeypatch):
    """upsert must be the string 'false' (TypedDict str); bool False is wrong."""
    bucket = FakeBucket()
    monkeypatch.setattr(storage, "get_supabase", lambda: FakeSupabase(bucket))

    storage.upload_object("u/i", b"x", "text/plain")

    _, _, options = bucket.calls[0]
    assert options["upsert"] == "false"
    assert isinstance(options["upsert"], str)


def test_download_and_delete_use_expected_bucket_methods(monkeypatch):
    class DLBucket:
        def download(self, path):
            assert path == "u/i"
            return b"bytes"

        def remove(self, paths):
            assert paths == ["u/i"]
            return [{"name": "u/i"}]

    monkeypatch.setattr(storage, "get_supabase", lambda: FakeSupabase(DLBucket()))
    assert storage.download_object("u/i") == b"bytes"
    storage.delete_object("u/i")


def test_real_sdk_request_carries_content_type_and_no_overwrite(monkeypatch):
    """Drive the installed storage3 end-to-end with a mocked HTTP transport:
    the object part must carry our MIME type and x-upsert must be 'false'."""
    import httpx
    from storage3 import SyncStorageClient

    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, json={"Key": "user-1/doc-1"})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = SyncStorageClient(
        "http://supabase.test/storage/v1/", {}, http_client=http
    )
    monkeypatch.setattr(
        storage, "get_supabase", lambda: type("S", (), {"storage": client})()
    )

    storage.upload_object("user-1/doc-1", b"%PDF", "application/pdf")

    req = captured["request"]
    # Object key format preserved: /object/{bucket}/{user_id}/{document_id}
    assert str(req.url).startswith(
        "http://supabase.test/storage/v1/object/documents/user-1/doc-1"
    )
    # Non-overwrite semantics sent to the API.
    assert req.headers.get("x-upsert") == "false"
    # Multipart part content type is the caller's MIME type, not text/plain.
    assert b"Content-Type: application/pdf" in req.content
    # Private bucket: no query params like ?public=true anywhere.
    assert "public" not in str(req.url)
