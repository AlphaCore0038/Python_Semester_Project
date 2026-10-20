"""Application configuration for the AI Digital Locker backend.

Reads backend/.env (never committed). Secret values are validated for
presence/placeholders but are never logged, echoed in errors, or returned
in API responses.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py -> backend/.env
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

# Values copied verbatim from .env.example that mean "not configured yet".
_PLACEHOLDERS = {
    "SUPABASE_URL": "https://your-project-ref.supabase.co",
    "SUPABASE_SERVICE_ROLE_KEY": "your-service-role-key",
    "JWT_SECRET": "your-long-random-jwt-signing-secret",
    "ADMIN_EMAIL": "admin@example.com",
    "OPENROUTER_API_KEY": "your-openrouter-api-key",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    # Required (no defaults): missing/empty -> clear startup error.
    supabase_url: str
    supabase_service_role_key: str = Field(min_length=1)
    jwt_secret: str = Field(min_length=1)

    # Optional with defaults (per .env.example).
    jwt_expiry_minutes: int = 1440
    admin_email: str = ""
    openrouter_api_key: str = ""
    openrouter_model: str = "xiaomi/mimo-v2.6-flash:free"
    storage_quota_bytes: int = 524_288_000  # 500 MB per user (spec)
    max_upload_bytes: int = 52_428_800  # 50 MB: Supabase Free per-file limit


def _placeholder_fields(settings: Settings) -> list[str]:
    values = {
        "SUPABASE_URL": settings.supabase_url,
        "SUPABASE_SERVICE_ROLE_KEY": settings.supabase_service_role_key,
        "JWT_SECRET": settings.jwt_secret,
        "ADMIN_EMAIL": settings.admin_email,
        "OPENROUTER_API_KEY": settings.openrouter_api_key,
    }
    return [name for name, value in values.items() if value == _PLACEHOLDERS.get(name)]


def load_settings() -> Settings:
    """Load and validate settings. Errors name variables, never their values."""
    try:
        settings = Settings(_env_file=ENV_FILE if ENV_FILE.exists() else None)
    except ValidationError as exc:
        missing = sorted(
            ".".join(str(loc) for loc in err["loc"]).upper() for err in exc.errors()
        )
        raise RuntimeError(
            "Missing required backend configuration: "
            f"{', '.join(missing)}. "
            "Copy backend/.env.example to backend/.env and fill in the values."
        ) from None

    placeholders = _placeholder_fields(settings)
    if placeholders:
        raise RuntimeError(
            "Backend configuration still contains template placeholder values: "
            f"{', '.join(placeholders)}. "
            "Edit backend/.env and replace every placeholder with a real value."
        )
    return settings


@lru_cache
def get_settings() -> Settings:
    return load_settings()
