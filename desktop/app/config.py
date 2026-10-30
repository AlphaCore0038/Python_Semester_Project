# desktop/app/config.py: Backend URL configuration.
"""Backend URL configuration for the desktop client.

FASTAPI_BASE_URL is read from the process environment, then from the
repo-root .env (shared, non-secret), then defaults to localhost. The
desktop client never holds Supabase or OpenRouter credentials.
"""
from __future__ import annotations

import os
from pathlib import Path

DEFAULT_BASE_URL = "http://127.0.0.1:8000"

                                              
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _base_url_from_env_file() -> str | None:
    env_file = _REPO_ROOT / ".env"
    try:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("FASTAPI_BASE_URL="):
                value = line.split("=", 1)[1].strip().strip("'\"")
                return value or None
    except OSError:
        pass
    return None


def base_url() -> str:
    return (
        os.environ.get("FASTAPI_BASE_URL")
        or _base_url_from_env_file()
        or DEFAULT_BASE_URL
    ).rstrip("/")
