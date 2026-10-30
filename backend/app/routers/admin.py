# backend/app/routers/admin.py: FastAPI router for admin.
"""Read-only administrator routes (Phase 9, Milestone 2).

Every route depends on require_admin, which re-reads users.is_admin from the
database on every request. There are no destructive or editing operations
here, and no administrator-only access to Supabase credentials or public
Storage URLs: downloads are proxied by the backend.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response

from app import db, storage
from app.deps import require_admin
from app.routers.documents import _attachment_header
from app.schemas import AdminDocumentResponse, AdminUserResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["admin"])


def _not_found() -> HTTPException:
                                                      
    return HTTPException(status_code=404, detail="Document not found")


def _to_admin_document(row: dict, owner_email: str | None) -> AdminDocumentResponse:
    return AdminDocumentResponse(
        id=str(row["id"]),
        user_id=str(row["user_id"]),
        owner_email=owner_email,
        filename=row["filename"],
        file_type=row["file_type"],
        file_size_bytes=int(row["file_size_bytes"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


@router.get("/users", response_model=list[AdminUserResponse])
def list_users(current_admin: dict = Depends(require_admin)) -> list[AdminUserResponse]:
                                                                 
    return [
        AdminUserResponse(
            id=str(user["id"]),
            email=user["email"],
            is_admin=bool(user["is_admin"]),
            created_at=str(user["created_at"]),
        )
        for user in db.list_users()
    ]


@router.get("/documents", response_model=list[AdminDocumentResponse])
def list_documents(
    current_admin: dict = Depends(require_admin),
) -> list[AdminDocumentResponse]:
                                                                             
    owners = {str(user["id"]): user["email"] for user in db.list_users()}
    return [
        _to_admin_document(row, owners.get(str(row["user_id"])))
        for row in db.list_documents_admin()
    ]


@router.get("/documents/{document_id}")
def download_document(
    document_id: str, current_admin: dict = Depends(require_admin)
) -> Response:
    try:
        uuid.UUID(document_id)
    except ValueError:
        raise _not_found() from None
    row = db.get_document_admin(document_id)
    if row is None:
        raise _not_found()

    try:
        data = storage.download_object(row["storage_path"])
    except Exception:
        logger.exception("Admin storage download failed")
        raise HTTPException(
            status_code=500, detail="Failed to download document"
        ) from None

                                                                         
    logger.info(
        "admin document download: admin_id=%s admin_email=%s "
        "document_id=%s owner_id=%s timestamp_utc=%s",
        current_admin["id"],
        current_admin["email"],
        row["id"],
        row["user_id"],
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    return Response(
        content=data,
        media_type=row["file_type"],
        headers={"Content-Disposition": _attachment_header(row["filename"])},
    )
