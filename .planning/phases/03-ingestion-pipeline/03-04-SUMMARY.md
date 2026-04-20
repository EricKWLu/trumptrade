---
phase: "03-ingestion-pipeline"
plan: "04"
subsystem: ingestion
tags: [apscheduler, ingestion, scheduler, wiring, truth-social, twitter, heartbeat, INGEST-01, INGEST-02, INGEST-03, INGEST-04]
one_liner: "Ingestion package wired into the running app via register_ingestion_jobs() registering 3 APScheduler jobs (Truth Social 60s, Twitter 5min, heartbeat 15min) activated on every create_app() call"

dependency_graph:
  requires:
    - trumptrade.ingestion.truth_social.poll_truth_social (03-02)
    - trumptrade.ingestion.twitter.poll_twitter (03-03)
    - trumptrade.ingestion.heartbeat.check_heartbeat (03-01)
    - trumptrade.core.app.scheduler (Phase 1 foundation)
  provides:
    - trumptrade.ingestion.register_ingestion_jobs
    - All 3 ingestion APScheduler jobs active on app startup
  affects:
    - Phase 4 (LLM analyzer) — ingestion pipeline fully running
    - Phase 5 (trading integration) — posts flow into analysis queue

tech_stack:
  added: []
  patterns:
    - register_ingestion_jobs(scheduler) function in package __init__.py wires all pollers
    - Local import inside create_app() to avoid circular imports (same as Phase 2 trading_router pattern)
    - stable job IDs (replace_existing=True) prevent duplicate registrations on hot-reload
    - All jobs: coalesce=True, max_instances=1 for safe interval scheduling

key_files:
  created: []
  modified:
    - trumptrade/ingestion/__init__.py
    - trumptrade/core/app.py

key_decisions:
  - "Local import inside create_app() for register_ingestion_jobs — matches Phase 2 pattern, avoids circular import"
  - "Module-level coroutine imports in ingestion/__init__.py — APScheduler receives proper callable references, not string paths"
  - "replace_existing=True on all jobs — idempotent registration safe for hot-reload and test re-runs"

patterns-established:
  - "Package __init__.py exposes single registration function (register_ingestion_jobs) — callers never touch individual poller modules"
  - "Local import pattern for sub-package registration in create_app() — established by Phase 2 trading_router, replicated for Phase 3"

requirements-completed: [INGEST-01, INGEST-02, INGEST-03, INGEST-04]

metrics:
  duration_seconds: 300
  completed_date: "2026-04-21"
  tasks_completed: 2
  tasks_total: 2
  files_created: 0
  files_modified: 2
---

# Phase 03 Plan 04: Ingestion Scheduler Wiring Summary

**Ingestion package wired into the running app via register_ingestion_jobs() registering 3 APScheduler jobs (Truth Social 60s, Twitter 5min, heartbeat 15min) activated on every create_app() call**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-04-21
- **Completed:** 2026-04-21
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- `ingestion/__init__.py` replaced stub with `register_ingestion_jobs(scheduler)` that adds all 3 APScheduler jobs with stable IDs, replace_existing=True, coalesce=True, and max_instances=1
- `trumptrade/core/app.py` patched — Phase 3 block added after Phase 2 trading router wiring, local import pattern used to avoid circular imports
- Full smoke test confirmed: `create_app()` returns without error, all 3 jobs (ingestion_truth_social, ingestion_twitter, ingestion_heartbeat) present in scheduler.get_jobs()
- Phase 3 ingestion pipeline complete — all 4 requirements (INGEST-01 through INGEST-04) delivered across plans 01–04

## Task Commits

Each task was committed atomically:

1. **Task 1: Populate ingestion/__init__.py with register_ingestion_jobs()** - `b37cb39` (feat)
2. **Task 2: Wire register_ingestion_jobs() into create_app() in app.py** - `e0fb02d` (feat)

## Files Created/Modified

- `trumptrade/ingestion/__init__.py` — Replaced stub; exports `register_ingestion_jobs(scheduler)` + imports all 3 coroutines at module level
- `trumptrade/core/app.py` — Added Phase 3 block (local import + call to register_ingestion_jobs) after Phase 2 trading router block

## Decisions Made

- Local import inside `create_app()` for `register_ingestion_jobs` — matches the Phase 2 `trading_router` pattern, prevents circular import between core.app and ingestion package
- Module-level coroutine imports in `ingestion/__init__.py` — ensures APScheduler receives proper callable objects rather than string lookup paths
- `replace_existing=True` on all three jobs — makes registration idempotent; safe for hot-reload and test environments that call `create_app()` multiple times

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — both modified files are fully implemented with no placeholders.

## Threat Flags

No new security surface introduced. Threat mitigations from plan applied:

| Threat ID | Mitigation | Status |
|-----------|------------|--------|
| T-03-13 | replace_existing=True + stable job IDs on all 3 jobs | Implemented |
| T-03-14 | max_instances=1 on all 3 jobs | Implemented |
| T-03-15 | Local import is anti-circular pattern only; module is trusted code | Accepted |

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required by this plan. (External service credentials for Truth Social and X/Twitter were addressed in plans 03-01 through 03-03.)

## Phase 3 Complete — Full Ingestion Pipeline Delivered

All Phase 3 files across plans 03-01 through 03-04:

| File | Plan | Purpose |
|------|------|---------|
| `trumptrade/ingestion/filters.py` | 03-01 | Keyword filter + signal classification |
| `trumptrade/ingestion/heartbeat.py` | 03-01 | 15-min watchdog heartbeat |
| `trumptrade/ingestion/truth_social.py` | 03-02 | Truth Social Mastodon API poller |
| `trumptrade/core/config.py` | 03-02 | truth_social_token added to Settings |
| `trumptrade/ingestion/twitter.py` | 03-03 | X/Twitter tweepy async poller |
| `trumptrade/ingestion/__init__.py` | 03-04 | register_ingestion_jobs() + package exports |
| `trumptrade/core/app.py` | 03-04 | Ingestion jobs activated at startup |

## Next Phase Readiness

- Phase 4 (LLM Analyzer) can import any ingestion module without circular-import risk
- Posts are SHA-256 deduped and filter-classified before reaching the analysis queue
- APScheduler is running and jobs are active on every app startup — no manual initialization needed
- All 4 ingestion requirements (INGEST-01, INGEST-02, INGEST-03, INGEST-04) are satisfied

---

## Self-Check

### Files Exist

- [x] `trumptrade/ingestion/__init__.py` — FOUND, contains register_ingestion_jobs
- [x] `trumptrade/core/app.py` — FOUND, contains register_ingestion_jobs call

### Commits Exist

- [x] b37cb39 — Task 1 (ingestion/__init__.py)
- [x] e0fb02d — Task 2 (app.py wiring)

## Self-Check: PASSED

---
*Phase: 03-ingestion-pipeline*
*Completed: 2026-04-21*
