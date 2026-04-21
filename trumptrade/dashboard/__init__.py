"""Dashboard package — WebSocket feed and watchlist CRUD (Phase 6).

dashboard_router (from router.py) is imported directly by app.py to avoid
a circular dependency: __init__.py must not import router.py until after
Plan 06-02 creates it (Wave 1 parallel execution).
"""
from __future__ import annotations

from trumptrade.dashboard.watchlist import router as watchlist_router
from trumptrade.dashboard.ws import router as ws_router

__all__ = ["watchlist_router", "ws_router"]
