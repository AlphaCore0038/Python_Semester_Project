"""Text extraction for AI context - TXT, PDF, and DOCX only.

Honest by design: unsupported formats and unreadable files return a clear
note instead of pretending the model read them. Extracted text is capped;
PDFs are never truncated before parsing (that would corrupt them).
"""
from __future__ import annotations

import io
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from pypdf import PdfReader

# Hard cap on any single document's extracted text handed to retrieval.
MAX_EXTRACT_CHARS = 30_000
MAX_PDF_PAGES = 30

_DOCX_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"


@dataclass
class ExtractionResult:
    text: str = ""
    note: str = ""  # empty string means success


def _finalize(text: str) -> ExtractionResult:
    text = text.strip()[:MAX_EXTRACT_CHARS]
    if not text:
        return ExtractionResult("", "The document appears to contain no readable text.")
    return ExtractionResult(text=text)


def _from_text(data: bytes) -> ExtractionResult:
    # utf-8-sig handles BOM; latin-1 never fails and is the honest last resort
    # (a utf-16 attempt without BOM silently "succeeds" on random bytes).
    try:
        return _finalize(data.decode("utf-8-sig"))
    except UnicodeDecodeError:
        return _finalize(data.decode("latin-1"))


def _from_pdf(data: bytes) -> ExtractionResult:
    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        return ExtractionResult(
            "", "This PDF is password-protected and cannot be read."
        )
    parts = [(page.extract_text() or "") for page in reader.pages[:MAX_PDF_PAGES]]
    text = "\n".join(parts)
    if not text.strip():
        return ExtractionResult(
            "",
            "This PDF has no extractable text (it may be a scan). "
            "OCR is not available.",
        )
    return _finalize(text)


def _from_docx(data: bytes) -> ExtractionResult:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        xml_bytes = archive.read("word/document.xml")
    root = ET.fromstring(xml_bytes)
    pieces = [el.text for el in root.iter(_DOCX_NS) if el.text]
    return _finalize("\n".join(pieces))


def extract_text(filename: str, file_type: str, data: bytes) -> ExtractionResult:
    """Best-effort text extraction; never raises for bad user files."""
    file_type = (file_type or "").lower()
    name = (filename or "").lower()
    try:
        if file_type.startswith("text/") or name.endswith((".txt", ".csv", ".md")):
            return _from_text(data)
        if "pdf" in file_type or name.endswith(".pdf"):
            return _from_pdf(data)
        if (
            file_type
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            or name.endswith(".docx")
        ):
            return _from_docx(data)
    except Exception:  # noqa: BLE001 - corrupt/adversarial files must not 500
        return ExtractionResult(
            "",
            "The document could not be read (it may be corrupted or password-protected).",
        )
    return ExtractionResult(
        "", "Text extraction is not supported for this format yet."
    )
