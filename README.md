# AI Digital Locker

A cloud-based personal document management application — a college-level and portfolio
project. Users upload, organize (search/sort/filter), and download documents with an
optional AI assistant for document understanding.

The full requirements live in
[`AI_Digital_Locker_Project_Specification(2).md`](AI_Digital_Locker_Project_Specification(2).md);
that specification is the source of truth.

## Architecture

```
Django Web App (web/)          Tkinter Desktop App (desktop/)
        │                                │
        └────────────┬───────────────────┘
                     ▼
              FastAPI Backend (backend/)
                     │
        ┌────────────┴────────────┐
        ▼                         ▼
     Supabase                 OpenRouter
  PostgreSQL + Storage       Cloud AI (MiniMax M3.1 Flash)
  (metadata + files)

  Local AI: UI placeholder only — no inference backend in this version.
  Google Sheets: deferred administrative document registry (later phase).
```

- **backend/** — shared FastAPI API: authentication, document operations, AI endpoints.
  The only component that holds Supabase and OpenRouter credentials.
- **web/** — Django client (browser UI). Talks to FastAPI over HTTP.
- **desktop/** — Tkinter Windows client (`py locker.py`, later phase). Talks to FastAPI
  over HTTP; may keep optional local offline copies of documents (this device only).
- **supabase/** — database schema scripts (added in a later phase).

Key product rules (from the specification): 500 MB cloud storage per user, flat document
collection (no folders), duplicate filenames allowed, single administrator, no document
sharing, Local AI must never be presented as working.

## Repository layout

```
backend/          FastAPI backend (requirements.txt, .env.example)
web/              Django web client (requirements.txt)
desktop/          Tkinter desktop client (requirements.txt)
supabase/         Schema scripts (Phase 2)
.env.example      Root template: non-secret client config (FASTAPI_BASE_URL)
```

## Configuration and secrets

Real environment files (`.env`) are gitignored. Templates are committed:

- Root `.env.example` — `FASTAPI_BASE_URL` for the clients.
- `backend/.env.example` — Supabase URL + service-role key, JWT secret, OpenRouter key,
  admin email, storage limits.

Privileged credentials (Supabase service-role key, JWT signing secret, OpenRouter API
key) exist **only** in `backend/.env` on the server. They are never placed in the Django
or Tkinter clients and are never committed to Git.

## Development status

| Phase | Scope | Status |
|---|---|---|
| 1 | Repository foundation (this) | **Complete** |
| 2 | Supabase schema + private storage bucket | **Complete** |
| 3 | FastAPI core + smoke test | **Complete** |
| 4 | Authentication (register/login, JWT, admin bootstrap) | **Complete** (admin bootstrap lands with admin phase) |
| 5 | Documents API (upload, quota, search, download, rename, delete) | **Complete** |
| 6 | Django web client | **Complete** |
| 7 | Tkinter desktop client | **Complete** |
| 8 | AI assistant (OpenRouter) | **Complete** |
| 9 | Admin access + Google Sheets registry (deferred) | Not started |
| 10 | Demo polish | Not started |

Backend foundation exists (`backend/app/`); clients and feature APIs arrive in
later phases. Target Python version: **3.14** (Django 6.1 and current FastAPI
both support it; backend dependencies install and pass tests on 3.14).

## Setup — backend (Windows, Python 3.14 via the `py` launcher)

Prerequisites: Python 3.14 installed (the Windows `py` launcher must work).

```bat
:: 1. Virtual environment
cd backend
py -m venv .venv
.venv\Scripts\activate

:: 2. Dependencies
pip install -r requirements.txt

:: 3. Configuration (never commit the real .env)
copy .env.example .env
notepad .env
:: Fill in SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, JWT_SECRET (required),
:: plus any optional values you need. Placeholder values are rejected at startup.

:: 4. Run the API
uvicorn app.main:app --reload
:: Health check: http://127.0.0.1:8000/health  ->  {"status":"ok"}

:: 5. Tests (no real .env or credentials required)
py -m pytest
```

The web (`web/`) and desktop (`desktop/`) clients each have their own
venv (see the Phase 6 and Phase 7 sections below).

## Authentication (Phase 4)

FastAPI-managed email/password auth against the `public.users` table
(no Supabase Auth). Passwords are bcrypt-hashed; access tokens are HS256 JWTs
signed with `JWT_SECRET`, valid for `JWT_EXPIRY_MINUTES` (default 24 h).

```bat
:: With the server running (uvicorn app.main:app --reload):
curl -X POST http://127.0.0.1:8000/auth/register -H "Content-Type: application/json" -d "{\"email\":\"demo@example.com\",\"password\":\"correct-horse-1\"}"
curl -X POST http://127.0.0.1:8000/auth/login    -H "Content-Type: application/json" -d "{\"email\":\"demo@example.com\",\"password\":\"correct-horse-1\"}"
curl http://127.0.0.1:8000/auth/me -H "Authorization: Bearer <access_token>"
```

Rules enforced by the API: emails are normalized to lowercase (duplicate
registration is case-insensitive); passwords must be 8–72 UTF-8 bytes (never
truncated); `is_admin` cannot be set through registration; login returns one
generic error for wrong password or unknown email; the authenticated user id
comes only from the verified JWT. Tests use an in-memory fake store — no real
Supabase project or `.env` is needed for `py -m pytest`.

## Documents API (Phase 5)

All routes require `Authorization: Bearer <access_token>`; the user is always
resolved from the verified JWT (never from request data).

| Route | Purpose |
|---|---|
| `POST /documents` | Upload (multipart `file`); 413 over 50 MiB or over the 500 MB quota |
| `GET /documents` | List with `search`, `sort` (`created_at`/`filename`/`file_size_bytes`), `order` (`asc`/`desc`), `file_type` |
| `GET /documents/usage` | `{used_bytes, quota_bytes, document_count}` for the current user |
| `GET /documents/{id}` | Download through FastAPI (private bucket, no public URLs) |
| `PATCH /documents/{id}` | Rename (metadata only; Storage object never moves) |
| `DELETE /documents/{id}` | Delete row, then best-effort Storage cleanup |

```bat
curl -X POST http://127.0.0.1:8000/documents -H "Authorization: Bearer %TOKEN%" -F "file=@sample.pdf"
curl "http://127.0.0.1:8000/documents?search=intern&sort=filename&order=asc" -H "Authorization: Bearer %TOKEN%"
curl -o sample.pdf http://127.0.0.1:8000/documents/<id> -H "Authorization: Bearer %TOKEN%"
```

Notes and honest limitations: filenames are validated strictly (1–255 chars,
no path separators/control characters — rejected with 422, never rewritten);
duplicate filenames are allowed; object keys are always
`{user_id}/{document_id}`. The quota check reads current usage from the
database, so two truly simultaneous uploads could race past the 500 MB limit
(negligible for personal use). If Storage cleanup fails after a metadata
delete, an orphaned object may remain (logged; excluded from quota).

Supabase notes: project `ai-digital-locker` (ap-south-1); tables `public.users`
and `public.documents` with RLS enabled; private Storage bucket `documents`.
The Supabase Free plan caps each uploaded object at 50 MB
(`MAX_UPLOAD_BYTES=52428800`); the application-level per-user quota remains
500 MB (`STORAGE_QUOTA_BYTES=524288000`).

## Web client — Django (Phase 6)

Django provides the UI and session management; FastAPI remains the sole API and
authorization boundary. Django calls FastAPI over HTTP only — it never touches
Supabase and never holds service-role or JWT-signing credentials.

```bat
:: 1. Virtual environment + dependencies (Windows, Python 3.14)
cd web
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

:: 2. Configuration (never commit the real .env)
copy .env.example .env
notepad .env
:: Set DJANGO_SECRET_KEY (required):
::   py -c "import secrets; print(secrets.token_urlsafe(64))"
:: FASTAPI_BASE_URL is inherited from the repo-root .env if present.

:: 3. Tests (all FastAPI calls are mocked; backend must NOT be running for clarity)
py manage.py test

:: 4. Run (with the FastAPI backend already running on :8000)
py manage.py runserver
:: Open http://127.0.0.1:8000/  ->  register, upload, search, sort, download
```

What works: registration with automatic login, login, POST-only logout,
authenticated dashboard with a 500 MB usage bar, upload (50 MiB UI hint,
FastAPI authoritative), filename search, sort/order, MIME-type filter,
streaming download proxy, rename, and delete behind a confirmation page.
Expired sessions (401) flush Django state and redirect to login; API/network
failures show safe generic messages.

Security posture: the FastAPI JWT lives only in Django's server-side session
store (database-backed cookie holds an opaque session key — HttpOnly,
SameSite=Lax, Secure when `DEBUG=False`); it is never rendered into HTML,
URLs, or JavaScript. Session keys rotate on every login, all state-changing
forms carry CSRF tokens, and `DJANGO_SECRET_KEY` is required from the
environment (the process refuses to start without it).

Honest limitations: Django does not proxy the backend's 413 `detail` strings
into structured codes (it matches the two known messages exactly); list
results are rendered unpaginated (fine at the 500 MB personal scale).

## Desktop client — Tkinter (Phase 7)

Windows Tkinter app that talks only to the FastAPI backend (never to
Supabase). Requires the same Python 3.14 + `py` launcher setup; the only
third-party dependency is `httpx`.

```bat
:: 1. Virtual environment + dependencies
cd desktop
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

:: 2. Configuration (optional): set a non-default backend URL
set FASTAPI_BASE_URL=http://127.0.0.1:8000
:: Otherwise the repo-root .env is read, then localhost is assumed.

:: 3. Tests (all HTTP mocked; no credentials needed)
py -m pytest

:: 4. Run with the FastAPI backend already running
py locker.py
```

What works: register (auto-login), login, logout, persisted login across
restarts, dashboard with usage bar and document list, upload (with the
spec's "Keep Offline Copy" checkbox), download, save-offline for existing
documents, rename, delete-with-confirmation, search/sort/MIME filter using
the real API parameters, and expired-session handling (401 returns to the
login screen).

**Sessions:** the JWT is stored in plaintext at
`%APPDATA%\AiDigitalLocker\session.json` (per-user folder, atomic writes).
It is never printed, logged, shown in the UI, or placed in a URL. Logout
clears it. Same-Windows-user access to that file is a documented
limitation; OS-level encryption (DPAPI) is possible future hardening.

**Offline copies (spec §11):** optional per-device copies live under
`desktop/offline/<document_id>/<filename>` (gitignored). They never
synchronize across devices or with later cloud changes; they are not
deleted on logout; cloud renames/deletes do not touch them; they are
plain local files. Downloads stream to a temp file and are moved into
place only when complete.

**Known limitations:** one network operation at a time (buttons disable
while one runs); the 50 MiB/500 MB messages rely on the backend's exact
413 wording (pinned by backend tests); logout does not revoke the
server-side JWT (it simply expires after 24 h).

## AI assistant — Cloud AI via OpenRouter (Phase 8)

The assistant is optional: the locker is fully usable without it (spec §17).
It runs entirely inside the FastAPI backend, which is the only component
holding the OpenRouter key. Clients pass a Bearer JWT; every AI endpoint
resolves the user from the verified token and touches documents only via
the same user-scoped database/storage paths the rest of the API uses.

**Model:** `minimax/minimax-m3.1-flash:free` (MiniMax M3.1 Flash, via
OpenRouter's free route). There is **no fallback model**: if the free route
is busy, unavailable, or the key is missing, AI endpoints return a clear,
safe 503 and the rest of the app keeps working. Override with
`OPENROUTER_MODEL` in `backend/.env`; reasoning effort with
`OPENROUTER_REASONING_EFFORT` (default `low` to keep chat latency sane).

**What works:**

- `GET /ai/status` — configured flag + model name (authenticated).
- `POST /ai/ask` — question answered from the user's own documents.
  Keyword-window retrieval (filename overlap weighted above content
  overlap, top 3 excerpts, hard character budget) picks candidates; if
  nothing looks relevant the model is **never called** and the API returns
  a fixed honest "couldn't find any documents" message with
  `relevant_documents_found: false`. When excerpts do not contain the
  answer, the fixed system prompt forces the model to say so instead of
  guessing. Document text is wrapped in `<document>` tags and treated as
  untrusted data (prompt-injection defense: the system prompt is fixed
  and the model has no tools or side effects).
- `POST /ai/summarize` — short summary of one owned document.
- `POST /ai/suggest-filename` — **proposal only.** The suggestion is
  validated server-side with the same filename rules as rename; applying
  it goes through the existing confirmed rename path (web: the rename
  page, desktop: an explicit yes/no prompt then `PATCH /documents/{id}`).
  The AI endpoints themselves never write anything.

**Text extraction (honest scope):** TXT, PDF (via `pypdf`), and DOCX only.
XLSX and images return a clear "not supported yet" message; scanned PDFs
with no text layer, password-protected files, and corrupt files each get
their own honest error. No OCR, no speculative success.

**UI:** Django — floating AI button (bottom-right, logged-in users only)
opens the `/ai/` page (ask / summarize / suggest). Tkinter — "AI Assistant"
button opens a compact dialog with the same three modes; "Local AI" is a
disabled radio button labeled unavailable, never a selectable working mode
(spec §12).

**Known limitations:** non-streaming (one reply per request; answers arrive
whole or not at all — streaming is a possible later upgrade); single-model,
no fallback; retrieval is keyword-based, not semantic (no embeddings/vector
store in this phase); PDF extraction covers text-based PDFs only; each ask
re-reads and re-extracts candidate documents (no caching); the free
OpenRouter route's availability is not guaranteed.

## License / scope

Personal use, college evaluation, and portfolio presentation. Not a production service.
