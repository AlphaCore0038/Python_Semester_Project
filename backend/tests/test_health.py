# backend/tests/test_health.py: Tests for tests.
"""Health endpoint tests — no real .env or credentials required."""

from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok() -> None:
                                                                         
                                                          
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
