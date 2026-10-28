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
  Google Sheets: best-effort administrative metadata reporting (Phase 11A).
```

- **backend/** — shared FastAPI API: authentication, document operations, AI endpoints,
  read-only administrator endpoints, and optional Sheets reporting. The only component
  that holds Supabase, OpenRouter, and Google service-account credentials.
- **web/** — Django client (browser UI). Talks to FastAPI over HTTP.
- **desktop/** — Tkinter Windows client (`py locker.py`). Talks to FastAPI over
  HTTP; may keep optional local offline copies of documents (this device only).
- **supabase/** — current database schema (`schema.sql`: users, sessions,
  documents, RLS); apply it in the Supabase SQL Editor.

Key product rules (from the specification): 500 MB cloud storage per user, flat document
collection (no folders), duplicate filenames allowed, single administrator, no document
sharing, Local AI must never be presented as working.

## Repository layout

```
backend/          FastAPI backend (requirements.txt, .env.example)
web/              Django web client (requirements.txt, .env.example)
desktop/          Tkinter desktop client (requirements.txt)
supabase/         Current database schema (schema.sql)
.env.example      Root template: non-secret client config (FASTAPI_BASE_URL)
```

## Configuration and secrets

Real environment files (`.env`) are gitignored. Templates are committed:

- Root `.env.example` — `FASTAPI_BASE_URL` for the clients.
- `backend/.env.example` — Supabase URL + service-role key, OpenRouter key,
  admin email, session lifetime, storage limits.

Privileged credentials (Supabase service-role key, OpenRouter API key) exist
**only** in `backend/.env` on the server. They are never placed in the Django
or Tkinter clients and are never committed to Git.

## Development status

| Phase | Scope | Status |
|---|---|---|
| 1 | Repository foundation (this) | **Complete** |
| 2 | Supabase schema + private storage bucket | **Complete** |
| 3 | FastAPI core + smoke test | **Complete** |
| 4 | Authentication (register/login, opaque sessions, admin bootstrap) | **Complete** (bootstrap script: `backend/scripts/make_admin.py`) |
| 5 | Documents API (upload, quota, search, download, rename, delete) | **Complete** |
| 6 | Django web client | **Complete** |
| 7 | Tkinter desktop client | **Complete** |
| 8 | AI assistant (OpenRouter) | **Complete** |
| 9 | Admin access (manual bootstrap, read-only API, web dashboard) | **Complete** |
| 10 | Demo polish (setup/docs, runbook, smoke checks) | **Complete** |
| 11A | Google Sheets reporting and shared web/desktop visual refresh | **Complete** |

Phases 1–10 are implemented and committed. Phase 9 provides a single,
manually bootstrapped administrator with read-only FastAPI endpoints, a web-only
dashboard at `/admin/`, and audited cross-user downloads. Phase 10 adds no new
product features: it fixes the Windows setup flow (Django database migration and
a non-conflicting web port), documents the opaque-session/PBKDF2 implementation,
and adds the repeatable demo runbook below. Phase 11A adds best-effort Google
Sheets metadata reporting and the shared web/desktop visual refresh, and the
desktop client has no admin UI. The specification's §32
open-decision list is preserved as written; this README does not treat those
entries as newly settled. Target Python version: **3.14** (verified locally on
3.14.6; Django 6.1 and current FastAPI both support it).

## Setup — backend (Windows, Python 3.14 via the `py` launcher)

Prerequisites: Python 3.14 installed (the Windows `py` launcher must work) and a
Supabase project prepared once:

1. In the Supabase SQL Editor, run [`supabase/schema.sql`](supabase/schema.sql)
   (users, `auth_sessions`, documents, and RLS).
2. In Storage, create a **private** bucket named `documents`. The backend uses
   the service-role key; no public bucket policy is needed.
3. In Project Settings -> API, copy the project URL and `service_role` key into
   `backend/.env` (never into a client or Git).

The existing demo project already has these. A fresh Supabase project needs all
three steps before the API can authenticate or store files.

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
:: Fill in SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (required), set
:: ADMIN_EMAIL for the admin bootstrap, and adjust optional values. Placeholder
:: values are rejected at startup.

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
(no Supabase Auth). Passwords are hashed with PBKDF2-HMAC-SHA256
(`hashlib.pbkdf2_hmac`, 600,000 iterations, a 16-byte random salt, and a
32-byte derived key). Login creates a random opaque session token; only its
SHA-256 hash is stored in `public.auth_sessions`. The raw token is returned in
the login response and sent back as a Bearer token. Sessions expire after
`SESSION_EXPIRY_MINUTES` (default 24 h), and logout deletes the row to revoke
the session immediately.

```bat
:: With the server running (uvicorn app.main:app --reload):
curl -X POST http://127.0.0.1:8000/auth/register -H "Content-Type: application/json" -d "{\"email\":\"demo@example.com\",\"password\":\"correct-horse-1\"}"
curl -X POST http://127.0.0.1:8000/auth/login    -H "Content-Type: application/json" -d "{\"email\":\"demo@example.com\",\"password\":\"correct-horse-1\"}"
curl http://127.0.0.1:8000/auth/me -H "Authorization: Bearer <access_token>"
curl -X POST http://127.0.0.1:8000/auth/logout -H "Authorization: Bearer <access_token>"
```

**Required schema.** The `auth_sessions` table must exist before login works.
Apply the current [`supabase/schema.sql`](supabase/schema.sql) in the Supabase
SQL Editor, or run only this migration:

```sql
create table if not exists public.auth_sessions (
    token_hash text primary key,
    user_id    uuid not null references public.users (id) on delete cascade,
    expires_at timestamptz not null,
    created_at timestamptz not null default now()
);

