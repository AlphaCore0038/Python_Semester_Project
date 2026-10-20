"""Password hashing (bcrypt) and JWT access tokens (HS256) — Phase 4."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import get_settings

# bcrypt silently truncates inputs at 72 bytes; we reject oversize passwords
# at validation time instead of ever truncating them here.
BCRYPT_MAX_BYTES = 72


class AuthError(Exception):
    """Token validation failure. Message is safe to show to the caller."""


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(
    user_id: str, email: str, expires_delta: timedelta | None = None
) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.jwt_expiry_minutes)
    )
    payload = {"sub": user_id, "email": email, "iat": now, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Token expired") from exc
    except jwt.PyJWTError as exc:
        raise AuthError("Invalid token") from exc


def parse_user_subject(sub: object) -> str:
    """Validate the token subject is a UUID before any database lookup."""
    try:
        return str(uuid.UUID(str(sub)))
    except (ValueError, AttributeError, TypeError) as exc:
        raise AuthError("Invalid token") from exc
