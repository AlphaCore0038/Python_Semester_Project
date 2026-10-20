"""Shared Pydantic request/response schemas (Phase 4: auth)."""

from __future__ import annotations

import re

from pydantic import BaseModel, field_validator

from app.security import BCRYPT_MAX_BYTES

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _normalize_email(value: str) -> str:
    email = value.strip().lower()
    if not _EMAIL_RE.match(email):
        raise ValueError("Invalid email address")
    return email


def _validate_password(value: str) -> str:
    if len(value) < 8:
        raise ValueError("Password must be at least 8 characters")
    size = len(value.encode("utf-8"))
    if size > BCRYPT_MAX_BYTES:
        raise ValueError(
            f"Password must be at most {BCRYPT_MAX_BYTES} bytes when encoded as UTF-8"
        )
    return value


class RegisterRequest(BaseModel):
    # extra fields (e.g. is_admin) are silently ignored, never honored
    email: str
    password: str

    _normalize_email_field = field_validator("email")(_normalize_email)
    _validate_password_field = field_validator("password")(_validate_password)


class LoginRequest(BaseModel):
    email: str
    password: str

    _normalize_email_field = field_validator("email")(_normalize_email)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: str
    email: str
    is_admin: bool
    created_at: str


class RegisterResponse(BaseModel):
    id: str
    email: str
