"""Configuration tests — use fake env values; never read the real backend/.env."""

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app

VALID_ENV = {
    "SUPABASE_URL": "https://example-project.supabase.co",
    "SUPABASE_SERVICE_ROLE_KEY": "test-service-role-key",
    "JWT_SECRET": "test-jwt-secret",
}


def _clear_cached_settings() -> None:
    config.get_settings.cache_clear()


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path):
    # Ensure the real .env is never read during tests: point the module's
    # ENV_FILE at a nonexistent path so load_settings() falls back to
    # process env only (OS vars are cleared below).
    monkeypatch.setattr(config, "ENV_FILE", tmp_path / ".env")
    for name in (
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "JWT_SECRET",
        "ADMIN_EMAIL",
        "OPENROUTER_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    _clear_cached_settings()
    yield
    _clear_cached_settings()


def test_load_settings_with_valid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in VALID_ENV.items():
        monkeypatch.setenv(name, value)
    settings = config.load_settings()
    assert settings.supabase_url == VALID_ENV["SUPABASE_URL"]
    assert settings.storage_quota_bytes == 524_288_000  # 500 MB unchanged
    assert settings.max_upload_bytes == 52_428_800  # 50 MB Supabase Free limit


def test_missing_required_settings_raise_clear_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(RuntimeError) as excinfo:
        config.load_settings()
    message = str(excinfo.value)
    assert "SUPABASE_URL" in message
    assert "JWT_SECRET" in message
    # Secret-safe: no value-looking content from the environment is echoed.
    assert "test-service-role-key" not in message


def test_placeholder_values_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in VALID_ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv(
        "SUPABASE_SERVICE_ROLE_KEY", "your-service-role-key"
    )
    with pytest.raises(RuntimeError) as excinfo:
        config.load_settings()
    message = str(excinfo.value)
    assert "SUPABASE_SERVICE_ROLE_KEY" in message
    assert "placeholder" in message.lower()


def test_health_startup_with_valid_config(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in VALID_ENV.items():
        monkeypatch.setenv(name, value)
    _clear_cached_settings()
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
