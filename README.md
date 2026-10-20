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
| 2 | Supabase schema + private storage bucket | **Complete** |
| 3 | FastAPI core + smoke test | **Complete** |
| 4 | Authentication (register/login, JWT, admin bootstrap) | Not started |
| 5 | Documents API (upload, quota, search, download, rename, delete) | Not started |
| 6 | Django web client | Not started |
| 7 | Tkinter desktop client | Not started |
| 8 | AI assistant (OpenRouter) | Not started |
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

The web (`web/`) and desktop (`desktop/`) clients get their own venvs when those
clients are built (later phases).

Supabase notes: project `ai-digital-locker` (ap-south-1); tables `public.users`
and `public.documents` with RLS enabled; private Storage bucket `documents`.
The Supabase Free plan caps each uploaded object at 50 MB
(`MAX_UPLOAD_BYTES=52428800`); the application-level per-user quota remains
500 MB (`STORAGE_QUOTA_BYTES=524288000`).

## License / scope

Personal use, college evaluation, and portfolio presentation. Not a production service.
