





































create table if not exists public.users (
    id            uuid primary key default gen_random_uuid(),
    email         text not null,
    password_hash text not null,
    is_admin      boolean not null default false,
    created_at    timestamptz not null default now()
);


create unique index if not exists users_email_lower_key
    on public.users (lower(email));








create table if not exists public.auth_sessions (
    token_hash text primary key,
    user_id    uuid not null references public.users (id) on delete cascade,
    expires_at timestamptz not null,
    created_at timestamptz not null default now()
);

create index if not exists auth_sessions_user_id_idx
    on public.auth_sessions (user_id);














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


create index if not exists documents_user_id_idx
    on public.documents (user_id);


create index if not exists documents_user_created_idx
    on public.documents (user_id, created_at desc);







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









alter table public.users enable row level security;
alter table public.auth_sessions enable row level security;
alter table public.documents enable row level security;
