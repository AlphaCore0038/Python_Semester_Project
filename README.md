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
  PostgreSQL + Storage       Cloud AI (MiMo-V2.6-Flash)
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
| 2 | Supabase schema + private storage bucket | Not started |
| 3 | FastAPI core + smoke test | Not started |
| 4 | Authentication (register/login, JWT, admin bootstrap) | Not started |
| 5 | Documents API (upload, quota, search, download, rename, delete) | Not started |
| 6 | Django web client | Not started |
| 7 | Tkinter desktop client | Not started |
| 8 | AI assistant (OpenRouter) | Not started |
| 9 | Admin access + Google Sheets registry (deferred) | Not started |
| 10 | Demo polish | Not started |

No application code exists yet. Target Python version: **3.14** (Django 6.1 and current
FastAPI both support it).

## Setup (once application phases begin)

```bat
py -m venv backend\.venv
backend\.venv\Scripts\activate
pip install -r backend\requirements.txt
copy backend\.env.example backend\.env
:: fill in backend\.env with real values, then run uvicorn (Phase 3)
```

Similar venvs are used for `web/` and `desktop/` when those clients are built.

## License / scope

Personal use, college evaluation, and portfolio presentation. Not a production service.
