"""Authentication routes: register, login, current-user profile."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app import db
from app.config import get_settings
from app.deps import get_current_user
from app.schemas import LoginRequest, RegisterRequest, RegisterResponse, TokenResponse, UserResponse
from app.security import create_access_token, hash_password, verify_password

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
    token = create_access_token(str(user["id"]), user["email"])
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.jwt_expiry_minutes * 60,
    )


@router.get("/me", response_model=UserResponse)
def read_me(current_user: dict = Depends(get_current_user)) -> UserResponse:
    return UserResponse(
        id=str(current_user["id"]),
        email=current_user["email"],
        is_admin=bool(current_user["is_admin"]),
        created_at=str(current_user["created_at"]),
    )
