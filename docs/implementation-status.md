# AI Digital Locker — Implementation Status

Statuses: `Complete`, `Partial`, `Missing`, `Deferred`, `Unknown`. Evidence is based on
repository source, tests, Git history, and README reports; live end-to-end verification
is deferred.

| Requirement | Status | Evidence / source | Notes |
|---|---|---|---|
| Email/password registration and login | Complete | `backend/app/routers/auth.py`, `backend/tests/test_auth.py`; web/desktop mocked tests | Valid live login not re-run in Phase 10 |
| Opaque database-backed sessions | Complete | `backend/app/db.py`, `auth.py`; README Auth | Live valid flow not re-run; invalid-token smoke checks performed |
| PBKDF2-HMAC-SHA256 for new passwords | Complete | `backend/app/security.py`; tests | 600k iterations, 16-byte salt, 32-byte key |
| Legacy bcrypt fallback retained | Partial | `backend/app/security.py`, `backend/tests/test_auth.py`, `backend/requirements.txt` | Live 2026-10-28 read-only check found 2 legacy bcrypt hashes; fallback rehashes after successful login and stays until the count is zero |
| Documents upload/download/list/search/sort/rename/delete | Complete | `backend/app/routers/documents.py`; `backend/tests/test_documents.py` | Live upload/download not re-run in Phase 10 |
| 500 MB per-user quota and 50 MB file cap | Complete | `backend/app/config.py`, `routers/documents.py`; README | Quota race documented as negligible |
| Duplicate filenames allowed | Complete | Spec §8; implementation uses unique document IDs | Tested |
| Flat collection, no folders | Complete | By design; spec §9 | No folder code |
| Single administrator, manual bootstrap | Complete | `backend/scripts/make_admin.py`, `routers/admin.py`; README Admin | Owner-confirmed live admin API login HTTP 200; Django admin password login not verified live |
| Read-only admin API and web dashboard | Complete | `routers/admin.py`, `web/locker/views.py`, templates | `is_admin` re-checked per request |
| Audited admin downloads | Complete | `routers/admin.py` application logging | Not a database audit table; retention host-dependent |
| Cloud AI via OpenRouter (ask/summarize/suggest) | Complete | `routers/ai.py`, `ai_client.py`, `extract.py`; mocked tests | Live AI not re-run in Phase 10; free route availability not guaranteed |
| Local AI placeholder only | Complete | UI shows disabled Local AI; no inference backend | Never presented as working |
| Google Sheets document registry/reporting | Complete | `backend/app/sheets.py`, `routers/documents.py`, `tests/test_sheets.py`; mocked tests | Best-effort secondary reporting layer per spec §22/§23; no real spreadsheet writes in tests |
| No document sharing, folders, multi-admin | Complete | By design; spec §25/§28 | No related code |
| RLS deny-by-default, service-role backend only | Complete | `supabase/schema.sql`; backend service-role key | Clients never hold service-role key |
| 72-byte password policy retained | Complete | `backend/app/security.py`, `schemas.py`; README | Registration behavior unchanged |

## Outstanding work
- Full live end-to-end verification: deferred.
- Legacy bcrypt migration: 2 live hashes remain; keep the fallback until the count
  is zero and removal is explicitly approved.
- Spec §32 open decisions: OpenRouter key arrangement, exact model, Google Sheets +
  single-admin scope, registration limits.