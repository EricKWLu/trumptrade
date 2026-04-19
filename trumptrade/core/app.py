"""FastAPI application factory — full implementation in 01-PLAN-05."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — APScheduler start/stop wired here in Plan 05."""
    # Scheduler startup added in 01-PLAN-05
    yield
    # Scheduler shutdown added in 01-PLAN-05


def create_app() -> FastAPI:
    """Create and return the configured FastAPI application."""
    app = FastAPI(
        title="TrumpTrade",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    return app
