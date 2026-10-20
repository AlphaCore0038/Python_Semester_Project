"""Views for the Django web client.

All application operations are proxied to FastAPI via
``fastapi_client``. Django stores only the FastAPI JWT in the
server-side session; it never renders the token into HTML, URLs, or
JavaScript, and it never contacts Supabase directly.
"""
from django.conf import settings
from django.contrib import messages
from django.http import StreamingHttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from . import fastapi_client
from .forms import LoginForm, RegisterForm, RenameForm

# FastAPI 413 detail strings (exact backend contract).
DETAIL_TOO_LARGE = "File exceeds the maximum upload size"
DETAIL_QUOTA = "Storage quota exceeded"


def _login_redirect(request, note="Please log in to continue."):
    if note:
        messages.info(request, note)
    return redirect(reverse("locker:login"))


def _session_expired(request):
    """401 on an authenticated call: clear auth state and go to login."""
    request.session.flush()
    messages.warning(request, "Your session has expired. Please log in again.")
    return redirect(reverse("locker:login"))


def _authed_request(request, fn, *args, **kwargs):
    """Run an authenticated client call; returns (result, error_response).

    On success error_response is None; otherwise it is the redirect to
    send (session expired, not found, or a safe generic message).
    """
    token = request.session.get("api_token")
    if not token:
        return None, _login_redirect(request)
    try:
        return fn(token, *args, **kwargs), None
    except fastapi_client.FastAPIError as exc:
        if exc.status_code in (0, 401, 404):
            return None, _auth_failure(request, exc)
        messages.error(request, "Something went wrong. Please try again.")
        return None, redirect("locker:dashboard")


def _auth_failure(request, exc):
    if exc.status_code == 0:
        messages.error(request, "Cannot reach the service right now. Please try again.")
        return redirect("locker:dashboard")
    if exc.status_code == 401:
        return _session_expired(request)
    messages.error(request, "Document not found.")
    return redirect("locker:dashboard")


@require_http_methods(["GET", "POST"])
def register_view(request):
    if request.session.get("api_token"):
        return redirect("locker:dashboard")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            fastapi_client.register(
                form.cleaned_data["email"].strip().lower(),
                form.cleaned_data["password"],
            )
        except fastapi_client.FastAPIError as exc:
            if exc.status_code == 409:
                form.add_error("email", "An account with this email already exists.")
            elif exc.status_code == 422:
                form.add_error(None, "Please check your email and password.")
            elif exc.status_code == 0:
                form.add_error(None, "Cannot reach the service right now. Please try again.")
            else:
                form.add_error(None, "Registration is unavailable right now. Please try again.")
        else:
            # Registration succeeded: automatic login.
            return _start_session(
                request,
                form.cleaned_data["email"].strip().lower(),
                form.cleaned_data["password"],
                success_note="Account created. Welcome!",
            )
    return render(request, "locker/register.html", {"form": form})


def _start_session(request, email, password, success_note=None):
    """Login via FastAPI, rotate the session key (fixation defense), and
    store the JWT server-side."""
    try:
        data = fastapi_client.login(email, password)
    except fastapi_client.FastAPIError as exc:
        messages.error(
            request,
            "Cannot reach the service right now. Please try again."
            if exc.status_code == 0
            else "Incorrect email or password.",
        )
        return redirect(reverse("locker:login"))
    request.session.cycle_key()
    request.session["api_token"] = data["access_token"]
    request.session["api_email"] = email
    request.session.modified = True
    if success_note:
        messages.success(request, success_note)
    return redirect("locker:dashboard")


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.session.get("api_token"):
        return redirect("locker:dashboard")
    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        return _start_session(
            request,
            form.cleaned_data["email"].strip().lower(),
            form.cleaned_data["password"],
        )
    return render(request, "locker/login.html", {"form": form})


@require_POST
def logout_view(request):
    request.session.flush()
    messages.info(request, "You have been logged out.")
    return redirect(reverse("locker:login"))


@require_http_methods(["GET"])
def dashboard(request):
    token = request.session.get("api_token")
    if not token:
        return _login_redirect(request, note=None)

    usage = None
    docs = []
    try:
        usage = fastapi_client.usage(token)
        docs = fastapi_client.list_documents(
            token,
            search=request.GET.get("search", ""),
            sort=request.GET.get("sort", ""),
            order=request.GET.get("order", ""),
            file_type=request.GET.get("file_type", ""),
        )
    except fastapi_client.FastAPIError as exc:
        if exc.status_code == 401:
            return _session_expired(request)
        if exc.status_code == 422:
            messages.error(request, "Invalid search or sort options.")
        else:
            messages.error(
                request,
                "Cannot reach the service right now. Please try again."
                if exc.status_code == 0
                else "Could not load your documents. Please try again.",
            )

    return render(
        request,
        "locker/dashboard.html",
        {
            "usage": usage,
            "documents": docs,
            "email": request.session.get("api_email", ""),
            "max_upload_bytes": settings.MAX_UPLOAD_BYTES,
            "query": {
                "search": request.GET.get("search", ""),
                "sort": request.GET.get("sort", ""),
                "order": request.GET.get("order", ""),
                "file_type": request.GET.get("file_type", ""),
            },
        },
    )


