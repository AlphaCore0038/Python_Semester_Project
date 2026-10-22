"""Password hashing (bcrypt) and opaque session tokens."""

from __future__ import annotations

import hashlib
import secrets

import bcrypt

# bcrypt silently truncates inputs at 72 bytes; we reject oversize passwords
# at validation time instead of ever truncating them here.
BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def new_session_token() -> str:
    """Return a cryptographically random, URL-safe opaque token."""
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    """Hash a session token for at-rest storage and lookup."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
