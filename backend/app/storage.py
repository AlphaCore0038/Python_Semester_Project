"""Thin Supabase Storage wrapper for the private 'documents' bucket (Phase 5).

Server-side only. No public URLs are ever created; downloads pass through
authenticated FastAPI endpoints.
"""

from __future__ import annotations

import logging

from app.supabase_client import get_supabase

logger = logging.getLogger(__name__)

BUCKET = "documents"


def upload_object(path: str, data: bytes, content_type: str) -> None:
    # storage3 2.33.0: upload(path, file, file_options) takes a FileOptions
    # TypedDict (string values), not content_type=/upsert= kwargs.
    # upsert="false" keeps POST non-overwriting (never clobber a key).
    get_supabase().storage.from_(BUCKET).upload(
        path, data, {"content-type": content_type, "upsert": "false"}
    )


def download_object(path: str) -> bytes:
    return get_supabase().storage.from_(BUCKET).download(path)


def delete_object(path: str) -> None:
    get_supabase().storage.from_(BUCKET).remove([path])
