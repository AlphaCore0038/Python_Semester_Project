"""Mirror server output to the console and a log file."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: hud_tee.py LOG_PATH")
        return 2

    log_path = Path(args[0])
    log_path.parent.mkdir(parents=True, exist_ok=True)
    sys.stdin.reconfigure(errors="replace")
    sys.stdout.reconfigure(errors="replace", line_buffering=True)

    with log_path.open("w", encoding="utf-8", errors="replace") as log:
        log.write(f"PyServer HUD log - {datetime.now():%Y-%m-%d %H:%M:%S}\n")
        log.flush()
        for line in sys.stdin:
            sys.stdout.write(line)
            sys.stdout.flush()
            log.write(line)
            log.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
