---
phase: 06-web-dashboard
plan: 01
subsystem: dashboard-backend
tags: [websocket, watchlist, cors, fastapi, broadcast]
dependency_graph:
  requires:
    - trumptrade/core/models.py (Watchlist model)
    - trumptrade/core/db.py (AsyncSessionLocal)
    - trumptrade/analysis/worker.py (Signal commit point)
    - trumptrade/ingestion/heartbeat.py (silence detection)
    - trumptrade/risk_guard/guard.py (Alpaca error handlers)
    - trumptrade/trading/router.py (bot status endpoint)
  provides:
    - trumptrade/dashboard/ws.py (ConnectionManager singleton + /ws/feed)
    - trumptrade/dashboard/watchlist.py (GET/POST/DELETE /watchlist)
    - trumptrade/dashboard/__init__.py (watchlist_router, ws_router exports)
    - CORS middleware on all FastAPI routes (http://localhost:5173)
    - WebSocket broadcast after every Signal commit
    - append_alert() call sites in heartbeat.py and guard.py
    - GET /trading/status endpoint
  affects:
    - trumptrade/core/app.py (CORS + router registrations)
    - trumptrade/dashboard/router.py (append_alert consumer — created by Plan 06-02)
tech_stack:
  added: []
  patterns:
    - ConnectionManager singleton with dead-connection cleanup in broadcast()
    - Local import inside loop body (analysis/worker.py) to avoid circular dependency
    - Module-level singleton manager imported by reference from other modules
    - Lazy local imports for dashboard.router in heartbeat/guard (router.py created by Plan 06-02)
key_files:
  created:
    - trumptrade/dashboard/ws.py
    - trumptrade/dashboard/watchlist.py
  modified:
    - trumptrade/dashboard/__init__.py
    - trumptrade/core/app.py
    - trumptrade/analysis/worker.py
    - trumptrade/ingestion/heartbeat.py
    - trumptrade/risk_guard/guard.py
    - trumptrade/trading/router.py
decisions:
  - "dashboard_router imported from trumptrade.dashboard.router directly in app.py (not via __init__) to avoid circular import with Plan 06-02 parallel execution"
  - "ws.py enforces one-way dependency: zero imports from analysis/, risk_guard/, or trading/"
  - "broadcast() silently removes dead WebSocket connections after loop to prevent one client blocking others (T-06-01-04)"
  - "WatchlistAdd uses Field(pattern='^[A-Z]{1,5}$') for SQL-injection-safe symbol validation (T-06-01-01)"
  - "append_alert() calls in heartbeat.py and guard.py use lazy local imports since dashboard/router.py is created by Plan 06-02"
metrics:
  duration: "~12 minutes"
  completed: "2026-04-21"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 6
---

# Phase 06 Plan 01: Dashboard Backend Package Summary

**One-liner:** WebSocket ConnectionManager singleton, watchlist CRUD endpoints, CORS for Vite dev server, and analysis worker broadcast wired via local imports to avoid circular dependencies.

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 | Create trumptrade/dashboard/ package (ws.py, watchlist.py, __init__.py) | 8708c32 | dashboard/ws.py, dashboard/watchlist.py, dashboard/__init__.py |
| 2 | Patch app.py (CORS+routers), worker.py (broadcast), heartbeat.py (alert), guard.py (alert), trading/router.py (status) | a6a402b | core/app.py, analysis/worker.py, ingestion/heartbeat.py, risk_guard/guard.py, trading/router.py |

## What Was Built

### trumptrade/dashboard/ws.py
- `ConnectionManager` class with `connect()`, `disconnect()`, `broadcast()` methods
- `broadcast()` uses try/except per-client to silently collect and remove dead connections after the loop (T-06-01-04 mitigation)
- Module-level `manager = ConnectionManager()` singleton — imported by reference from analysis/worker.py
- `/ws/feed` WebSocket endpoint: accept → receive loop → disconnect on `WebSocketDisconnect`
- Zero imports from analysis/, risk_guard/, or trading/ (one-way dependency enforced)

### trumptrade/dashboard/watchlist.py
- `WatchlistAdd(BaseModel)` with `symbol: str = Field(pattern=r"^[A-Z]{1,5}$")` — rejects injection, >5 chars, lowercase (T-06-01-01)
- `GET /watchlist` — returns all symbols ordered alphabetically with added_at
- `POST /watchlist` — inserts symbol, returns 409 on IntegrityError (duplicate), 201 on success
- `DELETE /watchlist/{symbol}` — normalizes to uppercase, returns 404 if not found, 200 on removal

### trumptrade/dashboard/__init__.py
- Exports `watchlist_router` and `ws_router`
- Does NOT import `dashboard_router` from router.py — that file is created by Plan 06-02 in the same wave

### trumptrade/core/app.py
- Added `CORSMiddleware` with `allow_origins=["http://localhost:5173"]` immediately after `FastAPI(...)` creation (must precede all `include_router` calls)
- Registered `dashboard_router` (from `trumptrade.dashboard.router`), `watchlist_router`, `ws_router` as local imports after Phase 5 router block

### trumptrade/analysis/worker.py
- Added broadcast block after `await session.commit()` and before risk_guard enqueue block
- Broadcasts `{"type": "post", "id", "platform", "content", "posted_at", "is_filtered", "filter_reason", "signal": {...}}` JSON
- Uses `from trumptrade.dashboard.ws import manager as _ws_manager` local import inside loop body (avoids circular import)

### trumptrade/ingestion/heartbeat.py
- Added `append_alert("heartbeat", ...)` call after silence warning log
- Uses lazy local import from `trumptrade.dashboard.router` (router.py created by Plan 06-02)

### trumptrade/risk_guard/guard.py
- Added `append_alert("alpaca", ...)` in `_check_daily_cap` APIError except block
- Added `append_alert("alpaca", ...)` in `_get_equity` APIError except block
- Both use lazy local import from `trumptrade.dashboard.router`

### trumptrade/trading/router.py
- Added `GET /trading/status` endpoint reading `bot_enabled` from AppSettings
- Returns `{"bot_enabled": bool}` — same source as executor's kill-switch check

## Deviations from Plan

None — plan executed exactly as written.

Note: The `trumptrade/dashboard/router.py` (which provides `append_alert`) is expected to be created by Plan 06-02 running in parallel in Wave 1. The imports in heartbeat.py and guard.py are lazy (inside function bodies) so they don't fail at module import time — they will only resolve at runtime after Plan 06-02 completes.

## Known Stubs

None — all wiring points to real implementations. The `append_alert` function in heartbeat.py and guard.py uses lazy imports that require Plan 06-02's router.py to exist at runtime. This is by design per the wave-parallel execution model.

## Threat Flags

No new threat surface beyond what is documented in the plan's threat model (T-06-01-01 through T-06-01-06).

## Self-Check: PASSED

- `trumptrade/dashboard/ws.py`: FOUND
- `trumptrade/dashboard/watchlist.py`: FOUND
- `trumptrade/dashboard/__init__.py`: FOUND (modified)
- Commit 8708c32: FOUND
- Commit a6a402b: FOUND
- All verification checks: PASSED
