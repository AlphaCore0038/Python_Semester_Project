# backend/app/security.py: Security and password hashing helpers.
"""Password hashing (PBKDF2) and opaque session tokens."""

from __future__ import annotations

import hashlib
import hmac
import secrets

import bcrypt

PBKDF2_ALGORITHM = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 600_000
PBKDF2_SALT_BYTES = 16
PBKDF2_DERIVED_KEY_BYTES = 32
_BCRYPT_PREFIXES = ("$2a$", "$2b$", "$2y$")

                                                                           
                                                              
MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(PBKDF2_SALT_BYTES)
    derived_key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
        dklen=PBKDF2_DERIVED_KEY_BYTES,
    )
    return (
        f"{PBKDF2_ALGORITHM}${PBKDF2_ITERATIONS}$"
        f"{salt.hex()}${derived_key.hex()}"
    )


def verify_password(password: str, password_hash: str) -> bool:
    if password_hash.startswith(_BCRYPT_PREFIXES):
        try:
            return bcrypt.checkpw(
                password.encode("utf-8"), password_hash.encode("utf-8")
            )
        except ValueError:
            return False

    try:
        algorithm, iterations, salt_hex, derived_key_hex = password_hash.split("$")
        if algorithm != PBKDF2_ALGORITHM or int(iterations) != PBKDF2_ITERATIONS:
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(derived_key_hex)
    except (TypeError, ValueError):
        return False

    if (
        len(salt) != PBKDF2_SALT_BYTES
        or len(expected) != PBKDF2_DERIVED_KEY_BYTES
    ):
        return False
    actual = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
        dklen=PBKDF2_DERIVED_KEY_BYTES,
    )
    return hmac.compare_digest(actual, expected)


def needs_rehash(password_hash: str) -> bool:
    return not password_hash.startswith(
        f"{PBKDF2_ALGORITHM}${PBKDF2_ITERATIONS}$"
    )


def new_session_token() -> str:
    """Return a cryptographically random, URL-safe opaque token."""
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    """Hash a session token for at-rest storage and lookup."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
