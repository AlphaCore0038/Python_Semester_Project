# backend/app/sheets.py: Google Sheets formatting helpers.
"""Google Sheets reporting layer (Phase 11A).

Administrative document registry/reporting layer per spec §22/§23.
Supabase PostgreSQL remains the primary database and file store; Sheets is a
secondary best-effort reporting layer.

Only document metadata is ever sent to Google Sheets: document id, owner email,
filename, file type, file size, upload time, last modified time, and storage
mode. Document contents, file bytes, passwords, session tokens, and service
credentials are never shared with Google Sheets.

The client is lazy: the Google API libraries are imported only when a report is
attempted. Every operation is a no-op when Sheets is not configured, the
libraries are not installed, or the API is unavailable. A Sheets failure never
causes a document operation (upload/rename/delete) to fail.
"""

from __future__ import annotations

import logging
import mimetypes
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)

                            
COLUMNS: list[str] = [
    "Document ID",
    "User Email",
    "Filename",
    "File Type",
    "File Size",
    "Upload Time",
    "Last Modified",
    "Storage Mode",
]

_STORAGE_MODE = "Cloud"
_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
_RANGE = "A:H"

_KIBIBYTE = 1_024
_MEBIBYTE = 1_048_576
_IST = timezone(timedelta(hours=5, minutes=30), "IST")
_MONTHS = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)


def _display_file_type(document: dict[str, Any]) -> str:
    """Return an uppercase extension, falling back to the MIME type.

    The filename is authoritative because clients may upload files with an
    unhelpful MIME type such as application/octet-stream.
    """
    filename = str(document.get("filename") or "")
    extension = Path(filename).suffix.lstrip(".").strip()
    if extension:
        return extension.upper()

    mime_type = str(document.get("file_type") or "").split(";", 1)[0].strip()
    guessed = mimetypes.guess_extension(mime_type) if mime_type else None
    return guessed.lstrip(".").upper() if guessed else "FILE"


def _display_size(value: Any) -> str:
    """Format a byte count with binary units and two decimal places."""
    try:
        size = max(0, int(value))
    except (TypeError, ValueError, OverflowError):
        size = 0
    if size < _MEBIBYTE:
        return f"{size / _KIBIBYTE:.2f} KB"
    return f"{size / _MEBIBYTE:.2f} MB"


def _display_ist(value: Any) -> str:
    """Format a timestamp as readable IST, treating naive values as UTC."""
    if isinstance(value, datetime):
        moment = value
    else:
        text = str(value or "").strip()
        if not text:
            return ""
        try:
            moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return text

    if moment.tzinfo is None or moment.utcoffset() is None:
        moment = moment.replace(tzinfo=timezone.utc)
    moment = moment.astimezone(_IST)
    hour = moment.hour % 12 or 12
    period = "AM" if moment.hour < 12 else "PM"
    return (
        f"{moment.day:02d} {_MONTHS[moment.month - 1]} {moment.year:04d}, "
        f"{hour:02d}:{moment.minute:02d} {period}"
    )


def _google_libraries_available() -> bool:
    try:
        import googleapiclient.discovery              
        import google.oauth2.service_account              
        return True
    except ImportError:
        return False


def _quote_sheet_title(title: str) -> str:
    """Quote a worksheet title for use in Google Sheets A1 notation.

    Sheet names containing spaces or special characters must be wrapped in
    single quotes. A single quote inside the name is escaped by doubling it.
    Simple names such as Sheet1 are also safely wrapped, which is accepted by
    the Sheets API.
    """
    escaped = title.replace("'", "''")
    return f"'{escaped}'!{_RANGE}"


