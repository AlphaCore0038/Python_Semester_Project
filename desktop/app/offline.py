"""Optional local offline copies (spec section 11).

Cloud storage stays primary; the user may keep per-device copies under
desktop/offline/<document_id>/<filename>. Limitations (intentional):
- No cross-device synchronization, ever (spec section 11).
- Copies are unencrypted files the user owns.
- Logging out does NOT delete copies; a cloud rename or delete does NOT
  touch them either (copies are keyed by document id).
"""
from __future__ import annotations

from pathlib import Path

# offline.py -> app -> desktop
_DESKTOP_ROOT = Path(__file__).resolve().parents[1]


def offline_root() -> Path:
    return _DESKTOP_ROOT / "offline"


def dir_for(document_id: str, root: Path | None = None) -> Path:
    return (root or offline_root()) / str(document_id)


def copy_path(document_id: str, filename: str, root: Path | None = None) -> Path:
    return dir_for(document_id, root) / filename


def has_copy(document_id: str, root: Path | None = None) -> bool:
    directory = dir_for(document_id, root)
    try:
        return any(p.is_file() for p in directory.iterdir())
    except OSError:
        return False
