# State: TrumpTrade

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-19)

**Core value:** Automatically detect and act on Trump's social media posts faster than a human can react — turning his words into trade signals before the market moves.
**Current focus:** Phase 7 - Benchmarks + Live Trading

## Current Position

Phase: 7 of 7 (Benchmarks + Live Trading) — executing
Plan: 3 of 4 in current phase
Status: Phase 7 executing — 07-03 complete (BenchmarksPage + Recharts LineChart + api.ts + router.tsx)
Last activity: 2026-04-23 — 07-03 complete: BenchmarksPage.tsx + BenchmarkChart + recharts install + dialog.tsx

Progress: [█████████░] 93%

## Performance Metrics

**Velocity:**
- Total plans completed: 10
- Average duration: ~8 min/plan
- Total execution time: ~1.2 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1. Foundation | 5/5 | ~40 min | ~8 min |
| 2. Alpaca Executor | 2/2 | ~16 min | ~8 min |
| 3. Ingestion Pipeline | 4/4 | ~25 min | ~6 min |
| 4. LLM Analysis Engine | 3/3 | ~25 min | ~8 min |
| 5. Risk Guard + Integration | 3/3 | ~19 min | ~6 min |
| 6. Web Dashboard | 5/5 | ~40 min | ~8 min |
| 7. Benchmarks + Live Trading | 3/4 | ~12 min | ~4 min |

**Recent Trend:**
- Last 3 plans: 04-03, 05-01
- Trend: On track

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Use `alpaca-py` (not deprecated `alpaca-trade-api`)
- Truth Social uses Mastodon-compatible JSON API (not HTML scraping)
- APScheduler in-process — no Celery/Redis needed
- Bracket orders only — stop-loss always atomic with entry
- `TRADING_MODE` enum: single config flag, not two code branches
- QueueItem in guard.py (not models.py) — re-exported from __init__.py; keeps risk logic self-contained
- executor.execute() accepts optional signal_id — enables full audit chain Signal → Order (SC-4)
- settings_router=None placeholder in __init__.py — try/except ImportError guard until router.py created in plan 03
- router.py uses _read_setting() helper per key (4 separate selects) — avoids complex multi-key query; DB is SQLite local, overhead negligible
- PATCH with empty body returns 200 with current values unchanged — correct PATCH semantics (T-05-12: not a vulnerability)
- None guard removed from app.py — router.py now exists; unconditional include_router() is cleaner
- STARTING_NAV=100_000.0 as virtual starting capital for all 3 shadow portfolios
- Holiday detection: None return from _fetch_close_sync aborts job before writing any rows (atomic)
- Random baseline carries cash in positions_json under 'cash' key — rehydrated from last snapshot
- register_benchmark_jobs() uses misfire_grace_time=300 (5 min) for cron jobs vs 15s for interval jobs
- GET /benchmarks returns {"snapshots": [...]} wrapper dict (not bare list) — matches D-09 response shape
- POST /set-mode returns 422 for invalid mode or confirmed=False — two-gate validation (T-07-04)
- Normalization uses first available NAV per portfolio — handles staggered starts with None for missing values
- BenchmarkChart inline in BenchmarksPage (no separate file) — single-use component per UI-SPEC Section 2d
- connectNulls=false on all 4 Line components — backend returns null for portfolios not yet started
- staleTime=refetchInterval=300_000 for benchmarks — data only updates at market close (5 min polling)

### Pending Todos

None yet.

### Blockers/Concerns

None yet.

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-04-23
Stopped at: Phase 7 plan 07-03 complete — BenchmarksPage + Recharts LineChart + api.ts + router.tsx
Resume file: .planning/phases/07-benchmarks-live-trading/07-04-PLAN.md
