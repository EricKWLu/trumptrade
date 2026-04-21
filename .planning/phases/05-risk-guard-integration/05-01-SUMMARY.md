---
phase: 05-risk-guard-integration
plan: 01
subsystem: risk_guard
tags: [asyncio, queue, risk-checks, position-sizing, market-hours, daily-cap, alembic]
dependency_graph:
  requires:
    - 04-llm-analysis-engine (Signal model, analysis_worker)
    - 02-alpaca-executor (AlpacaExecutor, BotDisabledError, executor.execute)
    - 01-foundation (AppSettings, AsyncSessionLocal, get_settings)
  provides:
    - trumptrade.risk_guard (signal_queue, QueueItem)
    - trumptrade.risk_guard.guard (risk_consumer)
    - app_settings keys: max_position_size_pct, max_daily_loss_dollars, signal_staleness_minutes
  affects:
    - trumptrade/trading/executor.py (signal_id parameter added to execute and _log_order)
tech_stack:
  added: []
  patterns:
    - asyncio.Queue producer-consumer with module-level instantiation (Python 3.11+)
    - confidence-gated after-hours hold list with 24h expiry
    - naive UTC datetime comparison for SQLite stored datetimes
    - math.floor() for integer share qty (never round — avoids exceeding budget)
    - run_in_executor for all Alpaca SDK sync calls
key_files:
  created:
    - trumptrade/risk_guard/__init__.py
    - trumptrade/risk_guard/guard.py
    - alembic/versions/005_risk_settings.py
  modified:
    - trumptrade/trading/executor.py
decisions:
  - "QueueItem dataclass placed in guard.py (not models.py) — single file keeps risk logic self-contained; re-exported from __init__.py"
  - "float(equity_raw) with None-guard preferred over float(account.equity) — handles paper accounts with zero activity returning None for last_equity"
  - "settings_router=None placeholder in __init__.py — try/except ImportError guard allows package to be imported before router.py exists (created in plan 03)"
  - "executor.execute() patched with optional signal_id — enables full audit chain from Signal to Order (SC-4); backward-compatible (default None)"
metrics:
  duration_seconds: 200
  completed_date: "2026-04-21"
  tasks_completed: 2
  tasks_total: 2
  files_created: 3
  files_modified: 1
---

# Phase 5 Plan 01: Risk Guard Package Summary

**One-liner:** asyncio.Queue chokepoint in `trumptrade/risk_guard/` with staleness, market-hours, daily-cap, and position-sizing risk checks before any order reaches AlpacaExecutor.

## What Was Built

### trumptrade/risk_guard/guard.py

Full risk consumer pipeline:

- **`QueueItem` dataclass** — carries signal_id, post_id, tickers (list[str]), side, confidence, posted_at (naive UTC)
- **`_get_setting()`** — uses `scalar_one_or_none()` with default fallback (not `scalar_one()` which raises on missing key)
- **`_make_clients()`** — instantiates `TradingClient` + `StockHistoricalDataClient` fresh each cycle (D-06 no caching)
- **`_check_staleness()`** — compares `post.posted_at` (naive UTC) to `datetime.now(timezone.utc).replace(tzinfo=None)` to avoid SQLite timezone mismatch
- **`_check_daily_cap()`** — reads `last_equity` and `equity` as `Optional[str]` from Alpaca, converts to float, checks `(last_equity - equity) >= max_daily_loss_dollars`
- **`_compute_qty()`** — implements `equity * (max_pct/100) * confidence / share_price` with `math.floor()` for integer qty; returns None if qty < 1
- **`_execute_for_tickers()`** — places one trade per ticker with independent sizing; `processed` set enforces D-08 dedupe; catches `BotDisabledError`, `HTTPException`, and general exceptions
- **`_drain_hold_list_if_open()`** — checks `get_clock().is_open`, processes held signals oldest-first, expires signals >24h as STALE, enforces D-08 dedupe via `processed_tickers` set
- **`_process_signal()`** — staleness → market hours → daily cap → execute pipeline
- **`risk_consumer()`** — `while True` loop with `asyncio.CancelledError` re-raised; drains hold list at open, awaits queue item, runs pipeline

### trumptrade/risk_guard/__init__.py

- Exports `signal_queue` (`asyncio.Queue(maxsize=100)`) — safe module-level instantiation in Python 3.11+
- Re-exports `QueueItem` from `guard.py`
- Lazy `try/except ImportError` for `settings_router` — allows package import before `router.py` exists (plan 03)

### alembic/versions/005_risk_settings.py

Seeds three new `app_settings` keys with `INSERT OR IGNORE` (idempotent):
- `max_position_size_pct` = `'2.0'` (D-09)
- `max_daily_loss_dollars` = `'500.0'` (D-13)
- `signal_staleness_minutes` = `'5'` (D-15)

Does not touch pre-existing keys (`stop_loss_pct`, `position_size_pct`, `max_daily_loss_pct`).

### trumptrade/trading/executor.py (patch)

Added optional `signal_id: int | None = None` parameter to `execute()` and `_log_order()`. The `signal_id` is now stored in the `orders` table when an order is placed from the risk consumer, enabling full audit chain from Signal → Order (SC-4).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] executor.execute() signal_id parameter**
- **Found during:** Task 1 (guard.py calls `executor.execute(..., signal_id=item.signal_id)`)
- **Issue:** `executor.execute()` had no `signal_id` parameter; the call in guard.py would have raised a TypeError at runtime
- **Fix:** Added `signal_id: int | None = None` to both `execute()` and `_log_order()`; threads through to `Order` creation in DB
- **Files modified:** `trumptrade/trading/executor.py`
- **Commit:** 9bae731 (included in Task 1 commit)
- **Note:** This was documented as an open question in RESEARCH.md and explicitly recommended in PATTERNS.md — not a surprise; included in Task 1 as required for correctness

## Known Stubs

- `settings_router = None` in `__init__.py` — intentional placeholder; replaced when `router.py` is created in plan 03. Not a data stub; does not affect signal processing.

## Threat Surface Scan

No new network endpoints introduced. All Alpaca API calls are outbound-only via existing SDK patterns. Credentials read from env via `get_settings()`. T-05-01 through T-05-05 mitigations all implemented:
- `float()` conversion with None-check for equity fields (T-05-01)
- `asyncio.CancelledError: raise` before broad `Exception` handler (T-05-05)
- `processed_tickers` set in `_drain_hold_list_if_open` (T-05-03)

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| trumptrade/risk_guard/__init__.py exists | FOUND |
| trumptrade/risk_guard/guard.py exists | FOUND |
| alembic/versions/005_risk_settings.py exists | FOUND |
| Commit 9bae731 (Task 1) exists | FOUND |
| Commit 7c6279b (Task 2) exists | FOUND |
