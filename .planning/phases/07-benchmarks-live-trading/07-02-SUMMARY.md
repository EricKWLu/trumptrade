---
phase: 07-benchmarks-live-trading
plan: "02"
subsystem: api
tags: [fastapi, benchmarks, shadow-portfolios, trading-mode, apscheduler]

# Dependency graph
requires:
  - phase: 07-01
    provides: benchmarks package with register_benchmark_jobs() and shadow_portfolio_snapshots table
  - phase: 05-risk-guard-integration
    provides: AppSettings write pattern (update + commit)
  - phase: 06-web-dashboard
    provides: dashboard router DB read pattern

provides:
  - GET /benchmarks endpoint returning normalized % return series for bot/spy/qqq/random
  - POST /trading/set-mode endpoint with two-gate validation (mode + confirmed)
  - benchmarks router wired into create_app() at /benchmarks
  - register_benchmark_jobs() called from create_app() lifespan

affects:
  - 07-03-live-trading-unlock (frontend uses POST /trading/set-mode)
  - 07-04-frontend-benchmarks-chart (frontend uses GET /benchmarks)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Pivot + normalize pattern: defaultdict pivot by date, first-NAV normalization to % return
    - Two-gate validation: mode enum check + confirmed=True guard before DB write
    - Local import inside endpoint body for sqlalchemy.update (matches existing trading/router.py pattern)

key-files:
  created:
    - trumptrade/benchmarks/router.py
  modified:
    - trumptrade/trading/router.py
    - trumptrade/core/app.py

key-decisions:
  - "GET /benchmarks returns {snapshots: [...]} wrapper dict (not bare list) — matches D-09 response shape"
  - "Normalization uses first available NAV per portfolio — handles staggered starts gracefully (None for missing)"
  - "POST /set-mode returns 422 (not 400) for invalid mode/confirmed=False — matches FastAPI validation convention"
  - "register_benchmark_jobs placed after Phase 4 analysis block in create_app() — preserves job startup order"

# Metrics
duration: ~2min
completed: 2026-04-23
---

# Phase 7 Plan 02: Benchmarks API + Trading Mode Endpoint Summary

**GET /benchmarks serving normalized % return series from shadow_portfolio_snapshots; POST /trading/set-mode with two-gate validation wired into existing trading router; both registered in create_app()**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-04-23T02:09:24Z
- **Completed:** 2026-04-23T02:10:49Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- `trumptrade/benchmarks/router.py` created — GET /benchmarks queries all ShadowPortfolioSnapshot rows, pivots by date, normalizes each portfolio series to % return from first available NAV, returns `{"snapshots": [...]}` (empty list when table empty)
- `trumptrade/trading/router.py` patched — SetModeRequest/SetModeResponse Pydantic models added; POST /set-mode validates mode in `{"paper","live"}` and confirmed=True (returns 422 otherwise), writes trading_mode to app_settings via UPDATE
- `trumptrade/core/app.py` patched — Phase 7 block registers benchmark snapshot jobs via `register_benchmark_jobs(scheduler)` and includes benchmarks router at `/benchmarks`

## Task Commits

Each task was committed atomically:

1. **Task 1: benchmarks/router.py** - `415d2eb` (feat)
2. **Task 2: trading/router.py + core/app.py** - `fad1803` (feat)

## Files Created/Modified

- `trumptrade/benchmarks/router.py` — GET /benchmarks with pivot + % return normalization
- `trumptrade/trading/router.py` — POST /trading/set-mode added with two-gate validation
- `trumptrade/core/app.py` — Phase 7 router + job registration blocks added

## Decisions Made

- Response shape `{"snapshots": [...]}` (dict wrapper, not bare list) per D-09 RESEARCH Pattern 4 decision
- Normalization: each portfolio uses its own first-available NAV as baseline — handles portfolios that may start on different dates by emitting `None` for missing values rather than crashing
- `confirmed=True` gate in set-mode is enforced server-side; client sends `confirmed: true` explicitly (defense-in-depth per T-07-04)
- Local imports inside `create_app()` for both router include and job registration — matches every other Phase N block in app.py

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — GET /benchmarks queries real DB rows; POST /set-mode writes real AppSettings.

## Threat Model Coverage

- T-07-04 (accidental live activation): two-gate check — `body.mode not in ("paper","live")` + `not body.confirmed` both return 422 before any DB write
- T-07-05 (injection via mode string): enum whitelist rejects any string outside `{"paper","live"}`; only whitelisted values reach the UPDATE statement
- T-07-06 (NAV data exposure): accepted per plan — single-user local tool, no auth layer

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| trumptrade/benchmarks/router.py exists | FOUND |
| trumptrade/trading/router.py exists | FOUND |
| trumptrade/core/app.py exists | FOUND |
| Commit 415d2eb exists | FOUND |
| Commit fad1803 exists | FOUND |
