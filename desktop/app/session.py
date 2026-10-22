"""Persistent local login session for the desktop client.

The FastAPI session token is stored at %APPDATA%\\AiDigitalLocker\\session.json
so the app can reopen straight to the dashboard. SECURITY NOTES (documented,
intentional for this phase):
- The token is stored in PLAINTEXT and is readable by the same Windows
  user account. DPAPI encryption is a possible future hardening, not here.
- It is never printed, logged, displayed, or placed in a URL.
- Writes are atomic (temp file + os.replace). The 0o600 mode is applied on
  platforms that honor it; on Windows, protection comes from the
  per-user %APPDATA% ACL, not from this mode alone.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path


def default_session_path() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "AiDigitalLocker" / "session.json"


@dataclass
class Session:
    access_token: str = field(repr=False)  # never appears in logs/reprs
    email: str
    expires_at: float

    def is_expired(self) -> bool:
        return time.time() >= self.expires_at


class SessionStore:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else default_session_path()

    def load(self) -> Session | None:
        """Returns None for missing, corrupt, or expired sessions."""
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            session = Session(
                access_token=str(data["access_token"]),
                email=str(data["email"]),
                expires_at=float(data["expires_at"]),
            )
        except (OSError, ValueError, KeyError, TypeError):
            return None
        if session.is_expired():
            self.clear()
            return None
        return session

    def save(self, session: Session) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {
                "access_token": session.access_token,
                "email": session.email,
                "expires_at": session.expires_at,
            }
        )
        fd, tmp_name = tempfile.mkstemp(
            dir=self.path.parent, prefix=".session-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
            try:
                os.chmod(tmp_name, 0o600)
            except OSError:
                pass
            os.replace(tmp_name, self.path)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    def clear(self) -> None:
        try:
            self.path.unlink()
        except OSError:
            pass
