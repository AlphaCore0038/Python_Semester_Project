# AI Digital Locker — Architecture Map

## Components and responsibilities
| Component | Path | Responsibilities | Credentials held |
|---|---|---|---|
| FastAPI backend | `backend/app/` | Auth, documents, AI, read-only admin API, Sheets reporting; sole backend credential holder | Supabase service-role key, OpenRouter API key, optional Google service-account key |
| Django web client | `web/` | Browser UI; server-side session store for opaque token; calls FastAPI over HTTP only | None |
| Tkinter desktop | `desktop/` | Windows GUI; calls FastAPI over HTTP; optional per-device offline copies | None |
| Supabase | `supabase/schema.sql` | PostgreSQL metadata + private Storage bucket `documents`; RLS deny-by-default | None in clients |

## Data flows
- Clients → FastAPI over HTTP with `Authorization: Bearer <opaque_token>`.
- FastAPI → Supabase using service-role key (bypasses RLS); application code enforces
  authorization by session user id.
- FastAPI → OpenRouter for AI; clients never hold the OpenRouter key.
- Django stores the FastAPI token in its server-side session; never renders it to HTML,
  URLs, or JavaScript.
- Desktop persists the token at `%APPDATA%\AiDigitalLocker\session.json` (plaintext,
  same-Windows-user limitation documented).

## Authentication and authorization
- `backend/app/security.py`: `hash_password`, `verify_password`, `needs_rehash`,
  `new_session_token`, `hash_session_token`.
- `backend/app/routers/auth.py`: `POST /auth/register`, `POST /auth/login`,
  `POST /auth/logout`, `GET /auth/me`.
- `backend/app/deps.py`: `get_current_user` validates the session hash, expiry, and user
  row; `require_admin` re-checks `users.is_admin` from the database per request.
- `backend/app/db.py`: user/session/document access; `update_password_hash` used only
  after successful legacy login.
- Passwords: PBKDF2-HMAC-SHA256 for new hashes; legacy bcrypt fallback retained
  for 2 remaining live hashes and transparently rehashes after successful login;
  8–72 UTF-8 byte password policy retained.
- Sessions: opaque token returned at login; SHA-256 hash stored in `auth_sessions`;
  logout deletes the row; expired rows ignored by backend.

## Documents
- `backend/app/routers/documents.py`: upload (50 MB file cap, 500 MB quota), list
  (search/sort/order/file_type), usage, download, rename (metadata only), delete
  (row then best-effort Storage cleanup).
- Object keys: `{user_id}/{document_id}`; Storage object never moves on rename.
- Duplicate filenames allowed; flat collection; no folders; no sharing.

## AI assistant
- `backend/app/routers/ai.py`, `backend/app/ai_client.py`, `backend/app/extract.py`.
- Endpoints: `GET /ai/status`, `POST /ai/ask`, `POST /ai/summarize`,
  `POST /ai/suggest-filename`.
- Keyword-window retrieval over the user's own documents; model not called when no
  relevant documents found; fixed system prompt treats document text as untrusted.
- Filename suggestions are proposals only; applying uses the existing validated rename
  path with explicit user confirmation.
- Text extraction: TXT, PDF, DOCX only; no OCR.

## Admin
- `backend/scripts/make_admin.py`: owner-run, idempotent, promotes one existing account
  matching `ADMIN_EMAIL`; creates no accounts, changes no passwords.
- `backend/app/routers/admin.py`: read-only `GET /admin/users`,
  `GET /admin/documents`, `GET /admin/documents/{id}`; audited application log for
  successful admin downloads (not a database audit table; retention depends on host).
- Django web dashboard at `/admin/` is read-only; desktop has no admin UI.

## Google Sheets reporting
- `backend/app/sheets.py`: lazy best-effort Google Sheets reporting client
  (`SheetsClient`). Imports Google API libraries only on first use; all
  operations are no-ops when Sheets is not configured or unreachable. Failures
  are logged and never fail a document operation.
- `backend/app/routers/documents.py`: calls `sheets.report_document` after
  upload and rename, and `sheets.delete_document_row` after delete, best-effort.
- `backend/app/db.py`: `get_document_report_row` combines document metadata with
  the owner email for the "User Email" column.
- Eight columns per spec §22: Document ID, User Email, Filename, File Type,
  File Size, Upload Time, Last Modified, Storage Mode.
- Rows are matched by Document ID for idempotent upsert/delete.

## Graphify findings
- Artifacts: `graphify-out/` (intentionally dirty, never staged).
- Last local refresh: 2026-10-28 from commit `cff62e88`; 1136 nodes, 2333 edges,
  76 communities. The artifacts are unstaged and may be newer than the committed
  snapshot; refresh after code changes.
- God nodes include `token_for()`, `make_user()`, `FakeUserStore`, `MainView`,
  `ApiClient`, `upload()`, `get_supabase()`.
- `graphify path` uses directed call edges; `graphify query` is better for scoped
  subgraphs. Never treat the graph as more authoritative than source code.
- Refresh after code changes: `graphify update .` (AST-only, no API cost).