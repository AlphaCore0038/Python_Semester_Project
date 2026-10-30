"""Tests for the synthetic Google Sheets demo registry."""

from __future__ import annotations

from collections import Counter

import pytest

from app.sheets import COLUMNS
from scripts import seed_demo_registry as seed

EXPECTED_FILENAMES = {
    "BTech_Semester_Marksheet.pdf",
    "Resume_2026.pdf",
    "Internship_Offer_Letter.pdf",
    "Python_Assignment_Unit_3.docx",
    "Project_Report_AI_Digital_Locker.pdf",
    "College_ID_Front.jpg",
    "Fee_Receipt_Oct_2026.pdf",
    "Monthly_Expense_Tracker.xlsx",
    "Workshop_Certificate.pdf",
    "Computer_Networks_Lab_Record.pdf",
    "Scholarship_Application.pdf",
    "Family_Trip_Itinerary.pdf",
    "Course_Completion_Certificate.pdf",
}


def test_registry_has_exactly_13_unique_document_ids():
    records = seed.load_records()
    document_ids = [record["Document ID"] for record in records]
    assert len(records) == 13
    assert len(set(document_ids)) == 13


def test_registry_has_six_users_with_expected_gender_split():
    records = seed.load_records()
    counts = Counter(record["User Email"].lower() for record in records)
    assert len(counts) == 6
    assert set(counts) == set(seed.DEMO_USERS)

    user_genders = Counter(seed.DEMO_USERS[email][1] for email in counts)
    assert user_genders == {"female": 4, "male": 2}

    record_genders = Counter(
        seed.DEMO_USERS[record["User Email"].lower()][1] for record in records
    )
    assert record_genders == {"female": 9, "male": 4}


def test_registry_matches_columns_and_demo_formatting():
    records = seed.load_records()
    assert list(records[0]) == COLUMNS
    assert {record["Filename"] for record in records} == EXPECTED_FILENAMES
    assert all(record["Storage Mode"] == "Cloud" for record in records)
    assert all(seed._SIZE_PATTERN.fullmatch(record["File Size"]) for record in records)
    assert all(seed._TIME_PATTERN.fullmatch(record["Upload Time"]) for record in records)
    assert all(
        seed._TIME_PATTERN.fullmatch(record["Last Modified"]) for record in records
    )
    assert all(
        record["Upload Time"] != record["Last Modified"] for record in records
    )


def test_registry_rejects_duplicate_document_ids():
    records = seed.load_records()
    records[1] = dict(records[0])
    with pytest.raises(ValueError, match="unique"):
        seed.validate_records(records)


def test_registry_rejects_wrong_record_count():
    records = seed.load_records()
    with pytest.raises(ValueError, match="exactly 13"):
        seed.validate_records(records[:12])
