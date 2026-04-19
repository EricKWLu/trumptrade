"""FastAPI application factory for TrumpTrade.

The scheduler instance is module-level so Phase 3 ingestion jobs can import
and register jobs via:
    from trumptrade.core.app import scheduler
    scheduler.add_job(...)
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from trumptrade.core.config import get_settings

logger = logging.getLogger(__name__)

# Module-level scheduler — Phase 3 adds jobs by importing this instance.
# Using AsyncIOScheduler: attaches to uvicorn's event loop when started
# inside the lifespan context manager.
scheduler = AsyncIOScheduler(timezone="UTC")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle: start scheduler on startup, stop on shutdown.

    Uses the lifespan context manager (NOT the deprecated @app.on_event).
    FastAPI requires this for proper startup/shutdown in production.
    """
    settings = get_settings()
    logger.info(
        "TrumpTrade starting",
        extra={
            "db_url": settings.db_url,
            "debug": settings.debug,
        },
    )

    # STARTUP
    scheduler.start()
    logger.info("APScheduler started — ready to receive jobs")

    yield  # Application runs here

    # SHUTDOWN
    # wait=False: do not block waiting for running jobs; abandon them cleanly.
    # Prevents hang in async context when jobs are mid-execution.
    scheduler.shutdown(wait=False)
    logger.info("APScheduler stopped")


def create_app() -> FastAPI:
    """Create and return the configured FastAPI application.

    Called by __main__.py. The returned app object is passed directly to
    uvicorn.run() — do NOT use a string import path alongside this factory,
    as the scheduler module-level instance would differ between import paths.
    """
    app = FastAPI(
        title="TrumpTrade",
        version="0.1.0",
        description="Automated Trump social media trading bot",
        lifespan=lifespan,
    )

    # ── Phase 2: trading router ──────────────────────────────────────────────
    from trumptrade.trading import trading_router          # local import avoids circular import
    app.include_router(trading_router, prefix="/trading", tags=["trading"])

    @app.get("/health")
    async def health() -> dict:
        """Health check — confirms server is up and scheduler is running."""
        return {
            "status": "ok",
            "scheduler_running": scheduler.running,
        }

    return app
