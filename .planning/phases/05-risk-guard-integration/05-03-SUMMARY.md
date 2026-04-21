---
phase: 05-risk-guard-integration
plan: 03
subsystem: risk_guard_settings_endpoint
tags: [fastapi, router, settings, pydantic, patch-semantics]
dependency_graph:
  requires:
    - 05-01 (risk_guard package: guard.py, __init__.py, signal_queue, QueueItem)
    - 05-02 (pipeline wiring: analysis_worker enqueue, app.py lifespan consumer task)
    - 01-foundation (AppSettings model, AsyncSessionLocal)
  provides:
    - GET /settings/risk — returns all 4 risk settings as JSON
    - PATCH /settings/risk — partial update, returns all current values after write
    - settings_router (real FastAPI router, no longer None)
  affects:
    - trumptrade/risk_guard/__init__.py (stub removed, direct import)
    - trumptrade/core/app.py (None guard removed, unconditional router registration)
tech_stack:
  added: []
  patterns:
    - PATCH semantics via model_dump(exclude_none=True) — only non-None fields written
    - scalar_one_or_none() with default fallback for app_settings reads
    - FastAPI APIRouter with Pydantic BaseModel request/response (trading/router.py analog)
    - HTTPException 500 on DB errors (log + raise, never swallow)
key_files:
  created:
    - trumptrade/risk_guard/router.py
  modified:
    - trumptrade/risk_guard/__init__.py
    - trumptrade/core/app.py
decisions:
  - "router.py uses _read_setting() helper per key (4 separate selects) — avoids complex multi-key query; DB is SQLite local, overhead negligible"
  - "PATCH with empty body returns 200 with current values unchanged — correct PATCH semantics per T-05-12 (not a vulnerability)"
  - "None guard removed from app.py — router.py now exists; unconditional include_router() is cleaner"
  - "RiskSettingsPatch uses Optional fields with Field(gt=0) validators — T-05-10 Pydantic validation at schema layer"
metrics:
  duration_seconds: 90
  completed_date: "2026-04-21"
  tasks_completed: 1
  tasks_total: 2
  files_created: 1
  files_modified: 2
---

# Phase 5 Plan 03: Settings Router Summary

**One-liner:** GET/PATCH /settings/risk FastAPI router with Pydantic validation, partial-update semantics, and settings_router stub replaced by direct import.

## What Was Built

### trumptrade/risk_guard/router.py (new)

Full settings router for the 4 configurable risk controls:

- **`RiskSettingsResponse`** — Pydantic model with all 4 fields: `max_position_size_pct` (float), `stop_loss_pct` (float), `max_daily_loss_dollars` (float), `signal_staleness_minutes` (int)
- **`RiskSettingsPatch`** — All fields Optional with Field validators: `gt=0, le=100` for percentages, `gt=0` for dollars and minutes. PATCH semantics via `model_dump(exclude_none=True)`.
- **`_read_setting(key, default)`** — uses `scalar_one_or_none()` with default fallback (not `scalar_one()` which raises on missing key — matches worker.py pattern)
- **`_read_all_risk_settings()`** — reads all 4 keys, converts str→float/int, returns `RiskSettingsResponse`
- **`GET /risk`** — returns current settings; 500 on DB error
- **`PATCH /risk`** — writes only non-None fields atomically in a single session, then returns all current values; empty-body PATCH returns current values without DB write

### trumptrade/risk_guard/__init__.py (updated)

- Removed `try/except ImportError` stub for `settings_router`
- Now uses direct import: `from trumptrade.risk_guard.router import router as settings_router`
- `settings_router` is now guaranteed non-None at import time

### trumptrade/core/app.py (updated)

- Removed `if settings_router is not None` guard
- `app.include_router(settings_router, prefix="/settings", tags=["settings"])` is now unconditional

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Removed None guard from app.py**
- **Found during:** Task 1
- **Issue:** Plan spec said settings_router stub should be replaced in __init__.py, but app.py still had `if settings_router is not None` guard that was only needed during plan execution order safety. With router.py now created, the guard is dead code that could mask future import failures.
- **Fix:** Removed the guard, making `include_router()` unconditional
- **Files modified:** `trumptrade/core/app.py`
- **Commit:** ef6af47

## Known Stubs

None — `settings_router = None` stub has been removed. All 4 risk settings are read from the live `app_settings` DB table (seeded by migration 005 in Plan 01).

## Threat Surface Scan

New network endpoints introduced:

| Flag | File | Description |
|------|------|-------------|
| threat_flag: new_http_endpoint | trumptrade/risk_guard/router.py | GET /settings/risk — exposes risk configuration |
| threat_flag: new_http_endpoint | trumptrade/risk_guard/router.py | PATCH /settings/risk — mutates risk controls |

Both endpoints already covered in the plan's threat model:
- T-05-10: Pydantic Field(gt=0, le=100) validation implemented
- T-05-11: model_dump(exclude_none=True) only writes known keys — extra fields ignored
- T-05-12: Empty-body PATCH returns 200 with current values — correct behavior
- T-05-13: Single-user tool, no auth in Phase 5 scope

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| trumptrade/risk_guard/router.py exists | FOUND |
| trumptrade/risk_guard/__init__.py updated (stub removed) | FOUND |
| trumptrade/core/app.py updated (None guard removed) | FOUND |
| Commit ef6af47 (Task 1) exists | FOUND |
| /settings/risk in app routes | FOUND (2 entries: GET + PATCH) |
| settings_router is non-None | PASSED |
| No try/except ImportError in __init__.py | CONFIRMED (grep exit 1) |

## Checkpoint Status

Task 2 (`checkpoint:human-verify`) reached. Awaiting human verification of the complete Phase 5 end-to-end pipeline.
