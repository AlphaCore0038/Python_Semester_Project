# backend/scripts/seed_demo_registry.py: Admin/seed utility script.
"""Seed the Google Sheets registry with the 13-record synthetic demo dataset.

This script only writes document metadata to the first worksheet of the
configured Google Sheet. It does not create Supabase users or documents.

Run from backend/:

    .venv\\Scripts\\python.exe scripts\\seed_demo_registry.py
    .venv\\Scripts\\python.exe scripts\\seed_demo_registry.py --apply

The first command is a dry run. The second writes only after explicit
confirmation on the command line.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import uuid
from pathlib import Path

                                                             
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.sheets import COLUMNS, SheetsClient              

EXPECTED_RECORD_COUNT = 13
STORAGE_MODE = "Cloud"
CSV_PATH = Path(__file__).with_name("demo_registry_13.csv")

DEMO_USERS: dict[str, tuple[str, str]] = {
    "ananya.reddy.demo@gmail.com": ("Ananya Reddy", "female"),
    "sai.priya.rao.demo@gmail.com": ("Sai Priya Rao", "female"),
    "lakshmi.devi.demo@gmail.com": ("Lakshmi Devi", "female"),
    "harika.chowdary.demo@gmail.com": ("Harika Chowdary", "female"),
    "arjun.naidu.demo@gmail.com": ("Arjun Naidu", "male"),
    "rohit.varma.demo@gmail.com": ("Rohit Varma", "male"),
}

_SIZE_PATTERN = re.compile(r"^(?:0|[1-9]\d*)\.\d{2} (?:KB|MB)$")
_TIME_PATTERN = re.compile(
    r"^(?:0[1-9]|[12]\d|3[01]) "
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) "
    r"\d{4}, (?:0[1-9]|1[0-2]):[0-5]\d (?:AM|PM)$"
)
_EMAIL_PATTERN = re.compile(r"^[a-z0-9][a-z0-9.]*@gmail\.com$")


def validate_records(records: list[dict[str, str]]) -> None:
    """Reject invalid rows before any spreadsheet write is attempted."""
    if len(records) != EXPECTED_RECORD_COUNT:
        raise ValueError(
            f"expected exactly {EXPECTED_RECORD_COUNT} records, found {len(records)}"
        )

    seen_ids: set[str] = set()
    for row in records:
        missing = [column for column in COLUMNS if not (row.get(column) or "").strip()]
        if missing:
            raise ValueError(f"missing required fields: {', '.join(missing)}")

        document_id = row["Document ID"].strip()
        try:
            uuid.UUID(document_id)
        except ValueError as exc:
            raise ValueError(f"invalid document ID: {document_id}") from exc
        if document_id in seen_ids:
            raise ValueError(f"document IDs must be unique; duplicate: {document_id}")
        seen_ids.add(document_id)

        email = row["User Email"].strip().lower()
        if not _EMAIL_PATTERN.fullmatch(email):
            raise ValueError(f"invalid Gmail address: {row['User Email']}")
        if email not in DEMO_USERS:
            raise ValueError(f"unexpected demo user: {row['User Email']}")

        filename = row["Filename"].strip()
        expected_type = Path(filename).suffix.lstrip(".").upper()
        if not expected_type or row["File Type"] != expected_type:
            raise ValueError(f"file type does not match filename: {filename}")
        if not _SIZE_PATTERN.fullmatch(row["File Size"]):
            raise ValueError(f"invalid file size: {row['File Size']}")
        if not _TIME_PATTERN.fullmatch(row["Upload Time"]):
            raise ValueError(f"invalid upload time: {row['Upload Time']}")
        if not _TIME_PATTERN.fullmatch(row["Last Modified"]):
            raise ValueError(f"invalid modified time: {row['Last Modified']}")
        if row["Storage Mode"] != STORAGE_MODE:
            raise ValueError(f"storage mode must be {STORAGE_MODE}")

    emails = {row["User Email"].strip().lower() for row in records}
    if emails != set(DEMO_USERS):
        raise ValueError("records must use all six configured demo users")

    female_records = sum(
        DEMO_USERS[row["User Email"].strip().lower()][1] == "female"
        for row in records
    )
    male_records = len(records) - female_records
    if (female_records, male_records) != (9, 4):
        raise ValueError(
            "expected 9 female-user records and 4 male-user records, "
            f"found {female_records} and {male_records}"
        )


def load_records(path: Path = CSV_PATH) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != COLUMNS:
            raise ValueError(
                "CSV headers must exactly match: " + ", ".join(COLUMNS)
            )
        records = list(reader)
    validate_records(records)
    return records


def _column_letter(column: int) -> str:
    letters = ""
    while column:
        column, remainder = divmod(column - 1, 26)
        letters = chr(ord("A") + remainder) + letters
    return letters


def _target_ranges(client: SheetsClient) -> tuple[str, list[str]]:
    title = "'" + (client._sheet_title or "Sheet1").replace("'", "''") + "'"
    result = (
        client._service.spreadsheets()
        .values()
        .get(spreadsheetId=client._spreadsheet_id, range=f"{title}!A:Z")
        .execute()
    )
    rows = result.get("values", []) or []

    used_row = 0
    used_column = 0
    for row_number, row in enumerate(rows, start=1):
        for column_number, value in enumerate(row, start=1):
            if str(value).strip():
                used_row = max(used_row, row_number)
                used_column = max(used_column, column_number)

    write_range = (
        f"{title}!A1:{_column_letter(len(COLUMNS))}"
        f"{EXPECTED_RECORD_COUNT + 1}"
    )
    clear_ranges: list[str] = []
    if used_row > EXPECTED_RECORD_COUNT + 1:
        clear_ranges.append(
            f"{title}!A{EXPECTED_RECORD_COUNT + 2}:"
            f"{_column_letter(max(used_column, len(COLUMNS)))}"
            f"{used_row}"
        )
    if used_column > len(COLUMNS):
        clear_ranges.append(
            f"{title}!{_column_letter(len(COLUMNS) + 1)}1:"
            f"{_column_letter(used_column)}{EXPECTED_RECORD_COUNT + 1}"
        )
    return write_range, clear_ranges


def seed_registry(
    client: SheetsClient,
    records: list[dict[str, str]],
    *,
    apply: bool,
) -> None:
    write_range, clear_ranges = _target_ranges(client)
    print(f"Worksheet: {client._sheet_title}")
    print(f"Write range: {write_range}")
    print(f"Clear ranges: {', '.join(clear_ranges) if clear_ranges else 'none'}")
    print(
        f"Records: {len(records)} "
        f"(unique document IDs: {len({r['Document ID'] for r in records})})"
    )

    if not apply:
        print("Dry run only: no cells were changed.")
        print("Re-run with --apply after confirming these ranges.")
        return

    values = client._service.spreadsheets().values()
    body = {
        "values": [COLUMNS] + [[row[column] for column in COLUMNS] for row in records]
    }
    values.update(
        spreadsheetId=client._spreadsheet_id,
        range=write_range,
        valueInputOption="RAW",
        body=body,
    ).execute()
    if clear_ranges:
        values.batchClear(
            spreadsheetId=client._spreadsheet_id,
            body={"ranges": clear_ranges},
        ).execute()
    print(f"Seeded {EXPECTED_RECORD_COUNT} records into {client._sheet_title}.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Seed the Google Sheets demo registry with 13 records."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write the records; without this flag the script only prints the plan",
    )
    args = parser.parse_args(argv)

    try:
        records = load_records()
    except (OSError, ValueError) as exc:
        print(f"Registry validation failed: {exc}")
        return 2

    client = SheetsClient()
    client._init()
    if client._service is None or client._spreadsheet_id is None:
        print("Google Sheets is not configured or unavailable; no changes made.")
        return 1

    try:
        seed_registry(client, records, apply=args.apply)
    except Exception as exc:                                                 
        print(f"Seeding failed ({type(exc).__name__}); no further writes attempted.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
