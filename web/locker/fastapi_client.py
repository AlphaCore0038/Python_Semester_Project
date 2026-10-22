"""Single point of contact between the Django web client and FastAPI.

Every FastAPI call in the web client goes through this module. Django
never talks to Supabase directly and never handles service-role keys.
The session token is supplied by the view from the server-side session; it
is never rendered into HTML, URLs, or browser JavaScript.
"""
import requests
from django.conf import settings

# Requests timeout: (connect, read) seconds. Kept short so a dead backend
# surfaces as a friendly message instead of a hung page.
TIMEOUT = (5, 15)
# AI calls wait on the model; must not time out before the backend's own
# OpenRouter read timeout (90 s).
AI_TIMEOUT = (5, 90)


class FastAPIError(Exception):
    """Normalized error from the FastAPI backend.

    status_code == 0 means the backend was unreachable (network error).
    detail carries the backend's JSON `detail` string when available.
    """

    def __init__(self, status_code, detail=""):
        super().__init__(detail or str(status_code))
        self.status_code = status_code
        self.detail = detail


def _url(path):
    return settings.FASTAPI_BASE_URL.rstrip("/") + path


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _detail(resp):
    try:
        payload = resp.json()
    except ValueError:
        return ""
    if isinstance(payload, dict):
        detail = payload.get("detail", "")
        return detail if isinstance(detail, str) else str(detail)
    return ""


def _call(method, path, *, token=None, json=None, files=None, params=None,
          stream=False, timeout=None):
    try:
        resp = requests.request(
            method,
            _url(path),
            headers=_headers(token) if token else None,
            json=json,
            files=files,
            params=params,
            stream=stream,
            timeout=timeout or TIMEOUT,
        )
    except requests.RequestException:
        raise FastAPIError(0, "backend unreachable") from None
    if resp.status_code >= 400:
        if stream:
            detail = _detail(resp)
            resp.close()
            raise FastAPIError(resp.status_code, detail)
        raise FastAPIError(resp.status_code, _detail(resp))
    return resp


def register(email, password):
    _call("POST", "/auth/register", json={"email": email, "password": password})


def login(email, password):
    """Returns the JSON body: {access_token, token_type, expires_in}."""
    return _call("POST", "/auth/login", json={"email": email, "password": password}).json()


def me(token):
    """Current user profile: {id, email, is_admin, created_at}."""
    return _call("GET", "/auth/me", token=token).json()


def logout(token):
    """Invalidate the server-side session (best effort at the view)."""
    _call("POST", "/auth/logout", token=token)


def list_documents(token, *, search="", sort="", order="", file_type=""):
    params = {
        k: v
        for k, v in {
            "search": search,
            "sort": sort,
            "order": order,
            "file_type": file_type,
        }.items()
        if v
    }
    return _call("GET", "/documents", token=token, params=params).json()


def usage(token):
    return _call("GET", "/documents/usage", token=token).json()


def upload(token, uploaded_file):
    """Multipart upload of a Django UploadedFile; returns the document JSON."""
    return _call("POST", "/documents", token=token, files={"file": uploaded_file}).json()


def download(token, document_id):
    """Streams a download; caller must close() the response when done."""
    return _call("GET", f"/documents/{document_id}", token=token, stream=True)


def rename(token, document_id, filename):
    return _call(
        "PATCH", f"/documents/{document_id}", token=token, json={"filename": filename}
    ).json()


def delete(token, document_id):
    _call("DELETE", f"/documents/{document_id}", token=token)


def admin_users(token):
    return _call("GET", "/admin/users", token=token).json()


def admin_documents(token):
    return _call("GET", "/admin/documents", token=token).json()


def admin_download(token, document_id):
    """Streams another user's document; caller must close() the response."""
    return _call("GET", f"/admin/documents/{document_id}", token=token, stream=True)


def ai_status(token):
    return _call("GET", "/ai/status", token=token, timeout=AI_TIMEOUT).json()


def ai_ask(token, question):
    return _call(
        "POST", "/ai/ask", token=token, json={"question": question},
        timeout=AI_TIMEOUT,
    ).json()


def ai_summarize(token, document_id):
    return _call(
        "POST", "/ai/summarize", token=token, json={"document_id": document_id},
        timeout=AI_TIMEOUT,
    ).json()


def ai_suggest_filename(token, document_id):
    return _call(
        "POST", "/ai/suggest-filename", token=token,
        json={"document_id": document_id}, timeout=AI_TIMEOUT,
    ).json()
