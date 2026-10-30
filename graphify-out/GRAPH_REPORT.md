# Graph Report - PythonProject  (2026-10-30)

## Corpus Check
- 84 files · ~248,483 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1249 nodes · 2576 edges · 79 communities (55 shown, 17 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 51 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `9cb74f9d`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- AI_Digital_Locker_Project_Specification(2).md
- What You Must Do When Invoked
- ._seed_session
- graphify reference: extra exports and benchmark
- AI Digital Locker
- 14. AI Capabilities
- graphify reference: query, path, explain
- test_auth.py
- opencode.json
- graphify reference: add a URL and watch a folder
- graphify reference: commit hook and native CLAUDE.md integration
- graphify reference: incremental update and cluster-only
- extract_text
- storage.py
- token_for
- graphify.js
- graphify reference: GitHub clone and cross-repo merge
- graphify reference: transcribe video and audio
- AGENTS.md
- extraction-spec.md
- test_demo_drill.py
- 12. AI Assistant
- AI Digital Locker
- 21. Supabase
- 3. User Accounts
- 5. Document Storage
- 31. Scope Boundary
- locker/views.py
- main.py
- ApiClient
- settings.py
- Session
- TaskRunner
- SessionStore
- MainView
- documents.py
- schemas.py
- db.py
- load_settings
- ai.py
- test_sheets.py
- test_admin_bootstrap.py
- deps.py
- test_ui_smoke.py
- admin.py
- AITests
- AdminTests
- AuthFlowTests
- ._api_doc_calls
- DemoDriver
- main
- AI Digital Locker — Architecture Map
- AI Digital Locker — Project Context
- AI Digital Locker — Project History
- AI Digital Locker — Session Handoff
- AI Digital Locker — Graphify Reference
- AI Digital Locker — Implementation Status
- tests.py
- theme.py
- LoginView
- DemoAccount
- ._upload_document
- _make_handler
- scripts/__init__.py
- ._status
- StaticAssetTests
- Google Sheets reporting (Phase 11A)
- Django web client
- Demo runbook (Phase 10)
- ServerHud
- SheetsClient
- hud_tee.py

## God Nodes (most connected - your core abstractions)
1. `token_for()` - 60 edges
2. `make_user()` - 58 edges
3. `FakeUserStore` - 42 edges
4. `MainView` - 39 edges
5. `ApiClient` - 30 edges
6. `upload()` - 29 edges
7. `get_supabase()` - 26 edges
8. `ServerHud` - 25 edges
9. `_call()` - 22 edges
10. `ApiError` - 21 edges

## Surprising Connections (you probably didn't know these)
- `delete_document()` --references--> `delete()`  [EXTRACTED]
  backend/app/routers/documents.py → web/locker/fastapi_client.py
- `test_main_rejects_arguments_without_loading_settings()` --indirect_call--> `make_admin()`  [INFERRED]
  backend/tests/test_admin_bootstrap.py → backend/tests/test_admin.py
- `test_main_reports_configuration_errors_safely()` --indirect_call--> `make_admin()`  [INFERRED]
  backend/tests/test_admin_bootstrap.py → backend/tests/test_admin.py
- `test_main_reports_database_failure_without_leaking_details()` --indirect_call--> `make_admin()`  [INFERRED]
  backend/tests/test_admin_bootstrap.py → backend/tests/test_admin.py
- `ai_ask()` --uses--> `AskRequest`  [INFERRED]
  backend/app/routers/ai.py → backend/app/schemas.py

## Import Cycles
- None detected.

## Communities (79 total, 17 thin omitted)

### Community 0 - "AI_Digital_Locker_Project_Specification(2).md"
Cohesion: 0.08
Nodes (23): 10. File Access, 11. Offline Storage, 13. AI User Interface, 15. AI and Document Modification, 16. AI and Backend Access, 17. AI Installation and Availability, 18. Web Application, 19. Desktop Application (+15 more)

### Community 1 - "What You Must Do When Invoked"
Cohesion: 0.08
Nodes (24): For /graphify add and --watch, For /graphify query, For the commit hook and native CLAUDE.md integration, For --update and --cluster-only, /graphify, Honesty Rules, Interpreter guard for subcommands, Part A - Structural extraction for code files (+16 more)

### Community 2 - "._seed_session"
Cohesion: 0.18
Nodes (3): DashboardTests, DocumentActionTests, Simulate an already-authenticated session.

### Community 3 - "graphify reference: extra exports and benchmark"
Cohesion: 0.22
Nodes (8): graphify reference: extra exports and benchmark, Step 6b - Wiki (only if --wiki flag), Step 7 - Neo4j export (only if --neo4j or --neo4j-push flag), Step 7a - FalkorDB export (only if --falkordb or --falkordb-push flag), Step 7b - SVG export (only if --svg flag), Step 7c - GraphML export (only if --graphml flag), Step 7d - MCP server (only if --mcp flag), Step 8 - Token reduction benchmark (only if total_words > 5000)

### Community 4 - "AI Digital Locker"
Cohesion: 0.15
Nodes (12): Admin — single administrator (Phase 9), AI assistant — Cloud AI via OpenRouter (Phase 8), AI Digital Locker, Architecture, Authentication (Phase 4), Configuration and secrets, Desktop client — Tkinter (Phase 7), Development status (+4 more)

### Community 5 - "14. AI Capabilities"
Cohesion: 0.29
Nodes (7): 14. AI Capabilities, Document Assistance, Document Reading, Filename Suggestions, Information Retrieval, Search, Summarization

### Community 6 - "graphify reference: query, path, explain"
Cohesion: 0.33
Nodes (5): For /graphify explain, For /graphify path, graphify reference: query, path, explain, Step 0 — Constrained query expansion (REQUIRED before traversal), Step 1 — Traversal

### Community 7 - "test_auth.py"
Cohesion: 0.12
Nodes (35): auth_header(), client(), FakeUserStore, login(), make_token(), fixture, MonkeyPatch, parametrize (+27 more)

### Community 8 - "opencode.json"
Cohesion: 0.50
Nodes (3): plugin, $schema, .opencode/plugins/graphify.js

### Community 9 - "graphify reference: add a URL and watch a folder"
Cohesion: 0.50
Nodes (3): For /graphify add, For --watch, graphify reference: add a URL and watch a folder

### Community 10 - "graphify reference: commit hook and native CLAUDE.md integration"
Cohesion: 0.50
Nodes (3): For git commit hook, For native CLAUDE.md integration, graphify reference: commit hook and native CLAUDE.md integration

### Community 11 - "graphify reference: incremental update and cluster-only"
Cohesion: 0.50
Nodes (3): For --cluster-only, For --update (incremental re-extraction), graphify reference: incremental update and cluster-only

### Community 12 - "extract_text"
Cohesion: 0.17
Nodes (22): extract_text(), ExtractionResult, _finalize(), _from_docx(), _from_pdf(), _from_text(), Text extraction for AI context - TXT, PDF, and DOCX only. Honest by design:…, Best-effort text extraction; never raises for bad user files. (+14 more)

### Community 13 - "storage.py"
Cohesion: 0.13
Nodes (15): download_object(), Thin Supabase Storage wrapper for the private 'documents' bucket (Phase 5).…, upload_object(), FakeBucket, FakeStorage, FakeSupabase, Regression tests for the Supabase Storage wrapper. The live bug: upload() was…, The installed SDK must accept file_options and NOT content_type. (+7 more)

### Community 15 - "token_for"
Cohesion: 0.06
Nodes (93): client(), env(), make_admin(), fixture, MonkeyPatch, TestClient, Admin API tests — read-only endpoints, fake DB/storage, no live services., test_admin_documents_lists_all_owners_with_email() (+85 more)

### Community 22 - "test_demo_drill.py"
Cohesion: 0.11
Nodes (26): _make_driver(), MonkeyPatch, Demo traffic simulator tests — mocked HTTP client; no real calls. All tests use…, Successful upload adds document to account's tracked list., Failed upload returns None and doesn't add document., Listing documents makes a GET request., Downloading a document owned by the account succeeds., Renaming a document owned by the account succeeds. (+18 more)

### Community 23 - "12. AI Assistant"
Cohesion: 0.40
Nodes (5): 12. AI Assistant, AI Options, Cloud AI — OpenRouter, Local AI — Placeholder Only, Privacy and Scope

### Community 24 - "AI Digital Locker"
Cohesion: 0.67
Nodes (3): 1. Project Overview, 2. Main Goals, AI Digital Locker

### Community 25 - "21. Supabase"
Cohesion: 0.67
Nodes (3): 21. Supabase, PostgreSQL Database, Storage

### Community 26 - "3. User Accounts"
Cohesion: 0.67
Nodes (3): 3. User Accounts, Example, Registration and Login

### Community 27 - "5. Document Storage"
Cohesion: 0.67
Nodes (3): 5. Document Storage, Cloud Storage, Storage Limit

### Community 29 - "locker/views.py"
Cohesion: 0.06
Nodes (67): require_http_methods, require_POST, admin_documents(), admin_download(), admin_users(), ai_ask(), ai_status(), ai_suggest_filename() (+59 more)

### Community 30 - "main.py"
Cohesion: 0.25
Nodes (6): health(), lifespan(), get, FastAPI application entry point., Health endpoint tests — no real .env or credentials required., FastAPI

### Community 31 - "ApiClient"
Cohesion: 0.08
Nodes (32): BaseException, BaseTransport, ApiClient, ApiError, describe_api_error(), _error_detail(), Exception, Path (+24 more)

### Community 37 - "Session"
Cohesion: 0.16
Nodes (7): Session, AIDialog, Proposal only: confirm, then reuse the existing validated rename., Compact AI window. Local AI is a visibly disabled placeholder; suggestions are…, Constructing must not touch the network (refresh is deferred via after)., test_ai_dialog_constructs_with_local_placeholder(), test_main_view_constructs()

### Community 38 - "TaskRunner"
Cohesion: 0.06
Nodes (37): base_url(), _base_url_from_env_file(), Backend URL configuration for the desktop client. FASTAPI_BASE_URL is read from…, copy_path(), dir_for(), has_copy(), offline_root(), Path (+29 more)

### Community 39 - "SessionStore"
Cohesion: 0.22
Nodes (16): default_session_path(), Path, Returns None for missing, corrupt, or expired sessions., SessionStore, make_session(), Path, Session persistence tests: tmp paths only, no real %APPDATA% usage., test_atomic_save_leaves_no_temp_files() (+8 more)

### Community 40 - "MainView"
Cohesion: 0.13
Nodes (9): Button, _center_on_parent(), _label(), MainView, Misc, Spec section 11: optional local offline copy at upload time., Local validation mirrors the API rule (reject, never rewrite)., test_logout_revokes_remotely_and_always_clears_locally() (+1 more)

### Community 41 - "documents.py"
Cohesion: 0.16
Nodes (23): create_document(), Trusted per-user usage from database metadata (never client-supplied)., sum_usage_and_count(), download_document(), list_documents(), _not_found(), get, HTTPException (+15 more)

### Community 42 - "schemas.py"
Cohesion: 0.10
Nodes (37): create_session(), delete_session(), get_user_by_email(), update_password_hash(), _dummy_hash(), login(), logout(), get (+29 more)

### Community 43 - "db.py"
Cohesion: 0.13
Nodes (23): create_user(), delete_document(), DuplicateEmailError, get_document(), get_document_admin(), get_document_report_row(), get_user_by_id(), list_documents() (+15 more)

### Community 44 - "load_settings"
Cohesion: 0.14
Nodes (21): load_settings(), _placeholder_fields(), Application configuration for the AI Digital Locker backend. Reads backend/.env…, Load and validate settings. Errors name variables, never their values., Settings, _normalize_email(), main(), promote_admin() (+13 more)

### Community 46 - "ai.py"
Cohesion: 0.15
Nodes (27): chat(), ProviderError, Exception, OpenRouter chat client - Cloud AI (the only working AI option, spec 12).…, Provider unavailable/busy/malformed. Messages are always safe to show., One-shot completion. Returns the assistant text or raises ProviderError., _unavailable(), get_settings() (+19 more)

### Community 47 - "test_sheets.py"
Cohesion: 0.07
Nodes (36): client(), _document_row(), env(), FakeDocStore, FakeSheets, FakeStorage, _make_client_with_service(), make_user() (+28 more)

### Community 48 - "test_admin_bootstrap.py"
Cohesion: 0.16
Nodes (11): fake_db(), fixture, MonkeyPatch, Admin bootstrap script tests — all database access is faked., test_existing_admin_is_an_idempotent_noop(), test_failed_update_is_not_reported_as_success(), test_main_rejects_arguments_without_loading_settings(), test_main_reports_configuration_errors_safely() (+3 more)

### Community 49 - "deps.py"
Cohesion: 0.32
Nodes (7): get_session(), get_current_user(), HTTPException, Authentication dependency: validates the Bearer session token and resolves the…, Administrator gate. Admin status comes from the fresh per-request database row…, require_admin(), _unauthorized()

### Community 50 - "test_ui_smoke.py"
Cohesion: 0.18
Nodes (12): Persistent local login session for the desktop client. The FastAPI session…, format_size(), format_timestamp(), format_type(), Tkinter views: login and the documents workspace. Views own widgets and user-…, fixture, UI construction smoke tests - widgets only, no network, no mainloop., Regression: on_renamed must be a callable (was a Tk after-id string),… (+4 more)

### Community 51 - "admin.py"
Cohesion: 0.24
Nodes (13): list_users(), Admin listing only; selects non-secret columns in registration order., download_document(), list_documents(), list_users(), _not_found(), get, HTTPException (+5 more)

### Community 56 - "DemoDriver"
Cohesion: 0.13
Nodes (12): DemoDriver, Register a new demo account via the public API., Log in and obtain session token., List documents for the given account., Download a document owned by the given account., Rename a document owned by the given account., Delete a document owned by the given account., Sleep for a random duration. (+4 more)

### Community 57 - "main"
Cohesion: 0.12
Nodes (17): _is_localhost(), main(), Check if the URL points to a localhost address., Running without --run or --dry-run exits with code 2., Running with --dry-run exits 0 and makes no network calls., Running with a non-localhost URL without --allow-remote exits 2., Running with localhost URL passes validation., User count must be between 1 and 20. (+9 more)

### Community 58 - "AI Digital Locker — Architecture Map"
Cohesion: 0.20
Nodes (9): Admin, AI assistant, AI Digital Locker — Architecture Map, Authentication and authorization, Components and responsibilities, Data flows, Documents, Google Sheets reporting (+1 more)

### Community 59 - "AI Digital Locker — Project Context"
Cohesion: 0.20
Nodes (9): AI Digital Locker — Project Context, Confirmed decisions and constraints, Current architecture, Current verified baseline, Files future sessions must read first, Graphify reference, Phase status, Purpose and scope (+1 more)

### Community 60 - "AI Digital Locker — Project History"
Cohesion: 0.25
Nodes (7): AI Digital Locker — Project History, Authentication migration, Chronological implementation history, Explicitly deferred or open, Fixes and reviews, Original idea and requirements, Technology choices

### Community 61 - "AI Digital Locker — Session Handoff"
Cohesion: 0.25
Nodes (7): AI Digital Locker — Session Handoff, Current state, Decisions that must not be reversed, In-progress work and blockers, Read first, Recommended next step, Safe Git practices

### Community 62 - "AI Digital Locker — Graphify Reference"
Cohesion: 0.29
Nodes (6): AI Digital Locker — Graphify Reference, Artifacts, Limitations, Local generation baseline, Navigation commands, Safe refresh procedure

### Community 64 - "tests.py"
Cohesion: 0.14
Nodes (9): patch, TestCase, ErrorDetailTests, make_response(), MockedAPITestCase, Django web-client tests. All HTTP calls to FastAPI are mocked at…, Base: patches locker.fastapi_client.requests with a route table., FastAPI 422 returns detail as a list; the client must not crash. (+1 more)

### Community 65 - "theme.py"
Cohesion: 0.21
Nodes (12): apply_theme(), apply_window_icon(), asset(), display(), load_logo(), Path, Tk, Shared visual tokens and ttk styling for the desktop client. (+4 more)

### Community 67 - "DemoAccount"
Cohesion: 0.25
Nodes (6): DemoAccount, Represents a demo user account with its session token., DemoAccount stores email, password, user_id, and has empty token initially., auth_headers returns Bearer token when token is set., test_demo_account_auth_headers_with_token(), test_demo_account_properties()

### Community 69 - "_make_handler"
Cohesion: 0.67
Nodes (3): _make_handler(), Build an httpx.MockTransport handler from a route table. routes maps (method,…, MockTransport

### Community 72 - "StaticAssetTests"
Cohesion: 0.18
Nodes (6): Client, override_settings, CsrfTests, A real token extracted from the rendered page must pass the middleware., Static assets must be discoverable, served, and present after collectstatic., StaticAssetTests

### Community 73 - "Google Sheets reporting (Phase 11A)"
Cohesion: 0.40
Nodes (5): Google Sheets reporting (Phase 11A), Limitations, Setup, Synchronization behavior, What is reported

### Community 74 - "Django web client"
Cohesion: 0.50
Nodes (3): Django web client, Local development, Production

### Community 75 - "Demo runbook (Phase 10)"
Cohesion: 0.50
Nodes (4): Demo runbook (Phase 10), Demonstration checklist, Phase 10 verification (2026-10-27), Start the three components

### Community 76 - "ServerHud"
Cohesion: 0.06
Nodes (35): build_command(), build_launcher(), _cmd_quote(), default_data_dir(), default_settings(), main(), port_is_open(), Misc (+27 more)

### Community 77 - "SheetsClient"
Cohesion: 0.08
Nodes (27): Any, _display_file_type(), _display_ist(), _display_size(), _google_libraries_available(), _quote_sheet_title(), Google Sheets reporting layer (Phase 11A). Administrative document…, Quote a worksheet title for use in Google Sheets A1 notation. Sheet names… (+19 more)

## Knowledge Gaps
- **138 isolated node(s):** `$schema`, `.opencode/plugins/graphify.js`, `Usage`, `What graphify is for`, `Step 0 - GitHub repos and multi-path merge (only if a URL or several paths)` (+133 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 449 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **17 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `MockedAPITestCase` connect `tests.py` to `._seed_session`, `StaticAssetTests`, `AITests`, `AdminTests`, `AuthFlowTests`, `._api_doc_calls`?**
  _High betweenness centrality (0.244) - this node is a cross-community bridge._
- **Why does `ServerConfig` connect `ServerHud` to `tests.py`?**
  _High betweenness centrality (0.244) - this node is a cross-community bridge._
- **Why does `rename_document()` connect `documents.py` to `tests.py`, `db.py`?**
  _High betweenness centrality (0.130) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `FakeUserStore` (e.g. with `make_admin()` and `world()`) actually correct?**
  _`FakeUserStore` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `MainView` (e.g. with `ApiError` and `Session`) actually correct?**
  _`MainView` has 4 INFERRED edges - model-reasoned connections that need verification._
- **What connects `$schema`, `.opencode/plugins/graphify.js`, `Usage` to the rest of the system?**
  _138 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `AI_Digital_Locker_Project_Specification(2).md` be split into smaller, more focused modules?**
  _Cohesion score 0.08333333333333333 - nodes in this community are weakly interconnected._