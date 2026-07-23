"""FastAPI application entrypoint.

This server is meant to run as a local sidecar process spawned by the Tauri
shell, bound to 127.0.0.1 only -- it is never exposed to the network. CORS
is scoped to the Tauri webview origin.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import settings
from app.logging_config import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    settings.ensure_directories()
    logger.info("Backend ready on %s:%s", settings.host, settings.port)
    yield
    logger.info("Backend shutting down")


app = FastAPI(
    title="Anki YouTube Generator",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["tauri://localhost", "http://localhost:1420", "http://127.0.0.1:1420"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
