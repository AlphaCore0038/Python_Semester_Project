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
