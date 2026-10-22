-- ============================================================================
-- AI Digital Locker — Supabase PostgreSQL schema (Phase 2A)
--
-- Source of truth: AI_Digital_Locker_Project_Specification(2).md
--   - Flat document collection, no folders, no sharing (spec sections 9, 25)
--   - Duplicate filenames allowed; unique internal ID per document (spec section 8)
--   - Account-level document separation; single administrator (spec sections 23-24)
--
-- How to initialize (new Supabase project):
--   1. Open the Supabase dashboard -> SQL Editor.
--   2. Paste this entire file and run it once.
--
-- Idempotency / safety:
--   - Safe to re-run on the same project: uses IF NOT EXISTS / CREATE OR REPLACE
--     and a guarded trigger creation. It never DROPs or deletes anything.
--   - If a table already exists with a DIFFERENT shape, IF NOT EXISTS will leave
--     it unchanged; schema changes after first run require a manual migration.
--
-- Security model:
--   - Both tables have Row Level Security enabled with NO policies for the
--     anon/authenticated roles => deny-by-default. There is no Supabase Auth
--     integration; our users are application users, so auth.uid() is not used.
--   - The FastAPI backend connects with the server-side service-role key
--     (which bypasses RLS) and MUST authorize every request in application
--     code: validate the opaque session token, scope every query by that
--     session's user id, and gate administrator routes on users.is_admin.
--   - Privileged credentials never appear in this file or in any client config.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- users
--   One row per registered account (email + password only, spec section 3).
--   is_admin is NEVER settable through the registration API; the single
--   administrator is promoted explicitly by the owner-run script
--   backend/scripts/make_admin.py using ADMIN_EMAIL from backend/.env.
--   Nothing promotes administrators automatically at startup.
-- ---------------------------------------------------------------------------

create table if not exists public.users (
    id            uuid primary key default gen_random_uuid(),
    email         text not null,
    password_hash text not null,
    is_admin      boolean not null default false,
    created_at    timestamptz not null default now()
);

-- Case-insensitive uniqueness: Alice@Example.com and alice@example.com collide.
create unique index if not exists users_email_lower_key
    on public.users (lower(email));

-- ---------------------------------------------------------------------------
-- auth_sessions
--   One row per active login. Only the SHA-256 hash of the opaque session
--   token is stored, never the raw token. Expiry is checked by FastAPI on
--   every request; logout deletes the row.
-- ---------------------------------------------------------------------------

create table if not exists public.auth_sessions (
    token_hash text primary key,
    user_id    uuid not null references public.users (id) on delete cascade,
    expires_at timestamptz not null,
    created_at timestamptz not null default now()
);

create index if not exists auth_sessions_user_id_idx
    on public.auth_sessions (user_id);

-- ---------------------------------------------------------------------------
-- documents
--   Metadata for one uploaded file. The visible filename may repeat for the
--   same user; id and storage_path keep every document distinct (spec section 8).
--
--   Storage-path convention (Supabase Storage object key):
--       {user_id}/{document_id}
--   The original filename lives ONLY in this table (filename column), never
--   in the Storage path — so renames are metadata-only updates and duplicate
--   filenames cannot collide in Storage. The Storage bucket itself is created
--   separately (not in this file).
-- ---------------------------------------------------------------------------

create table if not exists public.documents (
    id              uuid primary key default gen_random_uuid(),
    user_id         uuid not null references public.users (id) on delete cascade,
    filename        text not null check (length(filename) between 1 and 255),
    storage_path    text not null unique,
    file_type       text not null,
    file_size_bytes bigint not null check (file_size_bytes > 0),
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);

-- Ownership scoping and per-user quota SUM(file_size_bytes).
create index if not exists documents_user_id_idx
    on public.documents (user_id);

-- Default document listing: newest first, per user.
create index if not exists documents_user_created_idx
    on public.documents (user_id, created_at desc);

-- ---------------------------------------------------------------------------
-- updated_at maintenance
--   Keeps documents.updated_at honest on any metadata change (e.g. rename),
--   regardless of which tool performs the update.
-- ---------------------------------------------------------------------------

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at := now();
    return new;
end;
$$;

do $$
begin
    if not exists (
        select 1 from pg_trigger
        where tgname = 'documents_set_updated_at'
            and tgrelid = 'public.documents'::regclass
    ) then
        create trigger documents_set_updated_at
            before update on public.documents
            for each row
            execute function public.set_updated_at();
    end if;
end;
$$;

-- ---------------------------------------------------------------------------
-- Row Level Security — deny-by-default
--   Enabling RLS creates an implicit deny for every role. Because we add NO
--   policies for anon or authenticated, those roles can read/write nothing
--   here even if a non-privileged key were exposed. The backend's service
--   role bypasses RLS and is the only intended access path.
-- ---------------------------------------------------------------------------

alter table public.users enable row level security;
alter table public.auth_sessions enable row level security;
alter table public.documents enable row level security;
