"""Shared Pydantic request/response schemas (Phase 4: auth, Phase 5: documents)."""

from __future__ import annotations

import re

from pydantic import BaseModel, field_validator

from app.security import MAX_PASSWORD_BYTES

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_CONTENT_TYPE_RE = re.compile(r"^[\w.+-]+/[\w.+-]+$")


def _normalize_email(value: str) -> str:
    email = value.strip().lower()
    if not _EMAIL_RE.match(email):
        raise ValueError("Invalid email address")
    return email


def _validate_password(value: str) -> str:
    if len(value) < 8:
        raise ValueError("Password must be at least 8 characters")
    size = len(value.encode("utf-8"))
    if size > MAX_PASSWORD_BYTES:
        raise ValueError(
            f"Password must be at most {MAX_PASSWORD_BYTES} bytes when encoded as UTF-8"
        )
    return value


def validate_filename(value: str) -> str:
    """Strict filename validation: reject invalid names, never transform them."""
    name = value.strip()
    if not name or len(name) > 255:
        raise ValueError("Filename must be 1-255 characters")
    if name in {".", ".."}:
        raise ValueError("Invalid filename")
    if any(ord(char) < 32 for char in name):
        raise ValueError("Filename must not contain control characters")
    if "/" in name or "\\" in name:
        raise ValueError("Filename must not contain path separators")
    return name


def sanitize_content_type(value: str | None) -> str:
    if value and _CONTENT_TYPE_RE.match(value.strip()):
        return value.strip()
    return "application/octet-stream"


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


class DocumentResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    file_size_bytes: int
    created_at: str
    updated_at: str


class RenameRequest(BaseModel):
    filename: str

    _validate_filename_field = field_validator("filename")(validate_filename)


class UsageResponse(BaseModel):
    used_bytes: int
    quota_bytes: int
    document_count: int


class AskRequest(BaseModel):
    question: str

    @field_validator("question")
    @classmethod
    def _check_question(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("Question must not be empty")
        if len(text) > 1000:
            raise ValueError("Question must be at most 1000 characters")
        return text


class DocumentIdRequest(BaseModel):
    document_id: str


class DocumentSource(BaseModel):
    document_id: str
    filename: str


class AIStatusResponse(BaseModel):
    configured: bool
    provider: str
    model: str
    local_ai: str


class AskResponse(BaseModel):
    answer: str
    sources: list[DocumentSource]
    model: str
    relevant_documents_found: bool


class SummarizeResponse(BaseModel):
    summary: str
    sources: list[DocumentSource]
    model: str


class SuggestFilenameResponse(BaseModel):
    current_filename: str
    suggested_filename: str
    reason: str
    model: str


class AdminUserResponse(BaseModel):
    id: str
    email: str
    is_admin: bool
    created_at: str


class AdminDocumentResponse(BaseModel):
    id: str
    user_id: str
    owner_email: str | None
    filename: str
    file_type: str
    file_size_bytes: int
    created_at: str
    updated_at: str