create index if not exists auth_sessions_user_id_idx
    on public.auth_sessions (user_id);

alter table public.auth_sessions enable row level security;
```

There is no data migration: tokens issued by the previous signed-token
implementation are not valid session rows, so every user logs in again once
after deploying this schema and backend version. No cleanup job is required;
expired rows are ignored by the backend and can be deleted manually if desired.

**Live deployment status (2026-10-27).** The owner's live Supabase project has
the `auth_sessions` table, RLS, and service-role permissions applied; an
owner-confirmed admin API login returned HTTP 200. Phase 10's local live smoke
checks confirmed the backend can read the session table (invalid bearer ->
401), run the logout delete path (bogus token -> 204), and read users for an
unknown-email login (401). The Phase 10 harness did not perform a valid-password
login. A new Supabase project still needs the SQL above applied first.

**Password hash migration.** Existing legacy bcrypt hashes
(`$2a$`/`$2b$`/`$2y$`) remain valid while the `bcrypt` package is present.
After a successful login, the backend transparently replaces that user's stored
hash with a PBKDF2 hash; the password itself is unchanged and no reset is
required. New registrations use PBKDF2 immediately. The existing user id,
`is_admin` flag, and documents are untouched. There is no database schema
change. To check whether any legacy hashes remain:

```sql
select count(*) as legacy_hashes
from public.users
where password_hash like '$2%';
```

Keep the bcrypt fallback and dependency until this count is zero. Accounts that
never log in remain legacy; do not remove the fallback until they have either
logged in or been explicitly reset by the owner.

**Phase 11A live check (2026-10-28).** A read-only query against the live
`public.users` table found **2 legacy bcrypt hashes**. No user records or
password hashes were changed. The bcrypt fallback remains installed until the
count is zero and the owner explicitly approves its removal.

Rules enforced by the API: emails are normalized to lowercase (duplicate
registration is case-insensitive); passwords must be 8-72 UTF-8 bytes (never
truncated; the 72-byte cap is retained as a project policy); `is_admin` cannot
be set through registration; login returns one generic error for wrong password
or unknown email; the authenticated user id comes only from the active session
row. Tests use an in-memory fake store - no real Supabase project or `.env` is
needed for `py -m pytest`.

**Single administrator (manual bootstrap):** `ADMIN_EMAIL` in `backend/.env`
identifies the one account eligible for explicit promotion. Register that
account through the normal client flow first, then run the owner-run script
once from `backend/`:

```bat
.venv\Scripts\python.exe scripts\make_admin.py
```

The script promotes only the existing normalized `ADMIN_EMAIL` account,
creates no accounts, changes no passwords, and is idempotent. It is never
invoked automatically at startup, registration, or request time. The admin API
and the web-only dashboard are implemented in Phase 9 (see below); the desktop
client has no admin UI.

## Documents API (Phase 5)

All routes require `Authorization: Bearer <access_token>`; the user is always
resolved from the active session (never from request data).

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

Supabase notes: project `ai-digital-locker` (ap-south-1); tables `public.users`,
`public.auth_sessions`, and `public.documents` with RLS enabled; private Storage
bucket `documents`.
The Supabase Free plan caps each uploaded object at 50 MB
(`MAX_UPLOAD_BYTES=52428800`); the application-level per-user quota remains
500 MB (`STORAGE_QUOTA_BYTES=524288000`).

## Web client — Django (Phase 6)

Django provides the UI and session management; FastAPI remains the sole API and
authorization boundary. Django calls FastAPI over HTTP only — it never touches
Supabase and never holds service-role credentials.

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

:: 3. Create/upgrade Django's local session database (required on a fresh clone)
py manage.py migrate

:: 4. Tests (all FastAPI calls are mocked; backend must NOT be running for clarity)
py manage.py test

:: 5. Run on 8001 so it does not collide with FastAPI on 8000
py manage.py runserver 8001
:: Open http://127.0.0.1:8001/  ->  register, upload, search, sort, download
```

