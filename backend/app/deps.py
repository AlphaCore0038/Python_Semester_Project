"""Authentication dependency: validates the Bearer JWT and resolves the user."""

from __future__ import annotations

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

from app import db
from app.security import AuthError, decode_access_token, parse_user_subject

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=401, detail=detail, headers={"WWW-Authenticate": "Bearer"}
    )


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        payload = decode_access_token(token)
        user_id = parse_user_subject(payload.get("sub"))  # UUID validated here
    except AuthError as exc:
        raise _unauthorized(str(exc)) from exc
    user = db.get_user_by_id(user_id)
    if user is None:
        raise _unauthorized("Invalid token")
    return user


def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Administrator gate.

    Admin status comes from the fresh per-request database row resolved by
    get_current_user - never from the JWT, query parameters, headers, or
    client state. A failed lookup cannot reach this check, so it can never
    grant access.
    """
    if not current_user.get("is_admin"):
        raise HTTPException(
            status_code=403, detail="Administrator access required"
        )
    return current_user
