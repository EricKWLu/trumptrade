---
phase: 07-benchmarks-live-trading
plan: "01"
subsystem: database
tags: [alembic, sqlite, apscheduler, alpaca-py, benchmarks, shadow-portfolios]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: ShadowPortfolioSnapshot model in core/models.py and SQLite DB
  - phase: 05-risk-guard-integration
    provides: AppSettings pattern and Watchlist model
  - phase: 06-web-dashboard
    provides: run_in_executor pattern for sync Alpaca calls

provides:
  - Alembic migration 006 adding UNIQUE INDEX on shadow_portfolio_snapshots(portfolio_name, snapshot_date)
  - trumptrade/benchmarks/__init__.py with register_benchmark_jobs() CronTrigger Mon-Fri 4:01pm ET
  - trumptrade/benchmarks/job.py with benchmark_snapshot_job() writing bot/spy/qqq/random snapshots daily

affects:
  - 07-02-benchmarks-api
  - 07-03-live-trading-unlock
  - 07-04-frontend-benchmarks-chart

# Tech tracking
tech-stack:
  added: []
  patterns:
    - CronTrigger with day_of_week + timezone for EOD market-hours jobs
    - StockHistoricalDataClient.get_stock_bars() in run_in_executor for non-blocking price fetches
    - STARTING_NAV = 100_000.0 virtual portfolio with positions_json carrying state day-to-day
    - Idempotency guard via _already_snapshotted() + DB UNIQUE INDEX (defense in depth)

key-files:
  created:
    - alembic/versions/006_benchmark_unique.py
    - trumptrade/benchmarks/__init__.py
    - trumptrade/benchmarks/job.py
  modified: []

key-decisions:
  - "STARTING_NAV=100_000.0 as virtual starting capital for all 3 shadow portfolios"
  - "Holiday detection: None return from _fetch_close_sync aborts job before writing any rows (atomic)"
  - "Random baseline carries cash in positions_json under 'cash' key — rehydrated from last snapshot"
  - "register_benchmark_jobs() uses misfire_grace_time=300 (5 min) for cron jobs vs 15s for interval jobs"

patterns-established:
  - "CronTrigger pattern: CronTrigger(day_of_week='mon-fri', hour=16, minute=1, timezone='US/Eastern')"
  - "_already_snapshotted() + UNIQUE INDEX = two-layer idempotency for daily jobs"
  - "Watchlist ticker price fetching: build today_prices dict, fetch missing symbols on demand"

requirements-completed: [COMP-01, COMP-02, COMP-03]

# Metrics
duration: 8min
completed: 2026-04-23
---

# Phase 7 Plan 01: Benchmarks Package Summary

**Daily EOD snapshot job writes bot/SPY/QQQ/random NAV rows to SQLite via CronTrigger, with UNIQUE INDEX guard and holiday skip via None from Alpaca bars API**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-04-23T20:05:29Z
- **Completed:** 2026-04-23T20:13:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Migration 006 adds `ix_shadow_portfolio_unique` on `(portfolio_name, snapshot_date)` — idempotent upgrade/downgrade
- `register_benchmark_jobs()` registers CronTrigger firing Mon-Fri at 16:01 US/Eastern with 5-min grace
- `benchmark_snapshot_job()` fetches SPY/QQQ closes via `StockHistoricalDataClient` in `run_in_executor`, bot equity from `TradingClient.get_account().equity`, simulates random watchlist trade, writes 4 rows atomically

## Task Commits

Each task was committed atomically:

1. **Task 1: Alembic migration 006** - `3ce1883` (chore)
2. **Task 2: benchmarks package** - `a7223cd` (feat)

**Plan metadata:** (docs commit below)

## Files Created/Modified
- `alembic/versions/006_benchmark_unique.py` - UNIQUE INDEX migration on shadow_portfolio_snapshots
- `trumptrade/benchmarks/__init__.py` - register_benchmark_jobs() with CronTrigger
- `trumptrade/benchmarks/job.py` - benchmark_snapshot_job() coroutine: fetch SPY/QQQ/bot, simulate random, write 4 snapshots

## Decisions Made
- STARTING_NAV set to 100_000.0 (virtual capital) — all shadow portfolios start from the same base
- Random baseline stores cash as `positions_json["cash"]` to carry state across days without an extra DB column
- Holiday detection relies on None from `_fetch_close_sync` (no bar returned) — entire job aborts if SPY or QQQ bar missing, preventing partial writes
- `misfire_grace_time=300` for the cron job (5 min) vs 15s for interval jobs — cron fires once/day so grace window needs to be wider

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered
None.

## Threat Model Coverage
- T-07-01 (DoS via fetch failure): all Alpaca calls wrapped in try/except; job returns without writing on any error
- T-07-02 (duplicate rows): _already_snapshotted() guard + UNIQUE INDEX from migration 006 prevents duplicates
- T-07-03 (empty watchlist crash): `if watchlist:` guard ensures random.choice() is never called on empty list

## Known Stubs
None — benchmark_snapshot_job() is fully wired to real Alpaca data; no placeholder returns.

## Next Phase Readiness
- `trumptrade/benchmarks/job.py` is the data producer; plan 07-02 can now build `GET /benchmarks` endpoint reading `shadow_portfolio_snapshots`
- `register_benchmark_jobs()` ready to wire into `create_app()` in plan 07-02 or 07-04

---
*Phase: 07-benchmarks-live-trading*
*Completed: 2026-04-23*
