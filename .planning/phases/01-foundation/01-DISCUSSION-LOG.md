# Phase 1: Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-19
**Phase:** 01-foundation
**Areas discussed:** Package structure, DB schema scope, Settings model, Frontend scaffold

---

## Package Structure

| Option | Description | Selected |
|--------|-------------|----------|
| Domain sub-packages | trumptrade/ingestion/, trumptrade/analysis/, etc. | ✓ |
| Flat top-level modules | trumptrade/poller.py, trumptrade/analyzer.py, etc. | |
| Monolithic with service classes | trumptrade/services/ with one class per concern | |

**User's choice:** Domain sub-packages
**Notes:** All sub-packages stubbed in Phase 1 with empty `__init__.py`. Shared utilities in `trumptrade/core/`.

| Option | Description | Selected |
|--------|-------------|----------|
| python -m trumptrade | Standard module entry point | ✓ |
| uvicorn trumptrade.main:app | Direct uvicorn invocation | |
| Docker only | Container-only invocation | |

**User's choice:** `python -m trumptrade`

| Option | Description | Selected |
|--------|-------------|----------|
| Stub all sub-packages now | Create empty __init__.py for each domain | ✓ |
| Only create what's needed | Add domain modules per phase | |

| Option | Description | Selected |
|--------|-------------|----------|
| trumptrade/core/ | Centralized config/db/logging module | ✓ |
| trumptrade/utils/ | Generic utils folder | |
| Package root | config.py, db.py at root level | |

---

## DB Schema Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Full schema now | All tables in one migration | ✓ |
| Minimal — watchlist + settings only | Each phase adds its tables | |

| Option | Description | Selected |
|--------|-------------|----------|
| Include keyword_rules table | Define in Phase 1 schema | ✓ |
| Phase 4 adds it via migration | Keep Phase 1 schema minimal | |

| Option | Description | Selected |
|--------|-------------|----------|
| shadow_portfolios with NAV snapshots | One row per portfolio per day | ✓ |
| Separate table per benchmark | spy_portfolio, qqq_portfolio, etc. | |
| Derive on-the-fly | No shadow portfolio table | |

| Option | Description | Selected |
|--------|-------------|----------|
| Separate orders + fills tables | Matches Alpaca model, handles partial fills | ✓ |
| Single trades table | Combined order + fill row | |

---

## Settings Model

| Option | Description | Selected |
|--------|-------------|----------|
| .env = secrets only | Everything else in DB | ✓ |
| .env = secrets + trading_mode | Mode change requires restart | |
| .env = everything | All config in .env | |

**User's choice:** Secrets only in .env — risk params, thresholds, trading_mode in DB

| Option | Description | Selected |
|--------|-------------|----------|
| Seed safe defaults at migration | App works without manual config | ✓ |
| Require explicit config before running | More intentional, more friction | |

**Seeded defaults:** position_size=2%, stop_loss=5%, max_daily_loss=10%, confidence_threshold=0.7, trading_mode=paper, bot_enabled=false

**Secrets selected for .env:** ALPACA_API_KEY, ALPACA_SECRET_KEY, X_API_KEY, X_API_SECRET, X_BEARER_TOKEN, OPENAI/ANTHROPIC API key, TRUTH_SOCIAL_ACCOUNT_ID

---

## Frontend Scaffold

| Option | Description | Selected |
|--------|-------------|----------|
| Scaffold in Phase 1 | Vite + React 18 + shadcn/ui + TanStack Query | ✓ |
| Leave to Phase 6 | Pure Python in Phase 1 | |

| Option | Description | Selected |
|--------|-------------|----------|
| frontend/ at project root | Standard monorepo layout | ✓ |
| trumptrade/static/ or trumptrade/frontend/ | Nested inside Python package | |

## Deferred Ideas

- Docker/docker-compose — not needed for personal tool
- APScheduler job definitions — Phase 3 defines polling jobs
- FastAPI route definitions beyond health check
