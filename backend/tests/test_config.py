# backend/tests/test_config.py: Tests for tests.
"""Configuration tests — use fake env values; never read the real backend/.env."""

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app

VALID_ENV = {
    "SUPABASE_URL": "https://example-project.supabase.co",
    "SUPABASE_SERVICE_ROLE_KEY": "test-service-role-key",
}


def _clear_cached_settings() -> None:
    config.get_settings.cache_clear()


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path):
                                                                         
                                                                     
                                                   
    monkeypatch.setattr(config, "ENV_FILE", tmp_path / ".env")
    for name in (
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "ADMIN_EMAIL",
        "OPENROUTER_API_KEY",
        "SESSION_EXPIRY_MINUTES",
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
    assert settings.session_expiry_minutes == 1440
    assert settings.storage_quota_bytes == 524_288_000                    
    assert settings.max_upload_bytes == 52_428_800                             


def test_session_expiry_can_be_overridden(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in VALID_ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("SESSION_EXPIRY_MINUTES", "60")
    assert config.load_settings().session_expiry_minutes == 60


def test_missing_required_settings_raise_clear_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(RuntimeError) as excinfo:
        config.load_settings()
    message = str(excinfo.value)
    assert "SUPABASE_URL" in message
    assert "SUPABASE_SERVICE_ROLE_KEY" in message
                                                                           
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
