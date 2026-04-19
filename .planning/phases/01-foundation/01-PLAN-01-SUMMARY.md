---
phase: 01-foundation
plan: "01"
subsystem: infra
tags: [python, fastapi, pydantic-settings, sqlalchemy, uvicorn, apscheduler, alpaca-py, httpx]

# Dependency graph
requires: []
provides:
  - trumptrade Python package installable via pip install -e .
  - trumptrade.core.config — Pydantic Settings v2 singleton loading secrets from .env
  - trumptrade.core.logging — structured JSON logging setup
  - trumptrade.core.app — FastAPI application factory with lifespan context manager
  - trumptrade.__main__ — entry point (python -m trumptrade or CLI script)
  - five domain stub sub-packages (ingestion, analysis, trading, risk, dashboard)
affects: [01-PLAN-02, 01-PLAN-03, 01-PLAN-04, 01-PLAN-05, all-phases]

# Tech tracking
tech-stack:
  added:
    - fastapi>=0.115.0
    - uvicorn[standard]>=0.29.0
    - pydantic>=2.7.0
    - pydantic-settings>=2.2.0
    - sqlalchemy[asyncio]>=2.0.30
    - aiosqlite>=0.20.0
    - alembic>=1.13.0
    - apscheduler>=3.10.0
    - httpx>=0.27.0
    - tweepy>=4.14.0
    - openai>=1.30.0
    - alpaca-py>=0.20.0
    - beautifulsoup4>=4.12.0
    - lxml>=5.2.0
  patterns:
    - Pydantic Settings v2 lru_cache singleton via get_settings()
    - FastAPI lifespan context manager for scheduler start/stop
    - Structured JSON logging with JsonFormatter to stdout
    - Domain-per-package layout (ingestion/analysis/trading/risk/dashboard)
    - .env for secrets only; runtime-editable settings in app_settings DB table (D-08/D-09)

key-files:
  created:
    - pyproject.toml
    - .env.example
    - .gitignore
    - trumptrade/__init__.py
    - trumptrade/__main__.py
    - trumptrade/core/__init__.py
    - trumptrade/core/config.py
    - trumptrade/core/logging.py
    - trumptrade/core/app.py
    - trumptrade/ingestion/__init__.py
    - trumptrade/analysis/__init__.py
    - trumptrade/trading/__init__.py
    - trumptrade/risk/__init__.py
    - trumptrade/dashboard/__init__.py
  modified: []

key-decisions:
  - "Used alpaca-py (not deprecated alpaca-trade-api) per CLAUDE.md rule 1"
  - "Used httpx (not requests) in dependency list per CLAUDE.md rule 2"
  - "Pydantic Settings model_config = SettingsConfigDict (v2 form, not deprecated class Config)"
  - "trading_mode and runtime settings NOT in config.py — deferred to app_settings DB table per D-09"
  - "FastAPI lifespan asynccontextmanager (not deprecated @app.on_event) per research guidance"
  - "JsonFormatter outputs single-line JSON for machine readability"

patterns-established:
  - "Config pattern: from trumptrade.core.config import get_settings; s = get_settings()"
  - "Logging pattern: from trumptrade.core.logging import setup_logging; setup_logging() at startup"
  - "App factory pattern: from trumptrade.core.app import create_app; app = create_app()"
  - "Test override pattern: get_settings.cache_clear() then monkeypatch env vars"

requirements-completed: []

# Metrics
duration: 3min
completed: 2026-04-19
---

# Phase 1 Plan 01: Python Package Scaffold Summary

**Installable trumptrade Python package with Pydantic Settings v2 config, JSON structured logging, FastAPI app factory, and five domain stub sub-packages — all importable via pip install -e .**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-19T05:16:19Z
- **Completed:** 2026-04-19T05:18:52Z
- **Tasks:** 2
- **Files modified:** 14

