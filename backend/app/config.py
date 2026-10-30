# backend/app/config.py: Backend URL configuration.
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

                                       
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

                                                                          
_PLACEHOLDERS = {
    "SUPABASE_URL": "https://your-project-ref.supabase.co",
    "SUPABASE_SERVICE_ROLE_KEY": "your-service-role-key",
    "ADMIN_EMAIL": "admin@example.com",
    "OPENROUTER_API_KEY": "your-openrouter-api-key",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

                                                                   
    supabase_url: str
    supabase_service_role_key: str = Field(min_length=1)

                                                
    session_expiry_minutes: int = 1440
    admin_email: str = ""
    openrouter_api_key: str = ""
                                                                           
                                                                         
                                                                     
    openrouter_model: str = "minimax/minimax-m3.1-flash:free"
                                                                            
                                                                         
    openrouter_reasoning_effort: str = "low"
    ai_max_output_tokens: int = 700
    ai_context_doc_chars: int = 8000
    ai_context_total_chars: int = 24000
    ai_summary_chars: int = 16000
    ai_suggest_chars: int = 4000
    storage_quota_bytes: int = 524_288_000                          
    max_upload_bytes: int = 52_428_800                                       

                                                                               
                                                                     
    google_sheet_id: str = ""
    google_service_account_file: str = ""


def _placeholder_fields(settings: Settings) -> list[str]:
    values = {
        "SUPABASE_URL": settings.supabase_url,
        "SUPABASE_SERVICE_ROLE_KEY": settings.supabase_service_role_key,
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