@require_POST
def upload(request):
    token = request.session.get("api_token")
    if not token:
        return _login_redirect(request)

    uploaded = request.FILES.get("file")
    if uploaded is None:
        messages.error(request, "Choose a file to upload.")
        return redirect("locker:dashboard")
    # UI convenience pre-check only; FastAPI enforces the real limit.
    if uploaded.size > settings.MAX_UPLOAD_BYTES:
        messages.error(request, "That file is larger than the 50 MiB limit.")
        return redirect("locker:dashboard")

    try:
        doc = fastapi_client.upload(token, uploaded)
    except fastapi_client.FastAPIError as exc:
        status, detail = exc.status_code, exc.detail
        if status == 401:
            return _session_expired(request)
        if status == 413 and detail == DETAIL_QUOTA:
            messages.error(
                request, "Storage quota reached (500 MB). Delete files to free space."
            )
        elif status == 413:
            messages.error(request, "That file is larger than the 50 MiB limit.")
        elif status == 422 and detail == "File is empty":
            messages.error(request, "That file is empty.")
        elif status == 422:
            messages.error(request, "That file name is not allowed.")
        elif status == 0:
            messages.error(request, "Cannot reach the service right now. Please try again.")
        else:
            messages.error(request, "Upload failed. Please try again.")
        return redirect("locker:dashboard")

    messages.success(request, f'Uploaded "{doc["filename"]}".')
    return redirect("locker:dashboard")


def download(request, document_id):
    token = request.session.get("api_token")
    if not token:
        return _login_redirect(request)

    try:
        upstream = fastapi_client.download(token, str(document_id))
    except fastapi_client.FastAPIError as exc:
        return _auth_failure(request, exc)

    def stream():
        try:
            yield from upstream.iter_content(64 * 1024)
        finally:
            upstream.close()

    headers = {}
    content_disposition = upstream.headers.get("Content-Disposition")
    if content_disposition:
        headers["Content-Disposition"] = content_disposition
    return StreamingHttpResponse(
        stream(),
        content_type=upstream.headers.get("Content-Type", "application/octet-stream"),
        headers=headers,
    )


@require_http_methods(["GET", "POST"])
def rename(request, document_id):
    token = request.session.get("api_token")
    if not token:
        return _login_redirect(request)

    if request.method == "GET":
        form = RenameForm(initial={"filename": request.GET.get("filename", "")})
        return render(
            request,
            "locker/rename.html",
            {"form": form, "document_id": document_id},
        )

    form = RenameForm(request.POST)
    if form.is_valid():
        try:
            fastapi_client.rename(token, str(document_id), form.cleaned_data["filename"])
        except fastapi_client.FastAPIError as exc:
            if exc.status_code == 401:
                return _session_expired(request)
            if exc.status_code == 404:
                messages.error(request, "Document not found.")
                return redirect("locker:dashboard")
            if exc.status_code == 422:
                form.add_error("filename", "That name is not allowed.")
            else:
                messages.error(
                    request,
                    "Cannot reach the service right now. Please try again."
                    if exc.status_code == 0
                    else "Rename failed. Please try again.",
                )
        else:
            messages.success(request, "Document renamed.")
            return redirect("locker:dashboard")
    return render(
        request, "locker/rename.html", {"form": form, "document_id": document_id}
    )


@require_http_methods(["GET", "POST"])
def delete_confirm(request, document_id):
    """GET shows the confirmation page; only the POST actually deletes."""
    token = request.session.get("api_token")
    if not token:
        return _login_redirect(request)

    if request.method == "GET":
        return render(
            request, "locker/delete_confirm.html", {"document_id": document_id}
        )

    try:
        fastapi_client.delete(token, str(document_id))
    except fastapi_client.FastAPIError as exc:
        if exc.status_code == 401:
            return _session_expired(request)
        if exc.status_code == 404:
            messages.error(request, "Document not found (it may already be deleted).")
        elif exc.status_code == 0:
            messages.error(request, "Cannot reach the service right now. Please try again.")
        else:
            messages.error(request, "Delete failed. Please try again.")
        return redirect("locker:dashboard")

    messages.success(request, "Document deleted.")
    return redirect("locker:dashboard")
