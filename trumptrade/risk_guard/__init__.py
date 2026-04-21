"""Risk guard package — asyncio.Queue chokepoint between analysis and execution (Phase 5).

Exports:
  signal_queue    — asyncio.Queue(maxsize=100); producer: analysis_worker; consumer: risk_consumer
  QueueItem       — dataclass for queue items
  settings_router — FastAPI router for GET/PATCH /settings/risk (registered in app.py)
"""
from __future__ import annotations

import asyncio

from trumptrade.risk_guard.guard import QueueItem  # noqa: F401
from trumptrade.risk_guard.router import router as settings_router  # noqa: F401

# Module-level queue — safe in Python 3.11+ (no loop binding at creation time).
# D-02: maxsize=100 (blocks producer if backlogged; handles signal bursts).
signal_queue: asyncio.Queue = asyncio.Queue(maxsize=100)

__all__ = ["signal_queue", "QueueItem", "settings_router"]
