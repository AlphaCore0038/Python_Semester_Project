"""Authentication dependency: validates the Bearer session token and resolves
the user."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

from app import db
from app.security import hash_session_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=401, detail=detail, headers={"WWW-Authenticate": "Bearer"}
    )


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    session = db.get_session(hash_session_token(token))
    if session is None:
        raise _unauthorized("Invalid token")

    try:
        expires_at = datetime.fromisoformat(
            str(session["expires_at"]).replace("Z", "+00:00")
        )
    except ValueError:
        raise _unauthorized("Invalid token") from None
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        raise _unauthorized("Token expired")

    user = db.get_user_by_id(str(session["user_id"]))
    if user is None:
        raise _unauthorized("Invalid token")
    return user


def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Administrator gate.

    Admin status comes from the fresh per-request database row resolved by
    get_current_user - never from the session token, query parameters, headers,
    or client state. A failed lookup cannot reach this check, so it can never
    grant access.
    """
    if not current_user.get("is_admin"):
        raise HTTPException(
            status_code=403, detail="Administrator access required"
        )
    return current_user