What works: registration with automatic login, login, POST-only logout,
authenticated dashboard with a 500 MB usage bar, upload (50 MiB UI hint,
FastAPI authoritative), filename search, sort/order, MIME-type filter,
streaming download proxy, rename, and delete behind a confirmation page.
Expired sessions (401) flush Django state and redirect to login; API/network
failures show safe generic messages.

Security posture: the FastAPI session token lives only in Django's
server-side session store (database-backed cookie holds an opaque session key — HttpOnly,
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

**Sessions:** the session token is stored in plaintext at
`%APPDATA%\AiDigitalLocker\session.json` (per-user folder, atomic writes).
It is never printed, logged, shown in the UI, or placed in a URL. Logout
clears it locally and best-effort revokes the server-side session. Same-
Windows-user access to that file is a documented limitation; OS-level
encryption (DPAPI) is possible future hardening.

**Offline copies (spec §11):** optional per-device copies live under
`desktop/offline/<document_id>/<filename>` (gitignored). They never
synchronize across devices or with later cloud changes; they are not
deleted on logout; cloud renames/deletes do not touch them; they are
plain local files. Downloads stream to a temp file and are moved into
place only when complete.

**Known limitations:** one network operation at a time (buttons disable
while one runs); the 50 MiB/500 MB messages rely on the backend's exact
413 wording (pinned by backend tests); if the backend is unreachable during
logout, local state is still cleared but the server-side row remains until it
expires (24 h by default).

## AI assistant — Cloud AI via OpenRouter (Phase 8)

The assistant is optional: the locker is fully usable without it (spec §17).
It runs entirely inside the FastAPI backend, which is the only component
holding the OpenRouter key. Clients pass a Bearer session token; every AI
endpoint resolves the user from the active session and touches documents only
via the same user-scoped database/storage paths the rest of the API uses.

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

**Verification status (Phase 8):**

- **Live manual tests (previously reported):** AI question answering, document
  summarization, and filename suggestions were manually verified end-to-end
  against the real backend, Supabase, and OpenRouter in both the Django web
  client and the Tkinter desktop client. Happy paths only; filename
  suggestions required explicit user confirmation before renaming.
- **Automated tests (historical results):** backend 104, web 37, and desktop
  37 tests passing after the Phase 8 review fixes. Every automated test mocks
  external services (Supabase, OpenRouter, and the clients' HTTP calls); no
  automated integration test calls a live service.
- **Not verified live:** provider-unavailable 503 responses, retrieval
  no-match short-circuits, unsupported/encrypted/corrupt file handling, and
  hostile-filename escaping are exercised by mocked tests only — they have
  not been run against live services.

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

## Admin — single administrator (Phase 9)

Phase 9 is deliberately read-only. There is exactly one administrator, selected
by the owner and promoted manually; registration can never grant admin.

**Bootstrap (owner-run, once per deployment).** Set `ADMIN_EMAIL` in
`backend/.env`, register that account through the normal client flow first, then
run from `backend/`:

```bat
.venv\Scripts\python.exe scripts\make_admin.py
```

The script accepts no arguments, creates no accounts, changes no passwords, and
is idempotent. It is never invoked automatically at startup, registration, or
request time.

**FastAPI endpoints (read-only; administrator required):**

| Route | Purpose |
|---|---|
| `GET /admin/users` | All accounts: id, email, `is_admin`, created_at |
| `GET /admin/documents` | All documents with owner email; metadata only |
| `GET /admin/documents/{id}` | Audited download proxied by the backend |

Each route re-checks `users.is_admin` from the database on every request, so a
normal user receives 403 even with a session created while the account was an
admin.
Listings omit storage paths and document contents.

**Web dashboard (Django, `/admin/`).** Read-only users and documents tables;
each document can be downloaded through Django → FastAPI. The Admin nav link is
shown only when the session flag says the user is an administrator, but that
flag is cosmetic: FastAPI performs the real check on every request. Network,
401, 403, and 404 failures show safe messages, and the listing exposes no
document contents or storage paths. The desktop client has no admin UI.

**Privacy boundary.** An administrator can download every user's documents by
design. Successful admin downloads are recorded in the backend application log
with administrator id and email, document id, owner id, and a UTC timestamp.
Failed Storage retrievals return a controlled 500 and do not write a
successful-download audit entry. This is an application log, not a database
audit table; retention depends on how the backend is hosted.

**Google Sheets** is implemented as an optional, best-effort administrative
metadata registry (Phase 11A, below). It is not the primary database and never
receives document contents, passwords, session tokens, or credentials.

**Verification status (Phase 9):**

- **Live verification (2026-10-21, owner-confirmed account):** scripted HTTP
  checks against temporary local FastAPI and Django instances connected to the
  real Supabase project. The bootstrap promoted the existing account;
  administrator API listings returned real data; the Django `/admin/` page
  rendered users/documents with formatted UTC timestamps; an administrator
  download through Django → FastAPI returned the file as an attachment; the
  audit log contained the administrator id, document id, and a UTC timestamp; a
  normal user received 403 on all admin endpoints; a forged admin session flag
  was still denied; owner-scoped document routes returned 404 for a foreign
  document; and a temporary metadata row with a missing Storage object returned
  500 with no successful-download audit entry. The temporary row was removed,
  web checks used a server-side session carrying a real administrator access
  token, and no secrets were printed; no browser password login was performed.
- **Not verified live:** Django password login for the administrator (the
  password was not available to the verification harness; the login page itself
  renders), and a live registration attempt supplying `is_admin=true` (mocked
  test only, to avoid creating a disposable account).
- **Automated tests (current):** backend 169, web 61, desktop 39 — all passing and
  all external services mocked. They do not prove live behavior.

## Demo runbook (Phase 10)

Use the setup sections above first. A fresh web checkout **must** run
`py manage.py migrate` before the first `runserver`; that creates Django's
server-side session table. Keep FastAPI on port 8000 and Django on port 8001 so
the two local servers do not collide.

### Start the three components

```bat
:: Terminal 1 - FastAPI backend
cd backend
.venv\Scripts\activate
uvicorn app.main:app --reload
:: health: http://127.0.0.1:8000/health

:: Terminal 2 - Django web client
cd web
.venv\Scripts\activate
py manage.py migrate
py manage.py runserver 8001
:: open: http://127.0.0.1:8001/

:: Terminal 3 - Tkinter desktop client
cd desktop
.venv\Scripts\activate
py locker.py
```

### Demonstration checklist

Use synthetic/sample documents, not real personal records. Cloud AI sends the
selected document text to OpenRouter; Local AI is only a disabled placeholder.

- [ ] Register a demo account and confirm the dashboard shows `0 B / 500 MB`.
- [ ] Upload a small TXT, PDF, or DOCX file. Upload a second file with the same
      visible name; both must remain separate documents (spec §8).
- [ ] Search by filename, sort by name/size/date, and filter by MIME type.
- [ ] Rename one document, download it, delete one duplicate, and confirm the
      usage bar/count changes.
- [ ] Open the AI assistant, ask a question about an uploaded text-extractable
      document, summarize it, and request a filename suggestion. Apply the
      suggested name only through the explicit confirmation/rename flow. If the
      free OpenRouter route is unavailable, show the clear 503 message and that
      the locker still works without AI.
- [ ] In the desktop client, log in as the same user, upload with **Keep Offline
      Copy**, download, rename, delete, and open the AI dialog. Confirm Local AI
      is visibly disabled and cannot claim to run locally.
- [ ] Log out in both clients and log in again. Show that a wrong password gets
      the same generic error as an unknown email.
- [ ] Admin only: log in as the promoted account, open `/admin/`, verify the
      read-only user/document lists, and download one document. The desktop
      client intentionally has no admin UI.
- [ ] Remove disposable demo documents from the account when finished.

### Phase 10 verification (2026-10-27)

- **Automated:** backend 144, web 52, desktop 39 passing; Django `check` and
  `migrate --check` pass. All external services are mocked in these tests.
- **Local live smoke checks (real backend `.env` and real Supabase):**
  `/health` returned 200; invalid-token `/auth/me` returned 401; invalid-token
  `/auth/logout` returned 204; unknown-email `/auth/login` returned 401;
  invalid-token `/ai/status` returned 401. Django on port 8001 served
  `/login/` and `/register/` with 200 and a CSRF token; `/` and `/admin/`
  redirected unauthenticated visitors to login. This proves local wiring and
  session-table access, not a successful credential flow.
- **Owner-confirmed (not repeated by this harness):** a live admin API login
  returned HTTP 200 after the `auth_sessions` rollout.
- **Not re-run in Phase 10:** valid-password login from this harness, live
  upload/download/Storage, live OpenRouter AI, browser interaction, or desktop
  against the live backend. Earlier phases reported live AI/Storage checks;
  those remain historical claims.
- **Auth migration:** the live users table had 2 legacy bcrypt hashes at the
  2026-10-28 check (read-only). The bcrypt fallback remains installed until the
  count is zero and the owner explicitly approves its removal.

## Google Sheets reporting (Phase 11A)

Per spec §22/§23, Google Sheets is an administrative document registry and
reporting layer. It is **not** the primary database — Supabase PostgreSQL remains
the source of truth for document metadata, and Supabase Storage remains the file
store. Sheets is a secondary, best-effort reporting layer.

### What is reported

Each document is represented by one row with these eight columns, in order:

1. Document ID
2. User Email
3. Filename
4. File Type
5. File Size
6. Upload Time
7. Last Modified
8. Storage Mode

Document contents, file bytes, passwords, session tokens, and credentials are
**never** sent to Google Sheets. Only the metadata above is shared.

### Synchronization behavior

- **Upload:** after the document and metadata are created in Supabase, a
  corresponding spreadsheet row is created or updated.
- **Rename:** the existing row identified by Document ID is updated in place;
  no duplicate row is appended.
- **Delete:** the corresponding registry row is removed when the document is
  successfully deleted.
- **Idempotency:** rows are matched by Document ID, so retries do not create
  duplicate rows.

Sheets is a secondary system: a configuration or API failure is logged and
swallowed, and it never turns a successful document operation into a user-facing
failure. Document uploads, renames, and deletes succeed even if Sheets is not
configured or unreachable.

### Setup

1. Create a Google Sheet with the header row:
   `Document ID, User Email, Filename, File Type, File Size, Upload Time,
   Last Modified, Storage Mode`. The backend targets the spreadsheet's first
   worksheet, whatever its title is.
2. Share the spreadsheet with the Google service-account identity
   (`client_email` in your service-account JSON key) so it can write.
3. Copy `backend/.env.example` to `backend/.env` and set:
   - `GOOGLE_SHEET_ID` — the ID from the spreadsheet URL.
   - `GOOGLE_SERVICE_ACCOUNT_FILE` — path to the service-account JSON key file
     (server-only; never commit it).
4. Restart the backend.

If `GOOGLE_SHEET_ID` is not set, the backend starts and runs normally without
Sheets reporting.

### Limitations

- Reporting is best-effort and not transactional with Supabase; a sheet write
  that fails is logged but does not roll back the document operation.
- The first worksheet's `sheetId` and title are discovered when the backend
  first connects; if the worksheet is renamed or removed later, reporting may
  fail until the backend is restarted.
- No retry mechanism beyond the single API call is implemented; transient
  failures are logged and skipped.
- Concurrent updates to the sheet from multiple processes are not coordinated;
  a read-then-write cycle can target a stale row if another writer changes the
  sheet in between.
