# web/locker/views.py: Tkinter UI views and layout.
"""Views for the Django web client.

All application operations are proxied to FastAPI via
``fastapi_client``. Django stores only the FastAPI session token in the
server-side session; it never renders the token into HTML, URLs, or
JavaScript, and it never contacts Supabase directly.
"""
from datetime import datetime, timezone

from django.conf import settings
from django.contrib import messages
from django.http import StreamingHttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from . import fastapi_client
from .forms import LoginForm, RegisterForm, RenameForm

                                                      
DETAIL_TOO_LARGE = "File exceeds the maximum upload size"
DETAIL_QUOTA = "Storage quota exceeded"


def _format_utc(value):
    """Format an API ISO-8601 timestamp for display; never raises.

    Django's ``date`` filter returns an empty string for raw JSON strings,
    so timestamps are parsed here. Missing or malformed values render as
    an em dash instead of breaking the page.
    """
    if not isinstance(value, str) or not value:
        return "\u2014"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return "\u2014"
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc)
    return parsed.strftime("%Y-%m-%d %H:%M UTC")


def _add_display_times(rows, fields=("created_at",)):
    for row in rows or []:
        for field in fields:
            row[f"{field}_display"] = _format_utc(row.get(field))
    return rows


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
                                                      
            return _start_session(
                request,
                form.cleaned_data["email"].strip().lower(),
                form.cleaned_data["password"],
                success_note="Account created. Welcome!",
            )
    return render(request, "locker/register.html", {"form": form})


def _start_session(request, email, password, success_note=None):
    """Login via FastAPI, rotate the session key (fixation defense), and
    store the opaque session token server-side."""
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
                                                                    
                                                                 
    try:
        profile = fastapi_client.me(data["access_token"])
    except fastapi_client.FastAPIError:
        profile = {}
    request.session["api_is_admin"] = bool(profile.get("is_admin"))
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
    token = request.session.get("api_token")
    if token:
                                                                          
                                                        
        try:
            fastapi_client.logout(token)
        except fastapi_client.FastAPIError:
            pass
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
    except fastapi_client.FastAPIError as exc:
        if exc.status_code == 401:
            return _session_expired(request)

    try:
        docs = _add_display_times(
            fastapi_client.list_documents(
                token,
                search=request.GET.get("search", ""),
                sort=request.GET.get("sort", ""),
                order=request.GET.get("order", ""),
                file_type=request.GET.get("file_type", ""),
            )
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

    usage_percent = 0
    usage_remaining = None
    if usage and usage.get("quota_bytes"):
        used = usage.get("used_bytes", 0)
        quota = usage["quota_bytes"]
        usage_percent = min(100, round(used / quota * 100))
        usage_remaining = max(0, quota - used)

    return render(
        request,
        "locker/dashboard.html",
        {
            "usage": usage,
            "usage_percent": usage_percent,
            "usage_remaining": usage_remaining,
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


def _stream_response(upstream):
    """Proxy a streamed FastAPI download without buffering it in memory."""
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


def download(request, document_id):
    token = request.session.get("api_token")
    if not token:
        return _login_redirect(request)

    try:
        upstream = fastapi_client.download(token, str(document_id))
    except fastapi_client.FastAPIError as exc:
        return _auth_failure(request, exc)

    return _stream_response(upstream)


@require_http_methods(["GET"])
def admin_dashboard(request):
    """Read-only admin overview of all users and documents (spec 14.1)."""
    token = request.session.get("api_token")
    if not token:
        return _login_redirect(request)

    try:
        users = _add_display_times(fastapi_client.admin_users(token))
        documents = _add_display_times(
            fastapi_client.admin_documents(token), ("created_at", "updated_at")
        )
    except fastapi_client.FastAPIError as exc:
        if exc.status_code == 401:
            return _session_expired(request)
        if exc.status_code == 403:
            request.session["api_is_admin"] = False
            messages.error(request, "Administrator access is required.")
        elif exc.status_code == 0:
            messages.error(request, "Cannot reach the service right now. Please try again.")
        else:
            messages.error(request, "Could not load the admin dashboard. Please try again.")
        return redirect("locker:dashboard")

    return render(
        request,
        "locker/admin.html",
        {"users": users, "documents": documents},
    )


def admin_download(request, document_id):
    """Audited admin download, proxied through FastAPI."""
    token = request.session.get("api_token")
    if not token:
        return _login_redirect(request)

    try:
        upstream = fastapi_client.admin_download(token, str(document_id))
    except fastapi_client.FastAPIError as exc:
        if exc.status_code == 401:
            return _session_expired(request)
        if exc.status_code == 403:
            request.session["api_is_admin"] = False
            messages.error(request, "Administrator access is required.")
        elif exc.status_code == 404:
            messages.error(request, "Document not found.")
        elif exc.status_code == 0:
            messages.error(request, "Cannot reach the service right now. Please try again.")
        else:
            messages.error(request, "Download failed. Please try again.")
        return redirect("locker:admin_dashboard")

    return _stream_response(upstream)


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


@require_http_methods(["GET", "POST"])
def ai(request):
    """AI assistant page (spec 13): ask, summarize, suggest filename.

    Suggested filenames are proposals only - applying one goes through the
    existing rename confirmation page with its own validation.
    """
    token = request.session.get("api_token")
    if not token:
        return _login_redirect(request)

    context = {"result": None, "ai_status": None, "documents": []}
    try:
        context["ai_status"] = fastapi_client.ai_status(token)
        context["documents"] = fastapi_client.list_documents(token)
    except fastapi_client.FastAPIError as exc:
        if exc.status_code == 401:
            return _session_expired(request)
        messages.error(
            request,
            "Cannot reach the service right now. Please try again."
            if exc.status_code == 0
            else "AI is unavailable right now. Please try again.",
        )
        return redirect("locker:dashboard")

    if request.method == "POST":
        action = request.POST.get("action", "")
        document_id = request.POST.get("document_id", "")
        try:
            if action == "ask":
                question = request.POST.get("question", "").strip()
                if not question:
                    messages.error(request, "Type a question first.")
                else:
                    context["result"] = {
                        "kind": "ask",
                        "data": fastapi_client.ai_ask(token, question),
                    }
            elif action == "summarize":
                context["result"] = {
                    "kind": "summarize",
                    "data": fastapi_client.ai_summarize(token, document_id),
                }
            elif action == "suggest":
                context["result"] = {
                    "kind": "suggest",
                    "document_id": document_id,
                    "data": fastapi_client.ai_suggest_filename(token, document_id),
                }
        except fastapi_client.FastAPIError as exc:
            if exc.status_code == 401:
                return _session_expired(request)
            if exc.status_code == 404:
                messages.error(request, "Document not found.")
            elif exc.status_code == 422:
                messages.error(request, exc.detail or "The AI could not process that.")
            elif exc.status_code == 503:
                messages.error(
                    request, exc.detail or "The AI is unavailable right now."
                )
            elif exc.status_code == 0:
                messages.error(request, "Cannot reach the service right now.")
            else:
                messages.error(request, "The AI request failed. Please try again.")

    return render(request, "locker/ai.html", context)
