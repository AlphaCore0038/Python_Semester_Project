"""FastAPI application entry point (Phase 3: foundation only)."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import load_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail fast at startup with a clear, secret-safe message.
    load_settings()
    yield


app = FastAPI(title="AI Digital Locker API", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
