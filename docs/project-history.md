# AI Digital Locker — Project History

## Original idea and requirements
A personal cloud document locker for college/portfolio use. Two clients (Django web,
Tkinter Windows desktop) share one FastAPI backend. Supabase provides PostgreSQL
metadata and private Storage for files. OpenRouter is the implemented cloud AI option;
Local AI is a placeholder. Practical account separation and basic security; no
enterprise infrastructure.

## Technology choices
- Python 3.14, FastAPI backend, Django web client, Tkinter desktop client.
- Supabase PostgreSQL + private Storage bucket `documents`.
- OpenRouter `minimax/minimax-m3.1-flash:free` for cloud AI; no local inference.
- No Redis/Kafka/MongoDB/vector DB/microservices/Google Drive.

## Chronological implementation history
Commit references are from `git log --oneline` and are verified against repository
history.

- `ada39fd` — `supabase/schema.sql` created and tested (`users`, `auth_sessions`,
  `documents`, RLS).
- `a2555e1` — FastAPI backend foundation: config, health endpoint, tests.
- `68ecb02` — Email/password authentication: register, login, JWT-protected `/auth/me`.
- `dc7b62e` — Fix Supabase Storage upload options compatibility.
- `8d8f35b` — Add Django web client: auth, document dashboard, mocked-HTTP tests.
- `714e3b5` — Add Tkinter desktop client: auth, dashboard, uploads, offline copies,
  mocked tests.
- `43bafd0` — Add authenticated documents API: upload, quota, list, download, rename,
  delete.
- `e49ca5c` — Add AI assistant: OpenRouter MiniMax endpoint, extraction, ask/summarize/
  suggest with mocked tests.
- `3803cd2` — Phase 8 review fixes: escape document filenames in AI prompts, remove
  redundant retrieval lookups, extend AI tests.
- `2e2420a` — Docs: mark Phase 8 verified live, fix stale phase notes, harden gitignore.
- `3a0953b` — Add owner-run admin bootstrap script and fix stale bootstrap docs
  (Phase 9 M1).
- `31aac81` — Add read-only admin API with per-request authorization and audited
  downloads (Phase 9 M2).
- `ad3fd54` — Add read-only Django admin dashboard.
- `4ca9da0` — Complete Phase 9 admin verification and documentation.
- `023be51` — Replace JWT auth with database-backed session tokens (backend, Django,
  desktop).
- `8daa45a` — Revoke Django sessions on logout.
- `52e38d5` — Revoke desktop sessions on logout.
- `a6fcf1e` — Document opaque session authentication.
- `d7985ae` — Migrate password hashes to PBKDF2 with legacy bcrypt upgrade.
- `b1b9dee` — Document Phase 10 demo setup and verification.

## Authentication migration
- JWT/HS256 replaced with opaque `auth_sessions` rows storing SHA-256 token hashes.
- New registrations use PBKDF2 immediately.
- Legacy bcrypt hashes verified through a temporary fallback and were transparently
  rehashed after successful login.
- Live check (2026-10-28, read-only): 2 legacy bcrypt hashes remain.
- Stage 2 bcrypt removal is deferred: the fallback and `bcrypt` dependency remain
  until the live count is zero and the owner explicitly approves removal.

## Fixes and reviews
- Phase 8 review fixes: escape document filenames in AI prompts, remove redundant
  retrieval lookups, extend AI tests.
- Docs fixes: mark Phase 8 verified live, fix stale phase notes, harden `.gitignore`.
- Phase 10 setup fixes: add Django `migrate` before `runserver`, run Django on port
  8001 to avoid colliding with FastAPI on 8000.

## Explicitly deferred or open
- Google Sheets reporting: implemented as a best-effort metadata layer (Phase 11A);
  live spreadsheet writes remain unverified.
- Local AI inference: out of scope; UI placeholder only.
- Stage 2 bcrypt removal: blocked by 2 remaining legacy hashes and owner approval.
- Spec §32 open decisions: OpenRouter key arrangement, exact model, Google Sheets +
  single-admin scope, registration limits. Do not treat as settled.