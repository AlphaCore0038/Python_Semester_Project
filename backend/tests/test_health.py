"""Health endpoint tests — no real .env or credentials required."""

from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok() -> None:
    # TestClient without a context manager does not run lifespan, so this
    # exercises the route without requiring configuration.
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
