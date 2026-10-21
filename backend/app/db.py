"""Thin users-table access via the server-side Supabase client (Phase 4).

All functions run with the service-role key inside the backend only.
Authorization decisions live in FastAPI, never in the client.
"""

from __future__ import annotations

from postgrest.exceptions import APIError

from app.supabase_client import get_supabase

_USER_COLUMNS = "id, email, password_hash, is_admin, created_at"


class DuplicateEmailError(Exception):
    """Raised when the unique index on lower(email) rejects an insert."""


def create_user(email: str, password_hash: str) -> dict:
    # Only these two columns are ever sent: is_admin takes its DB default (false)
    # and id/created_at are database-generated.
    try:
        response = (
            get_supabase()
            .table("users")
            .insert({"email": email, "password_hash": password_hash})
            .execute()
        )
    except APIError as exc:
        raise DuplicateEmailError() from exc
    return response.data[0]


def get_user_by_email(email: str) -> dict | None:
    # Emails are canonicalized to lowercase by the API layer, matching the
    # users_email_lower_key unique index.
    response = (
        get_supabase()
        .table("users")
        .select(_USER_COLUMNS)
        .eq("email", email)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def get_user_by_id(user_id: str) -> dict | None:
    response = (
        get_supabase()
        .table("users")
        .select(_USER_COLUMNS)
        .eq("id", user_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def set_user_admin(user_id: str) -> bool:
    """Promote exactly one existing user row; owner-run bootstrap only."""
    response = (
        get_supabase()
        .table("users")
        .update({"is_admin": True})
        .eq("id", user_id)
        .execute()
    )
    return bool(response.data)


def list_users() -> list[dict]:
    """Admin listing only; selects non-secret columns in registration order."""
    response = (
        get_supabase()
        .table("users")
        .select("id, email, is_admin, created_at")
        .order("created_at", desc=False)
        .execute()
    )
    return response.data or []


# --- documents (Phase 5) ---

_DOCUMENT_COLUMNS = (
    "id, user_id, filename, storage_path, file_type, file_size_bytes, created_at, updated_at"
)

# Allowlisted sort columns; never interpolate client input into query builders.
DOCUMENT_SORT_COLUMNS = frozenset({"created_at", "filename", "file_size_bytes"})


def create_document(row: dict) -> dict:
    response = get_supabase().table("documents").insert(row).execute()
    return response.data[0]


def get_document(document_id: str, user_id: str) -> dict | None:
    response = (
        get_supabase()
        .table("documents")
        .select(_DOCUMENT_COLUMNS)
        .eq("id", document_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def list_documents(
    user_id: str,
    *,
    search: str | None = None,
    sort: str = "created_at",
    order: str = "desc",
    file_type: str | None = None,
) -> list[dict]:
    query = (
        get_supabase()
        .table("documents")
        .select(_DOCUMENT_COLUMNS)
        .eq("user_id", user_id)
    )
    if search:
        query = query.ilike("filename", f"%{search}%")
    if file_type:
        query = query.eq("file_type", file_type)
    column = sort if sort in DOCUMENT_SORT_COLUMNS else "created_at"
    query = query.order(column, desc=(order == "desc"))
    return query.execute().data or []


def update_filename(document_id: str, user_id: str, filename: str) -> dict | None:
    response = (
        get_supabase()
        .table("documents")
        .update({"filename": filename})
        .eq("id", document_id)
        .eq("user_id", user_id)
        .execute()
    )
    return response.data[0] if response.data else None


def delete_document(document_id: str, user_id: str) -> bool:
    response = (
        get_supabase()
        .table("documents")
        .delete()
        .eq("id", document_id)
        .eq("user_id", user_id)
        .execute()
    )
    return bool(response.data)


def list_documents_admin() -> list[dict]:
    """Admin listing across all users; newest first (same default as users)."""
    response = (
        get_supabase()
        .table("documents")
        .select(_DOCUMENT_COLUMNS)
        .order("created_at", desc=True)
        .execute()
    )
    return response.data or []


def get_document_admin(document_id: str) -> dict | None:
    """Admin lookup across users; intentionally not scoped by user_id."""
    response = (
        get_supabase()
        .table("documents")
        .select(_DOCUMENT_COLUMNS)
        .eq("id", document_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def sum_usage_and_count(user_id: str) -> tuple[int, int]:
    """Trusted per-user usage from database metadata (never client-supplied)."""
    response = (
        get_supabase()
        .table("documents")
        .select("file_size_bytes")
        .eq("user_id", user_id)
        .execute()
    )
    rows = response.data or []
    return sum(int(row["file_size_bytes"]) for row in rows), len(rows)
