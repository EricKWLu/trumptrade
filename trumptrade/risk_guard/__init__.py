"""Risk guard package — asyncio.Queue chokepoint between analysis and execution (Phase 5).

Exports:
  signal_queue  — asyncio.Queue(maxsize=100); producer: analysis_worker; consumer: risk_consumer
  QueueItem     — dataclass for queue items
  settings_router — FastAPI router for GET/PATCH /settings/risk (wired in Phase 5 plan 03)
"""
from __future__ import annotations

import asyncio

from trumptrade.risk_guard.guard import QueueItem  # noqa: F401

# Module-level queue — safe in Python 3.11+ (no loop binding at creation time per PEP 3156 removal)
# D-02: maxsize=100 (blocks producer if backlogged; handles bursts)
signal_queue: asyncio.Queue = asyncio.Queue(maxsize=100)

# settings_router imported lazily to avoid circular import at module load time.
# Imported by app.py create_app() via local import: from trumptrade.risk_guard import settings_router
# Import is deferred until router.py exists (Phase 5 plan 03).
# For now, expose a placeholder that will be overwritten when router.py is created.
try:
    from trumptrade.risk_guard.router import router as settings_router  # noqa: F401
except ImportError:
    settings_router = None  # type: ignore[assignment]  # router.py created in plan 03

__all__ = ["signal_queue", "QueueItem", "settings_router"]
