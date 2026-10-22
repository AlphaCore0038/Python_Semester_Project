"""Authentication routes: register, login, current-user profile, logout."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

from app import db
from app.config import get_settings
from app.deps import get_current_user, oauth2_scheme
from app.schemas import LoginRequest, RegisterRequest, RegisterResponse, TokenResponse, UserResponse
from app.security import (
    hash_password,
    hash_session_token,
    new_session_token,
    verify_password,
)

router = APIRouter(tags=["auth"])

# Lazily computed dummy hash so unknown-email logins take comparable time.
_DUMMY_HASH: str | None = None


def _dummy_hash() -> str:
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hash_password("timing-equalization-dummy")
    return _DUMMY_HASH


@router.post("/register", status_code=201, response_model=RegisterResponse)
def register(payload: RegisterRequest) -> RegisterResponse:
    if db.get_user_by_email(payload.email) is not None:
        raise HTTPException(status_code=409, detail="Email already registered")
    try:
        user = db.create_user(payload.email, hash_password(payload.password))
    except db.DuplicateEmailError:
        raise HTTPException(status_code=409, detail="Email already registered") from None
    return RegisterResponse(id=str(user["id"]), email=user["email"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    user = db.get_user_by_email(payload.email)
    if user is None:
        verify_password(payload.password, _dummy_hash())
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    settings = get_settings()
    raw_token = new_session_token()
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.session_expiry_minutes
    )
    db.create_session(
        hash_session_token(raw_token), str(user["id"]), expires_at.isoformat()
    )
    return TokenResponse(
        access_token=raw_token,
        token_type="bearer",
        expires_in=settings.session_expiry_minutes * 60,
    )


@router.post("/logout", status_code=204)
def logout(token: str = Depends(oauth2_scheme)) -> None:
    db.delete_session(hash_session_token(token))


@router.get("/me", response_model=UserResponse)
def read_me(current_user: dict = Depends(get_current_user)) -> UserResponse:
    return UserResponse(
        id=str(current_user["id"]),
        email=current_user["email"],
        is_admin=bool(current_user["is_admin"]),
        created_at=str(current_user["created_at"]),
    )
