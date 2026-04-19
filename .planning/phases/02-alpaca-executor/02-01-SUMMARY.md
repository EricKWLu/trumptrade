---
phase: 02-alpaca-executor
plan: "01"
subsystem: trading-executor
tags: [alpaca-py, bracket-orders, kill-switch, paper-mode, tdd]
dependency_graph:
  requires: [trumptrade.core.models.Order, trumptrade.core.models.AppSettings, trumptrade.core.db.AsyncSessionLocal, trumptrade.core.config.get_settings]
  provides: [AlpacaExecutor, BotDisabledError]
  affects: [trumptrade/trading/executor.py, pyproject.toml]
tech_stack:
  added: [pytz>=2024.1]
  patterns: [run_in_executor for sync alpaca-py calls, per-request client instantiation, string comparison for bot_enabled kill-switch]
key_files:
  created:
    - trumptrade/trading/executor.py
    - tests/trading/test_executor.py
    - tests/__init__.py
    - tests/trading/__init__.py
  modified:
    - pyproject.toml
decisions:
  - "bot_enabled stored as string 'true'/'false' — never Python bool; comparison is != 'true' not bool() cast"
  - "All alpaca-py calls wrapped in loop.run_in_executor() — alpaca-py has zero async methods"
  - "TradingClient/StockHistoricalDataClient instantiated per-request inside execute() — not cached (D-06)"
  - "BotDisabledError is plain Exception — router layer maps to HTTP 503, not executor"
  - "stop_price = round(last_price * (1 - stop_loss_pct / 100), 2) — 2dp Alpaca precision"
  - "OrderClass.BRACKET + StopLossRequest — stop-loss always atomic, never submitted separately (TRADE-03)"
metrics:
  duration: "~10 min"
  completed: "2026-04-19"
  tasks_completed: 2
  files_modified: 5
requirements_satisfied: [TRADE-01, TRADE-03]
---

# Phase 2 Plan 01: AlpacaExecutor Service Class Summary

**One-liner:** AlpacaExecutor service with bracket-order execution, kill-switch, and all alpaca-py sync calls wrapped in run_in_executor.

## What Was Built

Added `pytz>=2024.1` to `pyproject.toml` (required by `alpaca.data.historical` at import time) and implemented the `AlpacaExecutor` service class in `trumptrade/trading/executor.py`.

The executor implements:
1. Kill-switch check first: reads `bot_enabled` from DB and raises `BotDisabledError` (plain Exception, not HTTPException) if value is not the string `"true"`
2. Per-request mode re-read: `trading_mode` and `stop_loss_pct` fetched fresh from DB on every call (no caching — D-06)
3. Per-request Alpaca client instantiation: `TradingClient` and `StockHistoricalDataClient` constructed inside `execute()` based on live DB mode value
4. Price fetch via `run_in_executor`: `StockHistoricalDataClient.get_stock_latest_trade()` wrapped with `partial` to pass named args
5. Stop price calculation: `round(last_price * (1 - stop_loss_pct / 100), 2)` — 2dp precision for Alpaca
6. Atomic bracket order: `MarketOrderRequest(..., order_class=OrderClass.BRACKET, stop_loss=StopLossRequest(stop_price=...))` — never a separate stop-loss submission
7. Order submission via `run_in_executor`: `TradingClient.submit_order()` wrapped; error codes 403/422/429 mapped to appropriate HTTP status
8. DB audit: `str(alpaca_order.id)` UUID conversion before writing to `orders.alpaca_order_id`; status=`"submitted"`

## TDD Gate Compliance

Followed RED/GREEN/REFACTOR cycle:

- **RED:** `test(02-01): add failing tests for AlpacaExecutor behavior` (commit 40008a9) — 7 failing tests, confirmed `ModuleNotFoundError`
- **GREEN:** `feat(02-01): implement AlpacaExecutor service class` (commit b8f8ee0) — all 7 tests pass
- **REFACTOR:** No cleanup needed — implementation followed plan structure exactly

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add pytz to pyproject.toml | ce48514 | pyproject.toml |
| 2 (RED) | TDD: failing tests for AlpacaExecutor | 40008a9 | tests/trading/test_executor.py, tests/__init__.py, tests/trading/__init__.py |
| 2 (GREEN) | Implement AlpacaExecutor service class | b8f8ee0 | trumptrade/trading/executor.py |

## Verification Results

All plan verification checks passed:

- `python -c "from trumptrade.trading.executor import AlpacaExecutor, BotDisabledError; print('ok')"` → exits 0
- `python -c "from alpaca.data.historical import StockHistoricalDataClient; print('pytz ok')"` → exits 0
- `grep "pytz" pyproject.toml` → `"pytz>=2024.1",` found
- `grep "from __future__ import annotations" executor.py` → line 1 confirmed
- `grep 'bot_enabled_raw != "true"'` → found (string comparison, not bool cast)
- `grep "str(alpaca_order.id)"` → found (UUID → str before DB write)
- `grep "OrderClass.BRACKET"` → found (atomic bracket order enforced)
- `grep -c "run_in_executor"` → 4 matches (both alpaca-py calls wrapped, plus 2 await calls)
- All 7 pytest tests pass

## Threat Model Coverage

All 5 mitigations from the plan's threat register implemented:

| Threat ID | Mitigation | Implementation |
|-----------|------------|----------------|
| T-02-01 | `bot_enabled` string comparison | `bot_enabled_raw != "true"` — explicit string, not `bool()` |
| T-02-02 | No credentials in logs | `logger.info/error` logs only order IDs, symbols, modes |
| T-02-03 | UUID type mismatch | `str(alpaca_order.id)` before `Order(alpaca_order_id=...)` |
| T-02-04 | Event loop blocking | All alpaca-py calls in `loop.run_in_executor(None, ...)` |
| T-02-05 | Stop price precision | `round(stop_price, 2)` applied (accepted) |

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None — executor.py is fully implemented with all methods wired to real DB and Alpaca API (paper mode by default).

## Threat Flags

No new security surface introduced beyond what was planned — executor.py accesses Alpaca API (planned boundary) and reads AppSettings/writes Orders via existing DB schema (no schema changes).
