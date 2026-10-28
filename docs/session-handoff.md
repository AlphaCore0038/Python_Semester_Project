# AI Digital Locker — Session Handoff

## Read first
1. `PROJECT_CONTEXT.md`
2. `AGENTS.md`
3. `README.md`
4. `AI_Digital_Locker_Project_Specification(2).md`, especially §32 open decisions

## Current state
- Branch: `main`; use `git log -1 --oneline` and
  `git status --short --branch` for the current HEAD and working tree.
- Phases 1-10 are complete per `README.md`; Phase 11A (Google Sheets reporting)
  and the shared web/desktop visual refresh are implemented and tested.
- Tests: backend 169, web 61, desktop 39 all passing; Django `check` clean.
- Outstanding work: full live end-to-end verification (deferred), spec §32 open
  decisions, and the remaining legacy bcrypt migration (2 live hashes).

## Decisions that must not be reversed
- Django web + Tkinter desktop + shared FastAPI backend.
- Supabase PostgreSQL + Storage; OpenRouter cloud AI only; Local AI placeholder.
- Opaque database-backed sessions; no JWT/HS256.
- PBKDF2 for new passwords; legacy bcrypt fallback retained and rehashes after
  successful login until the live legacy count is zero.
- Single admin via manual `ADMIN_EMAIL` bootstrap; `is_admin` re-checked per request.
- AI suggestions require explicit user confirmation.
- Google Sheets reporting implemented (Phase 11A) per spec §22/§23; no sharing/
  folders/multi-admin/enterprise infrastructure.

## In-progress work and blockers
- The Phase 11A/final UI changes are complete; verify the commit before live checks.
- Blocker: full live end-to-end verification remains deferred.
- Blocker: 2 live legacy bcrypt hashes remain; do not remove the fallback without
  owner approval and a zero count.

## Safe Git practices
- Recheck `git status --short --branch`, `git rev-parse HEAD`, and
  `git rev-parse origin/main` before editing.
- Never commit `.env`, credentials, tokens, passwords, or private environment values.
- Do not stage anything inside `graphify-out/`; review `.gitignore` changes as
  intentional configuration.
- Stage only intended files; do not amend, rebase, force-push, or create empty commits.
- Do not commit or push until explicitly asked.

## Recommended next step
Verify the Phase 11A/final UI commit, then proceed to full live
end-to-end verification. Keep the bcrypt fallback until the legacy count is zero
and removal is explicitly approved.