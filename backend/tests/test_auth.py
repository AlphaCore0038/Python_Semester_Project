"""Authentication tests — in-memory fake user/session store; no real Supabase."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import config, db
from app.main import app
from app.security import hash_password, hash_session_token

VALID_ENV = {
    "SUPABASE_URL": "https://example-project.supabase.co",
    "SUPABASE_SERVICE_ROLE_KEY": "test-service-role-key",
}

CREATED_AT = "2026-10-20T00:00:00+00:00"


class FakeUserStore:
    def __init__(self) -> None:
        self.users: dict[str, dict] = {}
        self.sessions: dict[str, dict] = {}

    def create_user(self, email: str, password_hash: str) -> dict:
        if email in self.users:
            raise db.DuplicateEmailError()
        user = {
            "id": str(uuid.uuid4()),
            "email": email,
            "password_hash": password_hash,
            "is_admin": False,
            "created_at": CREATED_AT,
        }
        self.users[email] = user
        return user

    def get_user_by_email(self, email: str) -> dict | None:
        return self.users.get(email)

    def get_user_by_id(self, user_id: str) -> dict | None:
        for user in self.users.values():
            if user["id"] == user_id:
                return user
        return None

    def create_session(self, token_hash: str, user_id: str, expires_at: str) -> dict:
        row = {
            "token_hash": token_hash,
            "user_id": user_id,
            "expires_at": expires_at,
        }
        self.sessions[token_hash] = row
        return row

    def get_session(self, token_hash: str) -> dict | None:
        return self.sessions.get(token_hash)

    def delete_session(self, token_hash: str) -> bool:
        return self.sessions.pop(token_hash, None) is not None


@pytest.fixture()
def store(monkeypatch: pytest.MonkeyPatch) -> FakeUserStore:
    for name in (
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "ADMIN_EMAIL",
        "OPENROUTER_API_KEY",
        "SESSION_EXPIRY_MINUTES",
    ):
        monkeypatch.delenv(name, raising=False)
    for name, value in VALID_ENV.items():
        monkeypatch.setenv(name, value)
    config.get_settings.cache_clear()

    fake = FakeUserStore()
    for name, target in (
        ("create_user", fake.create_user),
        ("get_user_by_email", fake.get_user_by_email),
        ("get_user_by_id", fake.get_user_by_id),
        ("create_session", fake.create_session),
        ("get_session", fake.get_session),
        ("delete_session", fake.delete_session),
    ):
        monkeypatch.setattr(db, name, target)
    yield fake
    config.get_settings.cache_clear()


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def register(client: TestClient, email: str, password: str, **extra) -> dict:
    return client.post("/auth/register", json={"email": email, "password": password, **extra})


def login(client: TestClient, email: str, password: str) -> dict:
    return client.post("/auth/login", json={"email": email, "password": password})


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def make_token(user: dict, ttl_seconds: int = 3600) -> str:
    """Insert a fake session row directly; mirrors what login does."""
    token = f"test-session-{uuid.uuid4()}"
    expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
    ).isoformat()
    db.create_session(hash_session_token(token), user["id"], expires_at)
    return token


# --- registration ---

def test_register_success(client: TestClient, store: FakeUserStore) -> None:
    response = register(client, "Alice@Example.com", "correct-horse-1")
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "email"}
    assert body["email"] == "alice@example.com"  # normalized to lowercase
    assert "password_hash" not in response.text


def test_register_normalizes_email_and_detects_duplicate_casing(
    client: TestClient, store: FakeUserStore
) -> None:
    assert register(client, "alice@example.com", "correct-horse-1").status_code == 201
    duplicate = register(client, "ALICE@EXAMPLE.COM", "another-pass-2")
    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": "Email already registered"}
    assert len(store.users) == 1


def test_register_rejects_short_password(client: TestClient, store: FakeUserStore) -> None:
    response = register(client, "bob@example.com", "short7!")
    assert response.status_code == 422
    assert "at least 8 characters" in response.text


def test_register_rejects_password_over_72_utf8_bytes(
    client: TestClient, store: FakeUserStore
) -> None:
    response = register(client, "bob@example.com", "a" * 73)
    assert response.status_code == 422
    assert "72 bytes" in response.text


def test_register_rejects_unicode_password_over_72_bytes(
    client: TestClient, store: FakeUserStore
) -> None:
    # 40 * 2-byte chars = 80 UTF-8 bytes, but only 40 code points
    response = register(client, "bob@example.com", "é" * 40)
    assert response.status_code == 422
    assert "72 bytes" in response.text


def test_register_accepts_unicode_password_within_72_bytes(
    client: TestClient, store: FakeUserStore
) -> None:
    response = register(client, "uni@example.com", "pässwörd✓-1")
    assert response.status_code == 201
    # verify the stored hash validates the exact unicode password
    user = store.get_user_by_email("uni@example.com")
    from app.security import verify_password

    assert verify_password("pässwörd✓-1", user["password_hash"])


def test_register_ignores_is_admin_input(client: TestClient, store: FakeUserStore) -> None:
    response = register(client, "eve@example.com", "correct-horse-1", is_admin=True)
    assert response.status_code == 201
    assert "is_admin" not in response.json()
    assert store.get_user_by_email("eve@example.com")["is_admin"] is False


def test_register_rejects_invalid_email(client: TestClient, store: FakeUserStore) -> None:
    assert register(client, "not-an-email", "correct-horse-1").status_code == 422


# --- login ---

def test_login_success_returns_opaque_bearer_token(
    client: TestClient, store: FakeUserStore
) -> None:
    register(client, "alice@example.com", "correct-horse-1")
    response = login(client, "ALICE@example.com", "correct-horse-1")  # casing tolerated
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 86400
    token = body["access_token"]
    assert token
    assert "." not in token  # opaque, not a structured/signed token
    assert "password" not in response.text
    # Only the hash is stored, never the raw token.
    assert token not in store.sessions
    assert hash_session_token(token) in store.sessions


def test_login_creates_independent_sessions(
    client: TestClient, store: FakeUserStore
) -> None:
    register(client, "alice@example.com", "correct-horse-1")
    first = login(client, "alice@example.com", "correct-horse-1").json()["access_token"]
    second = login(client, "alice@example.com", "correct-horse-1").json()["access_token"]
    assert first != second
    assert len(store.sessions) == 2


def test_login_wrong_password_and_unknown_email_share_error(
    client: TestClient, store: FakeUserStore
) -> None:
    register(client, "alice@example.com", "correct-horse-1")
    wrong = login(client, "alice@example.com", "wrong-password-9")
    unknown = login(client, "ghost@example.com", "wrong-password-9")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json() == {"detail": "Incorrect email or password"}


# --- protected endpoint ---

def test_me_with_valid_token(client: TestClient, store: FakeUserStore) -> None:
    registered = register(client, "alice@example.com", "correct-horse-1").json()
    token = login(client, "alice@example.com", "correct-horse-1").json()["access_token"]
    response = client.get("/auth/me", headers=auth_header(token))
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == registered["id"]
    assert body["email"] == "alice@example.com"
    assert body["is_admin"] is False
    assert body["created_at"] == CREATED_AT
    assert "password_hash" not in response.text


def test_me_without_token_is_401_with_challenge(client: TestClient) -> None:
    response = client.get("/auth/me")
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize("token", ["garbage", "a.b.c", ""])
def test_me_with_invalid_token_is_401(
    client: TestClient, store: FakeUserStore, token: str
) -> None:
    response = client.get("/auth/me", headers=auth_header(token))
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_me_with_expired_token_is_401(client: TestClient, store: FakeUserStore) -> None:
    user = store.create_user("old@example.com", hash_password("correct-horse-1"))
    expired = make_token(user, ttl_seconds=-1)
    response = client.get("/auth/me", headers=auth_header(expired))
    assert response.status_code == 401
    assert response.json() == {"detail": "Token expired"}


def test_me_with_token_of_deleted_user_is_401(
    client: TestClient, store: FakeUserStore
) -> None:
    user = store.create_user("gone@example.com", hash_password("correct-horse-1"))
    token = make_token(user)
    store.users.clear()  # user deleted after session issued
    response = client.get("/auth/me", headers=auth_header(token))
    assert response.status_code == 401


def test_legacy_signed_tokens_are_rejected(
    client: TestClient, store: FakeUserStore
) -> None:
    # A previously issued signed token is just an unknown opaque token now.
    legacy_token = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiJ4IiwiZW1haWwiOiJ4QHkuY29tIn0."
        "signature"
    )
    response = client.get("/auth/me", headers=auth_header(legacy_token))
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


# --- logout ---

def test_logout_revokes_current_session(
    client: TestClient, store: FakeUserStore
) -> None:
    register(client, "alice@example.com", "correct-horse-1")
    token = login(client, "alice@example.com", "correct-horse-1").json()["access_token"]

    response = client.post("/auth/logout", headers=auth_header(token))
    assert response.status_code == 204
    assert client.get("/auth/me", headers=auth_header(token)).status_code == 401
    # Idempotent: logging out again is still a no-op success.
    assert client.post("/auth/logout", headers=auth_header(token)).status_code == 204


def test_logout_only_revokes_current_session(
    client: TestClient, store: FakeUserStore
) -> None:
    register(client, "alice@example.com", "correct-horse-1")
    first = login(client, "alice@example.com", "correct-horse-1").json()["access_token"]
    second = login(client, "alice@example.com", "correct-horse-1").json()["access_token"]

    assert client.post("/auth/logout", headers=auth_header(first)).status_code == 204
    assert client.get("/auth/me", headers=auth_header(first)).status_code == 401
    assert client.get("/auth/me", headers=auth_header(second)).status_code == 200


def test_logout_requires_auth(client: TestClient) -> None:
    assert client.post("/auth/logout").status_code == 401


def test_health_still_works(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}
