"""FastAPI application entry point (Phase 3: foundation only)."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import load_settings
from app.routers.auth import router as auth_router
from app.routers.documents import router as documents_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail fast at startup with a clear, secret-safe message.
    load_settings()
    yield


app = FastAPI(title="AI Digital Locker API", lifespan=lifespan)
app.include_router(auth_router, prefix="/auth")
app.include_router(documents_router, prefix="/documents")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
