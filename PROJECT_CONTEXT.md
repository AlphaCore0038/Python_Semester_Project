# AI Digital Locker — Project Context

## Purpose and scope
AI Digital Locker is a college-level and portfolio project: a personal cloud document
management application. Users register, log in, upload/download/search/sort/filter/rename
documents, and optionally use a cloud AI assistant for document understanding.
It is not a production service and intentionally avoids enterprise infrastructure.

## Current architecture
```
Django Web App (web/)          Tkinter Desktop App (desktop/)
        │                                │
        └────────────┬───────────────────┘
                     ▼
              FastAPI Backend (backend/)
                     │
         ┌───────────┴───────────┐
         ▼                       ▼
    Supabase                OpenRouter
 PostgreSQL + Storage    Cloud AI
 (metadata + files)      (MiniMax M3.1 Flash via free route)

Local AI: UI placeholder only — no inference backend.
Google Sheets: best-effort administrative metadata reporting (Phase 11A).
```

- `backend/` — shared FastAPI API. Only component holding Supabase service-role,
  OpenRouter, and Google service-account credentials.
- `web/` — Django client. Talks to FastAPI over HTTP; stores opaque session token
  server-side only.
- `desktop/` — Tkinter Windows client (`py locker.py`). Talks to FastAPI over HTTP;
  optional per-device offline copies under `desktop/offline/`.
- `supabase/` — `schema.sql`: `users`, `auth_sessions`, `documents`, RLS enabled,
  deny-by-default for non-service roles.

## Confirmed decisions and constraints
- Email/password auth only; no OTP/2FA/phone verification.
- Opaque database-backed sessions instead of JWT/HS256.
- New passwords: PBKDF2-HMAC-SHA256, 600,000 iterations, 16-byte salt, 32-byte key.
  Legacy bcrypt hashes remain supported by the fallback and are rehashed after a
  successful login; bcrypt stays installed until the live legacy count is zero.
- One administrator, manually bootstrapped via `ADMIN_EMAIL` and
  `backend/scripts/make_admin.py`; registration cannot grant admin.
- `is_admin` re-checked from the database on every request.
- AI suggestions are proposals only; applying them requires explicit user confirmation
  through the existing rename path.
- Cloud AI via OpenRouter only; Local AI is a disabled placeholder.
- Google Sheets reporting implemented (Phase 11A) per spec §22/§23.
- No document sharing, no folders, no multi-admin, no Redis/Kafka/MongoDB/vector
  databases, no microservices.

## Current verified baseline
- Branch: `main`; run `git log -1 --oneline` and `git status --short --branch`
  for the current HEAD and working-tree state.
- Baseline before the final UI/Sheets commit: `b1b9dee` `Document Phase 10 demo
  setup and verification`; `origin/main` matched it at that point.
- Working tree: `graphify-out/` is generated and must remain unstaged. The
  `.gitignore` update is intentional and should be reviewed with the commit.
- Tests: backend 169, web 61, desktop 39 - all passing. Django `manage.py
  check` and `migrate --check` clean.
- Live legacy-hash check (2026-10-28, read-only): 2 bcrypt hashes remain. The
  bcrypt fallback remains installed; no user records or hashes were changed.
- Full live end-to-end verification is deferred.

## Phase status
Phases 1–10 are implemented and committed per `README.md`. Phase 10 added no product
features; it fixed setup/docs, added the demo runbook, and recorded smoke checks.
Phase 11A (Google Sheets reporting per spec §22/§23) and the shared web/desktop
visual refresh are implemented and tested.

Outstanding work:
- Full live end-to-end verification (valid login, upload/download/Storage, OpenRouter
  AI, browser/desktop against live backend) is deferred.
- Legacy bcrypt migration: 2 live hashes remain; keep the fallback until the count
  is zero and the owner explicitly approves removal.

## Files future sessions must read first
1. `PROJECT_CONTEXT.md` — this file.
2. `AGENTS.md` — Graphify rules and repo conventions.
3. `README.md` — setup, runbook, auth, documents, AI, admin, and verified status.
4. `AI_Digital_Locker_Project_Specification(2).md` — source of truth, especially §32
   open decisions.
5. `docs/session-handoff.md` — current state, blockers, safe Git practices, next step.

## Graphify reference
- Graph artifacts live in `graphify-out/` and are intentionally dirty/unstaged.
- Last local refresh: 2026-10-28 from commit `cff62e88` (1136 nodes, 2333 edges,
  76 communities). The artifacts are unstaged, so they can be newer than the last
  committed snapshot; refresh after code changes: `graphify update .` (AST-only,
  no API cost).
- Do not stage `graphify-out/` output.
- Use `graphify query "<question>"`, `graphify path "<A>" "<B>"`, and
  `graphify explain "<concept>"` for scoped navigation; do not treat the graph as more
  authoritative than source code.

## Recommended next step
Verify the Phase 11A/final UI commit, then proceed to full live
end-to-end verification. Do not remove the bcrypt fallback until the legacy-hash
count is zero and the owner explicitly approves it.