## Accomplishments
- pyproject.toml with all 14 project dependencies declared (alpaca-py not alpaca-trade-api, httpx not requests), CLI entry point, and pip install -e . succeeding
- trumptrade.core.config: Pydantic Settings v2 singleton with lru_cache, loading secrets from .env with safe empty defaults; runtime-editable settings deferred to app_settings DB table per D-08/D-09
- trumptrade.core.logging: JSON structured logging with JsonFormatter; trumptrade.core.app: FastAPI factory with lifespan asynccontextmanager; five domain stub sub-packages with consistent import paths from day one

## Task Commits

Each task was committed atomically:

1. **Task 1: Create pyproject.toml, .gitignore, and .env.example** - `a59a5c7` (feat)
2. **Task 2: Create trumptrade package: core/ modules and domain stub sub-packages** - `302caa4` (feat)

## Files Created/Modified
- `pyproject.toml` - Package metadata, 14 dependencies, entry point trumptrade.__main__:main
- `.env.example` - All secrets as empty values template; .env gitignored
- `.gitignore` - Secrets, Python artifacts, node_modules, IDE files
- `trumptrade/__init__.py` - Package marker (empty)
- `trumptrade/__main__.py` - Entry point: main() calls uvicorn.run(create_app(), ...)
- `trumptrade/core/__init__.py` - Core sub-package marker (empty)
- `trumptrade/core/config.py` - Settings(BaseSettings) with SettingsConfigDict; get_settings() with @lru_cache
- `trumptrade/core/logging.py` - JsonFormatter + setup_logging() for structured JSON stdout logging
- `trumptrade/core/app.py` - create_app() FastAPI factory with lifespan context manager, /health endpoint
- `trumptrade/ingestion/__init__.py` - Stub (Phase 3)
- `trumptrade/analysis/__init__.py` - Stub (Phase 4)
- `trumptrade/trading/__init__.py` - Stub (Phase 5)
- `trumptrade/risk/__init__.py` - Stub (Phase 5)
- `trumptrade/dashboard/__init__.py` - Stub (Phase 6)

## Decisions Made
- Used `alpaca-py` (not deprecated `alpaca-trade-api`) per CLAUDE.md critical rule
- Used `httpx` in dependencies (not `requests`) per CLAUDE.md critical rule
- `trading_mode` and all runtime-editable settings deliberately excluded from config.py — they live in the `app_settings` DB table per D-09
- FastAPI `lifespan` asynccontextmanager used (not deprecated `@app.on_event`) per research guidance
- Pydantic Settings v2 `model_config = SettingsConfigDict(...)` form (not deprecated `class Config:`)

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

The five domain sub-packages contain intentional placeholder stubs per plan D-03:
- `trumptrade/ingestion/__init__.py` — Phase 3 (Truth Social + X/Twitter polling)
- `trumptrade/analysis/__init__.py` — Phase 4 (LLM + keyword analysis)
- `trumptrade/trading/__init__.py` — Phase 5 (Alpaca order execution)
- `trumptrade/risk/__init__.py` — Phase 5 (position sizing, daily cap)
- `trumptrade/dashboard/__init__.py` — Phase 6 (FastAPI routes + WebSocket)

These stubs are intentional per D-03 ("consistent import paths from day one, no renaming later"). The `core/app.py` lifespan also has scheduler stubs deferred to Plan 05. None prevent this plan's goal (the importable scaffold).

## Issues Encountered
None

## User Setup Required
None - no external service configuration required for the scaffold. API keys go in `.env` (copy from `.env.example`) when services are implemented in later phases.

## Next Phase Readiness
- Package structure established; all downstream plans can `from trumptrade.core.config import get_settings` immediately
- Plan 02 (SQLAlchemy models + Alembic migrations) can now import from `trumptrade.core`
- Plan 03 (Alembic init + DB session factory) can import from `trumptrade.core.config`
- No blockers for any downstream plan in Wave 1 or Wave 2

---
*Phase: 01-foundation*
*Completed: 2026-04-19*

## Self-Check: PASSED

All files found. All task commits verified (a59a5c7, 302caa4). SUMMARY committed (cf2d43f).
