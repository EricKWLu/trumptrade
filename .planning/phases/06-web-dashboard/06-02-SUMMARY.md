---
phase: 06-web-dashboard
plan: "02"
subsystem: dashboard
tags: [fastapi, sqlalchemy, alpaca, async, read-endpoints]
dependency_graph:
  requires: []
  provides: [dashboard-read-endpoints]
  affects: [frontend-tanstack-query-hooks]
tech_stack:
  added: []
  patterns:
    - run_in_executor for alpaca-py sync SDK calls
    - LEFT OUTER JOIN across Order+Signal+Post+Fill for audit chain
    - Module-level in-memory alert store with append_alert/clear_alerts
key_files:
  created:
    - trumptrade/dashboard/router.py
  modified: []
decisions:
  - TradingClient instantiated per-request inside get_portfolio (not module-level) — trading_mode re-read each call per D-06
  - get_portfolio uses two separate run_in_executor calls (get_account + get_all_positions) — keeps calls composable
  - _alerts is module-level list — survives process lifetime; restarts clear stale alerts (accepted per T-06-02-05)
  - Query(le=200) cap on /posts limit mitigates DoS per T-06-02-02
  - llm_prompt/llm_response exposed in /trades response — intentional per D-08 (single-user debugging tool)
metrics:
  duration: "~4 min"
  completed: "2026-04-21"
  tasks_completed: 2
  files_created: 1
  files_modified: 0
---

# Phase 6 Plan 02: Dashboard Read Endpoints Summary

**One-liner:** Four FastAPI read endpoints (GET /posts, /trades, /portfolio, /alerts) with SQLAlchemy LEFT OUTER JOIN audit chain and Alpaca run_in_executor proxy.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | GET /posts + GET /trades + GET /alerts + alert helpers | b5997d1 | trumptrade/dashboard/router.py |
| 2 | GET /portfolio with run_in_executor | b5997d1 | trumptrade/dashboard/router.py (same file) |

**Note:** Both tasks were implemented in a single complete file write (router.py), committed atomically as b5997d1. Task 2's portfolio route was included in the initial write rather than appended separately. All Task 2 acceptance criteria verified independently.

## What Was Built

`trumptrade/dashboard/router.py` provides:

- **GET /posts** — Paginated (default 50, max 200) post feed ordered newest-first. Returns `id, platform, content, posted_at, created_at, is_filtered, filter_reason`.
- **GET /trades** — Full audit chain via LEFT OUTER JOINs: `Order → Signal → Post → Fill`. Returns `llm_prompt` and `llm_response` per D-08 (debugging). Limited to 200 rows.
- **GET /portfolio** — Live Alpaca data proxied via `asyncio.get_running_loop().run_in_executor(None, ...)` for both `get_account()` and `get_all_positions()`. Returns `equity, last_equity, pl_today, buying_power, trading_mode, positions[]`. Raises HTTP 502 on Alpaca API errors.
- **GET /alerts** — Returns snapshot of module-level `_alerts` list.
- **`append_alert(source, message)`** — Called by risk_guard, ingestion to surface errors into the alert panel.
- **`clear_alerts()`** — Clears all alerts.

## Deviations from Plan

None — plan executed exactly as written. The complete router.py (all 4 routes) was written in one pass rather than two sequential writes, but all acceptance criteria for both tasks were verified independently.

## Known Stubs

None. All endpoints return real data (DB queries or live Alpaca API). No hardcoded values or placeholders.

## Threat Flags

No new security surface beyond what was documented in the plan's threat model.

| T-ID | Mitigation Status |
|------|-------------------|
| T-06-02-01 | Accepted — intentional per D-08 |
| T-06-02-02 | Mitigated — Query(le=200) cap implemented |
| T-06-02-03 | Accepted — env-based credentials |
| T-06-02-04 | Mitigated — run_in_executor on both Alpaca calls |
| T-06-02-05 | Accepted — in-memory list, restarts clear stale alerts |

## Self-Check

**Files exist:**
- trumptrade/dashboard/router.py: FOUND

**Commits exist:**
- b5997d1: FOUND

## Self-Check: PASSED
