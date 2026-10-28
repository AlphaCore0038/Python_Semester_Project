"""Authenticated document routes (Phase 5): upload, list, usage, download,
rename, delete. Ownership always derives from the authenticated session user."""

from __future__ import annotations

import logging
import uuid
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile

from app import db, storage
from app.config import get_settings
from app.deps import get_current_user
from app.sheets import sheets
from app.schemas import (
    DocumentResponse,
    RenameRequest,
    UsageResponse,
    sanitize_content_type,
    validate_filename,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["documents"])

_READ_CHUNK_BYTES = 1024 * 1024


def _to_response(row: dict) -> DocumentResponse:
    return DocumentResponse(
        id=str(row["id"]),
        filename=row["filename"],
        file_type=row["file_type"],
        file_size_bytes=int(row["file_size_bytes"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _not_found() -> HTTPException:
    # Indistinguishable for nonexistent and foreign-owned documents.
    return HTTPException(status_code=404, detail="Document not found")


async def _read_upload_bounded(file: UploadFile, limit: int) -> bytes:
    """Read the upload in bounded chunks; abort past the configured limit.

    Note: the accumulated bytes are still buffered in request memory; chunked
    reading bounds the loop, it does not eliminate buffering.
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_READ_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise HTTPException(
                status_code=413, detail="File exceeds the maximum upload size"
            )
        chunks.append(chunk)
    if total == 0:
        raise HTTPException(status_code=422, detail="File is empty")
    return b"".join(chunks)


def _attachment_header(filename: str) -> str:
    ascii_fallback = filename.encode("ascii", "ignore").decode().replace('"', "")
    return (
        f'attachment; filename="{ascii_fallback}"; '
        f"filename*=UTF-8''{quote(filename, safe='')}"
    )


@router.post("", status_code=201, response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
) -> DocumentResponse:
    try:
        filename = validate_filename(file.filename or "")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    settings = get_settings()
    data = await _read_upload_bounded(file, settings.max_upload_bytes)

    user_id = str(current_user["id"])
    # Quota from trusted database metadata, never client-supplied sizes.
    used_bytes, _count = db.sum_usage_and_count(user_id)
    if used_bytes + len(data) > settings.storage_quota_bytes:
        raise HTTPException(status_code=413, detail="Storage quota exceeded")

    document_id = str(uuid.uuid4())
    storage_path = f"{user_id}/{document_id}"
    file_type = sanitize_content_type(file.content_type)

    try:
        storage.upload_object(storage_path, data, file_type)
    except Exception:
        logger.exception("Storage upload failed")
        raise HTTPException(status_code=500, detail="Failed to store file") from None

    row = {
        "id": document_id,
        "user_id": user_id,
        "filename": filename,
        "storage_path": storage_path,
        "file_type": file_type,
        "file_size_bytes": len(data),
    }
    try:
        created = db.create_document(row)
    except Exception:
        logger.exception("Document insert failed; cleaning up stored object")
        try:
            storage.delete_object(storage_path)
        except Exception:
            # Orphaned object possible; logged without credentials or contents.
            logger.exception("Compensating storage cleanup failed")
        raise HTTPException(
            status_code=500, detail="Failed to save document metadata"
        ) from None

    # Best-effort Sheets reporting: never fails a successful upload.
    try:
        report_row = db.get_document_report_row(str(created["id"]), user_id)
        if report_row:
            sheets.report_document(report_row, report_row.get("owner_email"))
    except Exception:
        logger.exception("Google Sheets reporting failed after upload")

    return _to_response(created)


@router.get("", response_model=list[DocumentResponse])
def list_documents(
    search: str | None = Query(None, max_length=255),
    sort: Literal["created_at", "filename", "file_size_bytes"] = "created_at",
    order: Literal["asc", "desc"] = "desc",
    file_type: str | None = Query(None, max_length=100, pattern=r"^[\w.+-]+/[\w.+-]+$"),
    current_user: dict = Depends(get_current_user),
) -> list[DocumentResponse]:
    rows = db.list_documents(
        str(current_user["id"]),
        search=search,
        sort=sort,
        order=order,
        file_type=file_type,
    )
    return [_to_response(row) for row in rows]


@router.get("/usage", response_model=UsageResponse)
def storage_usage(current_user: dict = Depends(get_current_user)) -> UsageResponse:
    used_bytes, count = db.sum_usage_and_count(str(current_user["id"]))
    return UsageResponse(
        used_bytes=used_bytes,
        quota_bytes=get_settings().storage_quota_bytes,
        document_count=count,
    )


@router.get("/{document_id}")
def download_document(
    document_id: str, current_user: dict = Depends(get_current_user)
) -> Response:
    try:
        uuid.UUID(document_id)
    except ValueError:
        raise _not_found() from None
    row = db.get_document(document_id, str(current_user["id"]))
    if row is None:
        raise _not_found()
    try:
        data = storage.download_object(row["storage_path"])
    except Exception:
        logger.exception("Storage download failed")
        raise HTTPException(
            status_code=500, detail="Failed to download document"
        ) from None
    return Response(
        content=data,
        media_type=row["file_type"],
        headers={"Content-Disposition": _attachment_header(row["filename"])},
    )


@router.patch("/{document_id}", response_model=DocumentResponse)
def rename_document(
    document_id: str,
    payload: RenameRequest,
    current_user: dict = Depends(get_current_user),
) -> DocumentResponse:
    try:
        uuid.UUID(document_id)
    except ValueError:
        raise _not_found() from None
    updated = db.update_filename(
        document_id, str(current_user["id"]), payload.filename
    )
    if updated is None:
        raise _not_found()
    # Best-effort Sheets reporting: update the row in place by Document ID.
    try:
        report_row = db.get_document_report_row(
            str(updated["id"]), str(current_user["id"])
        )
        if report_row:
            sheets.report_document(report_row, report_row.get("owner_email"))
    except Exception:
        logger.exception("Google Sheets reporting failed after rename")
    # Metadata-only: the Storage object key {user_id}/{document_id} never changes.
    return _to_response(updated)


@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: str, current_user: dict = Depends(get_current_user)
) -> Response:
    try:
        uuid.UUID(document_id)
    except ValueError:
        raise _not_found() from None
    user_id = str(current_user["id"])
    row = db.get_document(document_id, user_id)
    if row is None:
        raise _not_found()
    if not db.delete_document(document_id, user_id):
        raise _not_found()
    # Best-effort Sheets reporting: remove the registry row for the deleted doc.
    try:
        sheets.delete_document_row(str(row["id"]))
    except Exception:
        logger.exception("Google Sheets reporting failed after delete")
    # Best-effort object cleanup after the metadata row is gone (the row is
    # the quota source of truth). A failure can leave an orphaned Storage
    # object; logged without credentials or file contents.
    try:
        storage.delete_object(row["storage_path"])
    except Exception:
        logger.exception("Storage cleanup failed after document delete")
    return Response(status_code=204)
