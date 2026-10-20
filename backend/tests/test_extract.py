"""Text extraction tests - no network, no OpenRouter."""

from __future__ import annotations

import io
import zipfile

from pypdf import PdfWriter

from app.extract import MAX_EXTRACT_CHARS, extract_text


def _minimal_pdf(text: str) -> bytes:
    content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"
        ),
        b"<< /Length " + str(len(content)).encode() + b" >> stream\n" + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")
    xref_at = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n".encode())
    out.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        out.write(f"{offset:010d} 00000 n \n".encode())
    out.write(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_at}\n%%EOF".encode()
    )
    return out.getvalue()


def _minimal_docx(text: str) -> bytes:
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", document_xml)
    return buffer.getvalue()


def _encrypted_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.encrypt("secret")
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_extracts_utf8_text() -> None:
    result = extract_text("notes.txt", "text/plain", "Registration number 12345".encode())
    assert result.text == "Registration number 12345"
    assert result.note == ""


def test_text_decoding_falls_back_to_latin1() -> None:
    result = extract_text("notes.txt", "text/plain", b"caf\xe9 notes")
    assert "caf" in result.text


def test_extracts_pdf_text() -> None:
    result = extract_text("report.pdf", "application/pdf", _minimal_pdf("Hello Locker"))
    assert "Hello Locker" in result.text


def test_encrypted_pdf_reports_honestly() -> None:
    result = extract_text("secret.pdf", "application/pdf", _encrypted_pdf())
    assert result.text == ""
    assert "password" in result.note.lower()


def test_image_only_pdf_reports_no_text() -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)
    result = extract_text("scan.pdf", "application/pdf", buffer.getvalue())
    assert result.text == ""
    assert "no extractable text" in result.note.lower()


def test_extracts_docx_text() -> None:
    result = extract_text(
        "letter.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        _minimal_docx("Dear student, your GPA is 3.8."),
    )
    assert "GPA is 3.8" in result.text


def test_xlsx_is_unsupported_with_clear_note() -> None:
    result = extract_text(
        "sheet.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        b"anything",
    )
    assert result.text == ""
    assert "not supported" in result.note.lower()


def test_image_is_unsupported() -> None:
    result = extract_text("photo.png", "image/png", b"\x89PNG")
    assert result.text == ""
    assert "not supported" in result.note.lower()


def test_corrupt_pdf_does_not_raise() -> None:
    result = extract_text("broken.pdf", "application/pdf", b"not a pdf at all")
    assert result.text == ""
    assert "could not be read" in result.note.lower()


def test_extracted_text_is_capped() -> None:
    result = extract_text("big.txt", "text/plain", b"a" * (MAX_EXTRACT_CHARS + 500))
    assert len(result.text) == MAX_EXTRACT_CHARS