class SheetsClient:
    """Best-effort Google Sheets reporting client.

    All failures are logged and swallowed. Document operations must never fail
    because Sheets is misconfigured or unreachable.
    """

    def __init__(self) -> None:
        self._service: Any = None
        self._spreadsheet_id: str | None = None
                                                                            
                                                                            
        self._sheet_title: str = "Sheet1"
        self._sheet_id: int = 0
        self._initialized: bool = False

    def _init(self) -> None:
        if self._initialized:
            return
        self._initialized = True

        if not _google_libraries_available():
            logger.warning(
                "Google Sheets reporting disabled: google-api-python-client / "
                "google-auth not installed"
            )
            return

        settings = get_settings()
        sheet_id = settings.google_sheet_id
        creds_file = settings.google_service_account_file
        if not sheet_id or not creds_file:
            logger.info("Google Sheets reporting disabled: not configured")
            return

        try:
            from google.oauth2.service_account import Credentials
            from googleapiclient.discovery import build

            credentials = Credentials.from_service_account_file(
                creds_file, scopes=_SCOPES
            )
            self._service = build(
                "sheets", "v4", credentials=credentials, cache_discovery=False
            )
            self._spreadsheet_id = sheet_id

                                                                         
            sheet_meta = (
                self._service.spreadsheets()
                .get(
                    spreadsheetId=sheet_id,
                    fields="sheets.properties.sheetId",
                )
                .execute()
            )
            sheets_list = sheet_meta.get("sheets", [])
            if sheets_list:
                first_sheet = sheets_list[0]["properties"]
                self._sheet_id = int(first_sheet["sheetId"])
                self._sheet_title = first_sheet.get("title") or "Sheet1"
        except Exception:
            logger.exception(
                "Google Sheets initialization failed; reporting disabled"
            )
            self._service = None

    @staticmethod
    def _row(
        document: dict[str, Any], owner_email: str | None
    ) -> list[str]:
        return [
            str(document["id"]),
            owner_email or "",
            str(document["filename"]),
            _display_file_type(document),
            _display_size(document.get("file_size_bytes")),
            _display_ist(document["created_at"]),
            _display_ist(document["updated_at"]),
            _STORAGE_MODE,
        ]

    def report_document(
        self, document: dict[str, Any], owner_email: str | None
    ) -> None:
        """Create or update the spreadsheet row for a document (upload/rename)."""
        self._init()
        if self._service is None or self._spreadsheet_id is None:
            return
        try:
            self._upsert_row(document, owner_email)
        except Exception:
            logger.exception(
                "Google Sheets upsert failed for document %s",
                document.get("id"),
            )

    def delete_document_row(self, document_id: str) -> None:
        """Remove the spreadsheet row for a deleted document."""
        self._init()
        if self._service is None or self._spreadsheet_id is None:
            return
        try:
            self._delete_row_by_id(str(document_id))
        except Exception:
            logger.exception(
                "Google Sheets delete failed for document %s", document_id
            )

    def _range_a1(self, row: int | None = None) -> str:
        """Return an A1 range for the discovered worksheet title.

        The title is always single-quoted so names containing spaces or
        apostrophes are handled safely by the Sheets API.
        """
        title = self._sheet_title or "Sheet1"
        quoted_title = _quote_sheet_title(title).split("!")[0]
        if row is None:
            return f"{quoted_title}!{_RANGE}"
        return f"{quoted_title}!{row}:{row}"

                                

    def _values(self) -> list[list[Any]]:
        result = (
            self._service.spreadsheets()
            .values()
            .get(spreadsheetId=self._spreadsheet_id, range=self._range_a1())
            .execute()
        )
        return result.get("values", []) or []

    def _find_row_index(
        self, values: list[list[Any]], document_id: str
    ) -> int | None:
        """Return the zero-based index into `values` for the document, or None.

        Row 0 of `values` is assumed to be the header row.
        """
        for index, row in enumerate(values):
            if row and str(row[0]) == document_id:
                return index
        return None

    def _upsert_row(
        self, document: dict[str, Any], owner_email: str | None
    ) -> None:
        values = self._values()
        row_index = self._find_row_index(values, str(document["id"]))
        row = self._row(document, owner_email)

        if row_index is None:
                                                          
            self._service.spreadsheets().values().append(
                spreadsheetId=self._spreadsheet_id,
                range=self._range_a1(),
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": [row]},
            ).execute()
        else:
                                                                              
            spreadsheet_row = row_index + 1
            self._service.spreadsheets().values().update(
                spreadsheetId=self._spreadsheet_id,
                range=self._range_a1(spreadsheet_row),
                valueInputOption="USER_ENTERED",
                body={"values": [row]},
            ).execute()

    def _delete_row_by_id(self, document_id: str) -> None:
        values = self._values()
        row_index = self._find_row_index(values, document_id)
        if row_index is None:
                                         
            return
                                                                             
                                                             
        self._service.spreadsheets().batchUpdate(
            spreadsheetId=self._spreadsheet_id,
            body={
                "requests": [
                    {
                        "deleteDimension": {
                            "range": {
                                "sheetId": self._sheet_id,
                                "dimension": "ROWS",
                                "startIndex": row_index,
                                "endIndex": row_index + 1,
                            }
                        }
                    }
                ]
            },
        ).execute()


sheets = SheetsClient()
