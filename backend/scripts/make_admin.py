"""Owner-run administrator bootstrap (Phase 9, Milestone 1).

Promotes the single existing account whose normalized email matches
ADMIN_EMAIL. Nothing here runs automatically: the application never promotes
users at startup, registration, or request time.

Run once from backend/ after the admin account has registered:

    .venv\\Scripts\\python.exe scripts\\make_admin.py

The script accepts no arguments, creates no accounts, and changes no
passwords. It is idempotent: an existing administrator is reported as a
no-op.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow `python scripts/make_admin.py` from backend/ without installing the
# app: put backend/ (the parent of scripts/) on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import db  # noqa: E402
from app.config import load_settings  # noqa: E402
from app.schemas import _normalize_email  # noqa: E402


def promote_admin(email: str) -> tuple[int, str]:
    """Promote the existing account matching *email*; returns (exit code, message)."""
    if not email or not email.strip():
        return 1, "ADMIN_EMAIL is not set. Configure it in backend/.env first."

    try:
        normalized = _normalize_email(email)
    except ValueError:
        return 1, "ADMIN_EMAIL is not a valid email address."

    user = db.get_user_by_email(normalized)
    if user is None:
        return (
            1,
            f"No registered account matches ADMIN_EMAIL ({normalized}). "
            "Register that account first, then re-run this script.",
        )
    if user["is_admin"]:
        return 0, f"{normalized} is already an administrator; no change made."

    if not db.set_user_admin(str(user["id"])):
        return 1, "Promotion failed: the database returned no updated row."

    return 0, f"Promoted {normalized} to administrator."


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args:
        print("This script takes no arguments; the target is ADMIN_EMAIL.")
        return 1

    try:
        settings = load_settings()
    except RuntimeError as exc:
        print(f"Configuration error: {exc}")
        return 1

    try:
        code, message = promote_admin(settings.admin_email)
    except Exception as exc:  # noqa: BLE001 - report failure without secrets
        print(f"Database error ({type(exc).__name__}); no change was made.")
        return 1

    print(message)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
