---
phase: 05-risk-guard-integration
plan: 02
subsystem: risk_guard_wiring
tags: [asyncio, queue, wiring, integration, lifespan]
dependency_graph:
  requires:
    - 05-01 (risk_guard package: signal_queue, QueueItem, risk_consumer)
    - 04-llm-analysis-engine (analysis_worker, Signal model)
    - 02-alpaca-executor (AlpacaExecutor with signal_id — patched in 05-01)
  provides:
    - analysis_worker enqueues BUY/SELL QueueItems after Signal commit
    - risk_consumer runs as asyncio task in FastAPI lifespan
    - settings_router registered at /settings prefix (guarded until plan 03)
  affects:
    - trumptrade/analysis/worker.py (enqueue block + asyncio import)
    - trumptrade/core/app.py (lifespan consumer task + settings_router)
tech_stack:
  added: []
  patterns:
    - local import inside loop body for circular import avoidance (analysis_worker)
    - asyncio.create_task() in FastAPI lifespan for background consumer
    - cancel + await pattern for graceful consumer shutdown
    - settings_router None guard for plan execution order safety
key_files:
  created: []
  modified:
    - trumptrade/analysis/worker.py
    - trumptrade/core/app.py
decisions:
  - "executor.py signal_id parameter was already present from Plan 01 — Task 1 only needed worker.py patches"
  - "settings_router None guard retained per plan spec — will be permanently true when router.py created in plan 03"
  - "Consumer cancel placed before scheduler.shutdown in lifespan shutdown to prevent hang"
metrics:
  duration_seconds: 112
  completed_date: "2026-04-21"
  tasks_completed: 2
  tasks_total: 2
  files_created: 0
  files_modified: 2
---

# Phase 5 Plan 02: Pipeline Wiring Summary

**One-liner:** Three integration patches wire analysis_worker → signal_queue → risk_consumer → app lifespan, completing the end-to-end signal dispatch pipeline.

## What Was Built

### trumptrade/analysis/worker.py (patch)

Two changes applied:

**Change A — `import asyncio` added** to imports block (line 15). Required for `asyncio.QueueFull` exception handling in the enqueue block.

**Change B — enqueue block added** after `await session.commit()` in the Signal insert loop:

- Guards on `final_action in ("BUY", "SELL") and final_tickers` — SKIP signals are never enqueued (they are in DB for audit only)
- Builds `QueueItem` from `signal.id` (populated after commit by SQLAlchemy 2.x async), `post.id`, `final_tickers` (already `list[str]` — no `json.loads()` needed), `final_action`, `signal_result.confidence`, `post.posted_at` (naive UTC datetime)
- `signal_queue.put_nowait(item)` — non-blocking; `asyncio.QueueFull` is caught, logged as warning, and discarded (never blocks analysis_worker)
- `from trumptrade.risk_guard import signal_queue, QueueItem` is a local import inside the loop body — matches established codebase pattern for circular import avoidance

### trumptrade/core/app.py (patch)

Three changes applied:

**Change A — `import asyncio`** added to top-level imports (line 10).

**Change B — lifespan startup block** extended after `scheduler.start()`:
- `from trumptrade.risk_guard.guard import risk_consumer` — local import inside lifespan body
- `asyncio.create_task(risk_consumer(), name="risk_consumer")` — creates consumer task after scheduler starts, maintaining startup order
- Task stored as `_consumer_task` for shutdown cancellation

**Change C — lifespan shutdown block** extended before `scheduler.shutdown(wait=False)`:
- `_consumer_task.cancel()` — signals the consumer to stop
- `await _consumer_task` inside `try/except asyncio.CancelledError: pass` — prevents "Task destroyed but pending!" warning
- Consumer cancel precedes APScheduler shutdown (correct ordering)

**Change D — settings_router registration** in `create_app()` after trading router:
- `from trumptrade.risk_guard import settings_router` — local import
- `if settings_router is not None` guard — allows app to start before `router.py` exists (plan 03); guard will be permanently true after plan 03

### trumptrade/trading/executor.py

No changes needed. `signal_id: int | None = None` parameter was already added to both `execute()` and `_log_order()` in Plan 01 as part of that plan's Task 1 deviation. The `_log_order()` body already passes `signal_id` to `Order(...)` for full audit chain (SC-4).

## Deviations from Plan

### Plan Observation

**executor.py already patched** — Plan 02 Task 1 specified patching executor.py with the `signal_id` parameter, but this was already done in Plan 01 (documented in 05-01-SUMMARY.md as a Rule 2 auto-fix deviation). No re-patch was needed. Task 1 proceeded with only worker.py changes.

This is not a deviation from correctness — the code state matches the plan's `must_haves` exactly. The executor patches were simply applied one plan earlier than scheduled.

## Known Stubs

- `settings_router = None` in `risk_guard/__init__.py` — carried forward from Plan 01. The `if settings_router is not None` guard in `app.py` handles this correctly. Will be resolved when `router.py` is created in Plan 03.

## Threat Surface Scan

No new network endpoints introduced. `app.py` lifespan changes are internal process management only. `analysis_worker.py` enqueue is an in-process `put_nowait()` call — no external input crosses this boundary. T-05-06 (QueueFull DoS) mitigated by `asyncio.QueueFull` catch + warn + discard. T-05-08 (create_task before event loop) mitigated by placement inside lifespan async context.

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| trumptrade/analysis/worker.py modified | FOUND |
| trumptrade/core/app.py modified | FOUND |
| `import asyncio` in worker.py | FOUND (line 15) |
| `signal_queue.put_nowait` in worker.py | FOUND (1 match) |
| `signal_id: int | None = None` in executor.py | FOUND (2 matches) |
| `asyncio.create_task(risk_consumer` in app.py | FOUND (1 match) |
| `_consumer_task.cancel()` in app.py | FOUND |
| `await _consumer_task` in app.py | FOUND |
| `settings_router` registered in app.py | FOUND |
| Commit f2ed4dd (Task 1) exists | FOUND |
| Commit 6d4e34a (Task 2) exists | FOUND |
| `python -c "from trumptrade.core.app import create_app; create_app()"` | PASSED |
| `python -c "from trumptrade.analysis.worker import analysis_worker"` | PASSED |
