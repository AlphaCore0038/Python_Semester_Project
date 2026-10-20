"""HTTP client for the FastAPI backend (the only API the desktop uses).

The backend is the sole source of truth for authentication, authorization,
cloud metadata, and quotas. This module never contacts Supabase directly
and never builds public Storage URLs. The JWT travels only in the
Authorization header -- never in URLs, logs, or printed output.
"""
from __future__ import annotations

import mimetypes
import os
import tempfile
from pathlib import Path

import httpx

# Exact backend 413 detail strings (verified against app/routers/documents.py).
DETAIL_TOO_LARGE = "File exceeds the maximum upload size"
DETAIL_QUOTA = "Storage quota exceeded"

DOWNLOAD_CHUNK = 64 * 1024


class ApiError(Exception):
    """Normalized backend/network error. status_code 0 == unreachable."""

    def __init__(self, status_code: int, detail: str = ""):
        super().__init__(detail or str(status_code))
        self.status_code = status_code
        self.detail = detail


def describe_api_error(exc: BaseException) -> str:
    """Safe, user-facing message. Never returns raw exception internals."""
    if isinstance(exc, ApiError):
        status, detail = exc.status_code, exc.detail
        if status == 0:
            return "Cannot reach the server. Is the backend running?"
        if status == 401:
            return "Your session has expired. Please log in again."
        if status == 404:
            return "Document not found."
        if status == 409:
            return "Email already registered."
        if status == 413 and detail == DETAIL_QUOTA:
            return "Storage quota reached (500 MB). Delete files to free space."
        if status == 413:
            return "That file is larger than the 50 MiB limit."
        if status == 422 and detail == "File is empty":
            return "That file is empty."
        if status == 422:
            return detail or "Invalid input."
    return "Something went wrong. Please try again."


def _error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return ""
    if isinstance(payload, dict):
        detail = payload.get("detail", "")
        return detail if isinstance(detail, str) else str(detail)
    return ""


class ApiClient:
    def __init__(self, base_url: str, transport: httpx.BaseTransport | None = None,
                 timeout: tuple[float, float] = (5.0, 60.0)):
        self._client = httpx.Client(
            base_url=base_url, transport=transport, timeout=timeout
        )

    def close(self) -> None:
        self._client.close()

    @staticmethod
    def _headers(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def _check(self, response: httpx.Response) -> httpx.Response:
        if response.status_code >= 400:
            raise ApiError(response.status_code, _error_detail(response))
        return response

    def _handle(self, method: str, path: str, *, token: str | None = None, **kwargs):
        try:
            headers = self._headers(token) if token else None
            if headers:
                kwargs["headers"] = {**kwargs.get("headers", {}), **headers}
            response = self._client.request(method, path, **kwargs)
        except httpx.HTTPError:
            raise ApiError(0, "backend unreachable") from None
        return self._check(response)

    # --- auth -----------------------------------------------------------

    def register(self, email: str, password: str) -> dict:
        return self._handle(
            "POST", "/auth/register", json={"email": email, "password": password}
        ).json()

    def login(self, email: str, password: str) -> dict:
        """Returns {access_token, token_type, expires_in}."""
        return self._handle(
            "POST", "/auth/login", json={"email": email, "password": password}
        ).json()

    def me(self, token: str) -> dict:
        return self._handle("GET", "/auth/me", token=token).json()

    # --- documents ------------------------------------------------------

    def list_documents(self, token: str, *, search: str = "", sort: str = "",
                       order: str = "", file_type: str = "") -> list[dict]:
        params = {
            k: v
            for k, v in {
                "search": search, "sort": sort, "order": order, "file_type": file_type,
            }.items()
            if v
        }
        return self._handle("GET", "/documents", token=token, params=params).json()

    def usage(self, token: str) -> dict:
        return self._handle("GET", "/documents/usage", token=token).json()

    def upload(self, token: str, file_path: Path) -> dict:
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        with open(file_path, "rb") as fh:
            return self._handle(
                "POST",
                "/documents",
                token=token,
                files={"file": (file_path.name, fh, content_type)},
            ).json()

    def download_to_file(self, token: str, document_id: str, dest: Path) -> Path:
        """Stream an authenticated download into a temp file, then atomically
        move it to dest. A failed download never leaves a partial file."""
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=dest.parent, prefix=".dl-", suffix=".part")
        try:
            with os.fdopen(fd, "wb") as tmp:
                try:
                    with self._client.stream(
                        "GET", f"/documents/{document_id}", headers=self._headers(token)
                    ) as response:
                        if response.status_code >= 400:
                            detail = _error_detail(response)
                            raise ApiError(response.status_code, detail)
                        for chunk in response.iter_bytes(DOWNLOAD_CHUNK):
                            tmp.write(chunk)
                except httpx.HTTPError:
                    raise ApiError(0, "backend unreachable") from None
            os.replace(tmp_name, dest)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise
        return dest

    def rename(self, token: str, document_id: str, filename: str) -> dict:
        return self._handle(
            "PATCH", f"/documents/{document_id}", token=token,
            json={"filename": filename},
        ).json()

    def delete(self, token: str, document_id: str) -> None:
        self._handle("DELETE", f"/documents/{document_id}", token=token)
