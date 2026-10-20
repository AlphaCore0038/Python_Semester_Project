"""Lazy Supabase client factory (server-side only).

The service-role key must only ever be used here, inside the backend.
Clients (Django/Tkinter) never receive Supabase credentials.
"""

from __future__ import annotations

from functools import lru_cache

from supabase import Client, create_client

from app.config import get_settings


@lru_cache
def get_supabase() -> Client:
    """Create (once) and return the Supabase client using server credentials.

    Lazy: nothing happens at import time, so /health and tests work without
    valid credentials or network access. Creating the client makes no network
    request.
    """
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
