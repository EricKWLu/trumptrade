# Phase 1: Foundation - Context

**Gathered:** 2026-04-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Set up the project infrastructure that every subsequent phase builds on: Python package structure, FastAPI app skeleton, Pydantic Settings loading from `.env`, full SQLite schema with Alembic migrations, seeded default settings, and a React/Vite frontend scaffold. No business logic — just the floor.

</domain>

<decisions>
## Implementation Decisions

### Package Structure
- **D-01:** Domain sub-packages: `trumptrade/ingestion/`, `trumptrade/analysis/`, `trumptrade/trading/`, `trumptrade/risk/`, `trumptrade/dashboard/` — one module per future phase domain
- **D-02:** Shared utilities in `trumptrade/core/` — holds config loading, DB session factory, logging setup, and the FastAPI app factory
- **D-03:** All domain sub-packages stubbed out in Phase 1 with empty `__init__.py` files — consistent import paths from day one, no renaming later
- **D-04:** Entry point: `python -m trumptrade` starts both FastAPI (via uvicorn) and APScheduler in a single process

### DB Schema Scope
- **D-05:** Full schema defined in Phase 1 — all tables created in a single Alembic migration: `watchlist`, `app_settings`, `posts`, `signals`, `orders`, `fills`, `shadow_portfolio_snapshots`, `keyword_rules`
- **D-06:** `shadow_portfolio_snapshots` table: columns `id`, `portfolio_name` (SPY/QQQ/random), `snapshot_date`, `nav_value`, `cash`, `positions_json` — one row per portfolio per day
- **D-07:** Separate `orders` (submitted to Alpaca) and `fills` (confirmed by Alpaca) tables — matches Alpaca's model, handles partial fills correctly

### Settings Model
- **D-08:** `.env` holds secrets only: `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `X_API_KEY`, `X_API_SECRET`, `X_BEARER_TOKEN`, `OPENAI_API_KEY` (or `ANTHROPIC_API_KEY`), `TRUTH_SOCIAL_ACCOUNT_ID`
- **D-09:** Everything runtime-editable lives in the `app_settings` DB table: position size %, stop-loss %, max daily loss cap, confidence threshold, trading mode, bot enabled flag
- **D-10:** Alembic migration seeds safe defaults: `position_size_pct=2.0`, `stop_loss_pct=5.0`, `max_daily_loss_pct=10.0`, `confidence_threshold=0.7`, `trading_mode=paper`, `bot_enabled=false`

### Frontend Scaffold
- **D-11:** `frontend/` directory at project root (alongside `trumptrade/` Python package) — standard monorepo layout
- **D-12:** Frontend scaffold: Vite + React 18 + shadcn/ui + TanStack Query v5 — just the skeleton, `npm run dev` starts the dev server, no components built yet

### Claude's Discretion
- Exact logging format and level (structured JSON logging preferred for machine-readability, but not locked)
- `pyproject.toml` vs `setup.py` vs `requirements.txt` — use `pyproject.toml` with `[project.scripts]` for the entry point
- Specific SQLAlchemy model field types and constraints beyond what's implied by the schema above

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project context
- `.planning/PROJECT.md` — project vision, constraints, key decisions (especially: use `alpaca-py` not `alpaca-trade-api`, bracket orders only, paper mode default)
- `.planning/REQUIREMENTS.md` — SETT-01 is the only v1 requirement for this phase; traceability table

### Research findings
- `.planning/research/STACK.md` — exact library names, versions, and "what NOT to use" (critical: `httpx` not `requests`, `alpaca-py` not `alpaca-trade-api`)
- `.planning/research/ARCHITECTURE.md` — component boundaries, data flow, how test/live mode is handled (single config enum at executor)
- `.planning/research/SUMMARY.md` — concise corrections to be aware of

### No external ADRs yet — this is the first phase of a greenfield project.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None — greenfield project. Phase 1 creates the foundation.

### Established Patterns
- None yet — Phase 1 establishes the patterns for all future phases.

### Integration Points
- `trumptrade/core/db.py` — SQLAlchemy async session factory, all phases import from here
- `trumptrade/core/config.py` — Pydantic Settings instance, all phases import from here
- `trumptrade/__main__.py` — entry point, starts uvicorn + APScheduler
- `frontend/` — React app, served independently in dev, proxied to FastAPI in production

</code_context>

<specifics>
## Specific Ideas

- No specific UI references — frontend scaffold is just `npx create-vite@latest` + shadcn/ui init
- Bot starts with `bot_enabled=false` seeded in DB — must be explicitly turned on, never auto-starts

</specifics>

<deferred>
## Deferred Ideas

- Docker / docker-compose setup — not needed for a personal tool, can add later if desired
- APScheduler job definitions — Phase 3 (ingestion) defines the actual polling jobs; Phase 1 only wires up the scheduler instance
- FastAPI route definitions beyond health check — Phase-specific routes added in their respective phases

</deferred>

---

*Phase: 01-foundation*
*Context gathered: 2026-04-19*
