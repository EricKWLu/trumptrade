"""FastAPI application factory for TrumpTrade.

The scheduler instance is module-level so Phase 3 ingestion jobs can import
and register jobs via:
    from trumptrade.core.app import scheduler
    scheduler.add_job(...)
"""
from __future__ import annotations

import asyncio
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

    # Phase 5: start risk consumer (D-03 — asyncio.create_task, not APScheduler job)
    # Local import avoids circular import (established codebase pattern from Phase 3/4).
    # Task MUST be created AFTER scheduler.start() to maintain startup order.
    from trumptrade.risk_guard.guard import risk_consumer  # local import
    _consumer_task = asyncio.create_task(risk_consumer(), name="risk_consumer")
    logger.info("Risk consumer task started")

    yield  # Application runs here

    # SHUTDOWN
    # Cancel consumer task and await it — prevents "Task destroyed but pending!" warning.
    # CancelledError is swallowed here (in the lifespan context) — NOT in the consumer itself.
    _consumer_task.cancel()
    try:
        await _consumer_task
    except asyncio.CancelledError:
        pass
    logger.info("Risk consumer task stopped")

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

    # ── Phase 6: CORS for Vite dev server ───────────────────────────────────
    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Phase 2: trading router ──────────────────────────────────────────────
    from trumptrade.trading import trading_router          # local import avoids circular import
    app.include_router(trading_router, prefix="/trading", tags=["trading"])

    # ── Phase 5: risk settings router ───────────────────────────────────────
    from trumptrade.risk_guard import settings_router      # local import avoids circular import
    app.include_router(settings_router, prefix="/settings", tags=["settings"])

    # ── Phase 6: dashboard + WebSocket routers ───────────────────────────────
    from trumptrade.dashboard import watchlist_router, ws_router        # local import
    from trumptrade.dashboard.router import router as dashboard_router  # local import
    app.include_router(dashboard_router, tags=["dashboard"])
    app.include_router(watchlist_router, tags=["watchlist"])
    app.include_router(ws_router, tags=["websocket"])

    # ── Phase 3: ingestion jobs ──────────────────────────────────────────────
    from trumptrade.ingestion import register_ingestion_jobs  # local import avoids circular import
    register_ingestion_jobs(scheduler)

    # ── Phase 4: analysis jobs ───────────────────────────────────────────────
    from trumptrade.analysis import register_analysis_jobs  # local import avoids circular import
    register_analysis_jobs(scheduler)

    @app.get("/health")
    async def health() -> dict:
        """Health check — confirms server is up and scheduler is running."""
        return {
            "status": "ok",
            "scheduler_running": scheduler.running,
        }

    return app
