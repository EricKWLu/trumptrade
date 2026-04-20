---
phase: 02-alpaca-executor
plan: "02"
subsystem: trading-router
tags: [fastapi, router, pydantic, kill-switch, bracket-orders]
dependency_graph:
  requires: [AlpacaExecutor, BotDisabledError, trumptrade.core.app.create_app]
  provides: [trading_router, /trading/execute, /trading/kill-switch]
  affects: [trumptrade/trading/router.py, trumptrade/trading/__init__.py, trumptrade/core/app.py]
tech_stack:
  added: []
  patterns: [local import inside create_app() to avoid circular import, Pydantic Field(gt=0) for qty validation, BotDisabledError -> HTTP 503 mapping]
key_files:
  created:
    - trumptrade/trading/router.py
  modified:
    - trumptrade/trading/__init__.py
    - trumptrade/core/app.py
decisions:
  - "Local import of trading_router inside create_app() body — not top-level — avoids circular import (executor.py imports from trumptrade.core.*)"
  - "qty: float = Field(gt=0) rejects zero/negative at Pydantic layer before executor is called (T-02-06)"
  - "BotDisabledError (plain Exception from executor) mapped to HTTPException(503) in router layer"
  - "Module-level _executor = AlpacaExecutor() keeps HTTP handlers thin"
metrics:
  duration: "~5 min"
  completed: "2026-04-19"
  tasks_completed: 2
  files_modified: 3
requirements_satisfied: [TRADE-01, TRADE-03]
status: complete
---

# Phase 2 Plan 02: Trading Router + App Registration Summary

**One-liner:** FastAPI trading router with /execute and /kill-switch endpoints wired into create_app() via local import to avoid circular imports.

## What Was Built

Created `trumptrade/trading/router.py` with the HTTP layer for the AlpacaExecutor service:

1. **Pydantic request/response models** (v2 style, no inner `class Config:`):
   - `ExecuteSignalRequest`: symbol, side, qty with `Field(gt=0)` validation (T-02-06 mitigation)
   - `ExecuteSignalResponse`: order_id, status
   - `KillSwitchRequest`: enabled bool
   - `KillSwitchResponse`: bot_enabled bool, ok bool

2. **Route handlers**:
   - `POST /execute`: calls `_executor.execute()`, maps `BotDisabledError` to 503 `{"error": "bot_disabled"}`
   - `POST /kill-switch`: calls `_executor.set_bot_enabled()`, logs toggle, returns structured response

3. **`trumptrade/trading/__init__.py`**: replaced stub comment with `from trumptrade.trading.router import router as trading_router` export.

4. **`trumptrade/core/app.py`**: added router registration inside `create_app()` body using local import pattern — `include_router(trading_router, prefix="/trading", tags=["trading"])`.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create trading router and __init__ export | 8e3a303 | trumptrade/trading/router.py, trumptrade/trading/__init__.py |
| 2 | Register trading router in create_app() | 016cc3e | trumptrade/core/app.py |
| 3 | checkpoint:human-verify | pending | — |

## Verification Results (pre-checkpoint)

All structural and functional automated checks passed:

- `python -c "from trumptrade.trading import trading_router; print('router import ok')"` → exits 0
- `python -c "from trumptrade.core.app import create_app; app = create_app(); routes = [r.path for r in app.routes]; assert '/trading/execute' in routes and '/trading/kill-switch' in routes and '/health' in routes"` → exits 0 — routes: `['/openapi.json', '/docs', '/docs/oauth2-redirect', '/redoc', '/trading/execute', '/trading/kill-switch', '/health']`
- `grep "include_router(trading_router"` → found in create_app() body
- `grep "from trumptrade.trading import trading_router"` → found inside function body (not top-level)
- `grep "Field(gt=0)"` → found on qty field
- `grep "status_code=503"` → found in BotDisabledError handler
- `grep "BotDisabledError"` → found in import and except clause

## Threat Model Coverage

| Threat ID | Mitigation | Implementation |
|-----------|------------|----------------|
| T-02-06 | qty Field(gt=0) | `qty: float = Field(gt=0)` — Pydantic rejects 0 and negative before executor is called; returns 422 |
| T-02-07 | Symbol injection | Passed to Alpaca API; Alpaca 422 caught by executor's APIError handler and mapped to 400 |
| T-02-08 | Side enum mapping | Executor maps to OrderSide enum; arbitrary strings default to SELL (accepted) |
| T-02-09 | Kill-switch race | SQLite serializes writes; each /execute re-reads bot_enabled from DB (accepted) |
| T-02-10 | Kill-switch unprotected | Single-user tool; no multi-user auth in scope (accepted) |

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None — router.py fully wired to AlpacaExecutor service with real DB and Alpaca API.

## Threat Flags

No new security surface beyond what was planned — /trading/execute and /trading/kill-switch endpoints were the planned trust boundaries (T-02-06 through T-02-10 in plan's threat register).

## Self-Check

**Created files:**
- trumptrade/trading/router.py: FOUND
- trumptrade/trading/__init__.py: FOUND (modified)
- trumptrade/core/app.py: FOUND (modified)

**Commits:**
- 8e3a303: FOUND (feat(02-02): create trading router and __init__ export)
- 016cc3e: FOUND (feat(02-02): register trading router in create_app())

## Self-Check: PASSED
