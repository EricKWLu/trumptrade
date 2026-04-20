---
phase: "03-ingestion-pipeline"
plan: "01"
subsystem: ingestion
tags: [filters, heartbeat, pre-filter, market-hours, INGEST-01, INGEST-04]
one_liner: "Post pre-filter logic (filters.py) and heartbeat silence alerter (heartbeat.py) as Wave 1 building blocks for pollers"

dependency_graph:
  requires:
    - trumptrade.core.db.AsyncSessionLocal
    - trumptrade.core.models.Post
    - trumptrade.core.models.AppSettings
    - pytz
  provides:
    - trumptrade.ingestion.filters.apply_filters
    - trumptrade.ingestion.filters.FINANCIAL_KEYWORDS
    - trumptrade.ingestion.heartbeat.check_heartbeat
  affects:
    - trumptrade/ingestion/__init__.py  (pollers in Wave 2 will import from here)

tech_stack:
  added: []
  patterns:
    - frozenset for module-level constants (hashable, faster set intersection)
    - datetime.now(utc).astimezone(eastern) for DST-safe timezone conversion
    - Two separate AsyncSessionLocal blocks (settings read then count query)
    - scalar_one_or_none for nullable AppSettings reads

key_files:
  created:
    - trumptrade/ingestion/filters.py
    - trumptrade/ingestion/heartbeat.py
    - tests/ingestion/__init__.py
    - tests/ingestion/test_filters.py
    - tests/ingestion/test_heartbeat.py
  modified: []

decisions:
  - "frozenset for FINANCIAL_KEYWORDS (not plain set) — hashable, marginally faster intersection"
  - "Two separate AsyncSessionLocal sessions in check_heartbeat — short-lived, avoids holding connection open during timezone computation"
  - "datetime.now(utc).astimezone() pattern for ET — avoids DST edge case in pytz.localize()"

metrics:
  duration_seconds: 149
  completed_date: "2026-04-20"
  tasks_completed: 2
  tasks_total: 2
  files_created: 5
  files_modified: 0
---

# Phase 03 Plan 01: Ingestion Utilities — filters.py and heartbeat.py

**Summary:** Post pre-filter logic (filters.py) and heartbeat silence alerter (heartbeat.py) as Wave 1 building blocks for pollers

## What Was Built

Two standalone ingestion utilities that Wave 2 pollers depend on:

1. **`trumptrade/ingestion/filters.py`** — `apply_filters(text)` classifies posts via three ordered rules (D-07):
   - `too_short` — content under 100 characters
   - `pure_repost` — starts with `RT @` (case-insensitive)
   - `no_financial_keywords` — no word in the 29-term D-08 keyword list
   - Returns `(False, None)` when post passes all filters
   - `FINANCIAL_KEYWORDS` frozenset holds all 29 terms from D-08

2. **`trumptrade/ingestion/heartbeat.py`** — `check_heartbeat()` async coroutine (D-09/D-10):
   - Reads `heartbeat_start_hour` and `heartbeat_end_hour` from `app_settings` (defaults 9/17)
   - Skips entirely outside the configured US/Eastern daytime window
   - Queries `posts` table for Truth Social posts in the last 30 minutes
   - Logs `WARNING: "HEARTBEAT: no Truth Social posts in last 30 minutes"` when count == 0

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create filters.py | adb6671 | trumptrade/ingestion/filters.py, tests/ingestion/test_filters.py |
| 2 | Create heartbeat.py | b51ec30 | trumptrade/ingestion/heartbeat.py, tests/ingestion/test_heartbeat.py |

**TDD commits:**
- 638f0af — test(03-01): RED tests for filters.py
- adb6671 — feat(03-01): GREEN implementation for filters.py
- 46769a1 — test(03-01): RED tests for heartbeat.py
- b51ec30 — feat(03-01): GREEN implementation for heartbeat.py

## Test Coverage

- 15 tests for `apply_filters` / `FINANCIAL_KEYWORDS` (all pass)
- 14 tests for `check_heartbeat` / `_is_market_hours` (all pass)
- 36 total tests passing across the project (no regressions)

## TDD Gate Compliance

- RED gate: test(03-01) commits exist before feat(03-01) commits for both tasks
- GREEN gate: feat(03-01) commits follow RED commits for both tasks
- Sequence: RED filters → GREEN filters → RED heartbeat → GREEN heartbeat

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — both files are fully implemented with no placeholders.

## Threat Flags

No new security-relevant surface introduced. Both files:
- `filters.py`: pure stateless transform, no I/O, no eval/exec/SQL (T-03-01: accepted)
- `heartbeat.py`: logs only count and the exact warning string — no post content, no credentials (T-03-02: mitigated)

## Self-Check

### Files Exist

- [x] `trumptrade/ingestion/filters.py` — FOUND
- [x] `trumptrade/ingestion/heartbeat.py` — FOUND
- [x] `tests/ingestion/test_filters.py` — FOUND
- [x] `tests/ingestion/test_heartbeat.py` — FOUND

### Commits Exist

- [x] 638f0af — FOUND (RED filters)
- [x] adb6671 — FOUND (GREEN filters)
- [x] 46769a1 — FOUND (RED heartbeat)
- [x] b51ec30 — FOUND (GREEN heartbeat)

## Self-Check: PASSED
