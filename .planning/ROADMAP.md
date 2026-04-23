# Roadmap: TrumpTrade

## Overview

TrumpTrade is built as a linear event-driven pipeline. The seven phases follow a strict dependency order: project foundation first, then the executor that money flows through, then the ingestion sources feeding it, then the brain that interprets posts, then the risk chokepoint that guards capital, then the dashboard that exposes everything, and finally the benchmarks and live trading that make the system accountable. Each phase delivers a coherent, independently verifiable capability before the next phase builds on it.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundation** - Project scaffolding, environment config, DB schema, migrations, and watchlist settings
- [x] **Phase 2: Alpaca Executor** - Paper trading with bracket stop-loss orders and kill-switch endpoint
- [x] **Phase 3: Ingestion Pipeline** - X/Twitter + Truth Social pollers, SHA-256 dedup, heartbeat alert
- [x] **Phase 4: LLM Analysis Engine** - Signal classification, keyword rule overlay, confidence gate, audit trail
- [x] **Phase 5: Risk Guard + Integration** - asyncio.Queue chokepoint, position sizing, daily loss cap, market hours, full pipeline wired end-to-end
- [x] **Phase 6: Web Dashboard** - Live post feed, trade log, portfolio view, bot kill switch, settings UI
- [ ] **Phase 7: Benchmarks + Live Trading** - SPY/QQQ/random shadow portfolios, comparison chart, two-step live trading unlock
- [ ] **Phase 8: Deployment** - Oracle Cloud Free Tier, systemd service, Nginx reverse proxy, persistent SQLite, SSH management

## Phase Details

### Phase 1: Foundation
**Goal**: The project runs, configuration is validated at startup, the database schema exists, and the watchlist is configurable
**Depends on**: Nothing (first phase)
**Requirements**: SETT-01
**Success Criteria** (what must be TRUE):
  1. Running `python -m trumptrade` starts a FastAPI server without errors and logs validated config values from `.env`
  2. Running Alembic migrations against a fresh SQLite file creates all tables with correct schema
  3. The watchlist can be populated and queried from the database — tickers added persist across restarts
  4. Secrets (API keys, tokens) are absent from all tracked files and the `.gitignore` protects `.env`
**Plans**: 5 plans
Plans:
- [x] 01-PLAN-01.md — Python package scaffold (pyproject.toml, core/ modules, domain stubs)
- [x] 01-PLAN-02.md — Frontend scaffold (Vite + React 19 + shadcn/ui + TanStack Query v5)
- [x] 01-PLAN-03.md — SQLAlchemy models (all 8 tables) + async DB session factory
- [x] 01-PLAN-04.md — Alembic async migrations + app_settings seed defaults
- [x] 01-PLAN-05.md — FastAPI app + APScheduler lifespan + entry point wiring

### Phase 2: Alpaca Executor
**Goal**: The system can place, fill, and confirm paper trades with atomic bracket stop-loss orders using stub signals
**Depends on**: Phase 1
**Requirements**: TRADE-01, TRADE-03
**Success Criteria** (what must be TRUE):
  1. Injecting a stub BUY signal causes the executor to place a bracket order on the Alpaca paper environment and log a confirmed order ID
  2. The placed bracket order contains an attached stop-loss at the correct calculated percentage from fill price — never submitted as a separate order
  3. The system runs in paper mode by default; switching to live mode requires an explicit config change (`TRADING_MODE=live`)
  4. A kill-switch endpoint halts trade execution immediately when called
**Plans**: 2 plans
Plans:
- [x] 02-01-PLAN.md — pytz dependency + AlpacaExecutor service class (executor.py)
- [x] 02-02-PLAN.md — Trading router (/execute, /kill-switch) + __init__ export + app.py wiring

### Phase 3: Ingestion Pipeline
**Goal**: New Trump posts from both platforms flow into a deduplicated store with alerting for scraper failures
**Depends on**: Phase 2
**Requirements**: INGEST-01, INGEST-02, INGEST-03, INGEST-04
**Success Criteria** (what must be TRUE):
  1. New posts from Trump's X/Twitter account appear in the database within one polling interval; rate-limit budget is tracked and logged
  2. New posts from Trump's Truth Social profile appear in the database within one polling interval; a heartbeat alert fires if zero posts are seen during a daytime window
  3. A post published on both platforms is stored exactly once — the second arrival is discarded via SHA-256 hash comparison
  4. Short posts, pure reposts, and posts with no financial keywords are marked as filtered and never forwarded to analysis
**Plans**: 4 plans
Plans:
- [x] 03-01-PLAN.md — filters.py (pre-filter logic) + heartbeat.py (silence alert)
- [x] 03-02-PLAN.md — truth_social.py (httpx poller, HTML strip, cursor, SAVEPOINT dedup) + config.py patch
- [x] 03-03-PLAN.md — twitter.py (tweepy in executor, rate-limit budget, SAVEPOINT dedup)
- [x] 03-04-PLAN.md — ingestion/__init__.py (register_ingestion_jobs) + app.py wiring

### Phase 4: LLM Analysis Engine
**Goal**: Every qualifying post produces a structured signal with sentiment, confidence, and affected tickers — all audited
**Depends on**: Phase 3
**Requirements**: ANLYS-01, ANLYS-02, ANLYS-03, ANLYS-04
**Success Criteria** (what must be TRUE):
  1. A qualifying post produces a structured LLM output with `BULLISH`/`BEARISH`/`NEUTRAL` sentiment, a confidence float, and a list of affected watchlist tickers only
  2. Keyword rules can override or supplement LLM output — a post containing "tariffs" applies the configured keyword action regardless of LLM sentiment
  3. Signals below the 0.7 confidence threshold are logged with reason code `BELOW_THRESHOLD` and never forwarded to the executor
  4. Every signal has a complete audit record: raw LLM prompt, raw LLM response, keyword matches, final action, and reason code — queryable from the database
**Plans**: 3 plans
Plans:
- [x] 04-01-PLAN.md — BaseAdapter + SignalResult + AnthropicAdapter + GroqAdapter + dispatcher + config patch + Alembic migration 004
- [x] 04-02-PLAN.md — analysis_worker() with anti-join query, keyword overlay, confidence gate, Signal insert
- [x] 04-03-PLAN.md — analysis/__init__.py (register_analysis_jobs) + app.py wiring

### Phase 5: Risk Guard + Integration
**Goal**: Signals flow through a single risk chokepoint before reaching the executor, with capital protected by position sizing, daily loss cap, and market hours enforcement
**Depends on**: Phase 4
**Requirements**: TRADE-04, RISK-01, RISK-02, RISK-03, SETT-02
**Success Criteria** (what must be TRUE):
  1. A signal arriving outside market hours or older than the configured staleness threshold is discarded with reason code `STALE` or `MARKET_CLOSED` — no order is placed
  2. Position size per trade respects the configured risk level (low/medium/high) as a percentage of live Alpaca portfolio value
  3. When cumulative daily losses reach the configured max daily loss cap (read from live Alpaca account), all subsequent signals are blocked until the next trading day
  4. End-to-end: a real Trump post on either platform flows through ingestion → analysis → risk guard → paper trade execution with the full audit chain intact
  5. User can update position size %, stop-loss %, and daily loss cap from a settings endpoint and changes take effect on the next signal
**Plans**: 3 plans
Plans:
- [x] 05-01-PLAN.md — risk_guard package scaffold (guard.py, __init__.py) + Alembic migration 005
- [x] 05-02-PLAN.md — Patch analysis_worker.py (enqueue) + executor.py (signal_id) + app.py (lifespan wiring)
- [x] 05-03-PLAN.md — risk_guard/router.py (GET/PATCH /settings/risk) + end-to-end human verify

### Phase 6: Web Dashboard
**Goal**: Users can monitor the full pipeline, review all trades, see live portfolio state, and control the bot from a browser
**Depends on**: Phase 5
**Requirements**: DASH-01, DASH-02, DASH-03, DASH-04
**Success Criteria** (what must be TRUE):
  1. The dashboard displays incoming Trump posts in real time with their LLM sentiment and confidence overlaid, pushed via WebSocket without page refresh
  2. The trade log shows the full audit chain per trade: post → signal → order → fill with all audit fields visible
  3. The portfolio view reads live positions and P&L directly from the Alpaca API — not from the bot's internal state
  4. A kill-switch toggle on the dashboard stops all trade execution immediately; an alert panel surfaces scraper failures and API errors as they occur
  5. Watchlist and risk settings (position size %, stop-loss %, max daily loss cap) are editable from the dashboard settings panel
**Plans**: 5 plans
Plans:
- [x] 06-01-PLAN.md — Dashboard package scaffold (ws.py, watchlist.py, __init__.py) + CORS + app.py wiring + worker.py broadcast patch
- [x] 06-02-PLAN.md — Data read endpoints (GET /posts, GET /trades, GET /portfolio, GET /alerts)
- [x] 06-03-PLAN.md — React Router v6 shell (router, AppShell, KillSwitchBtn, AlertPanel, api.ts, usePostFeed, page stubs)
- [x] 06-04-PLAN.md — FeedPage + PostCard (WebSocket push + initial load)
- [x] 06-05-PLAN.md — TradesPage + PortfolioPage + SettingsPage

### Phase 7: Benchmarks + Live Trading
**Goal**: Users can measure whether the bot beats the market and optionally unlock live trading with real money
**Depends on**: Phase 6
**Requirements**: TRADE-02, COMP-01, COMP-02, COMP-03, COMP-04
**Success Criteria** (what must be TRUE):
  1. A SPY shadow portfolio and a QQQ shadow portfolio each track NAV math from bot start date — no Alpaca orders placed, pure calculation
  2. A random-trade baseline shadow portfolio executes random buy/sell decisions on watchlist tickers over the same period
  3. The dashboard comparison chart shows bot performance vs. SPY, QQQ, and random baseline on the same time axis
  4. Switching to live trading mode requires explicit two-step confirmation from the dashboard; the UI shows a persistent `LIVE` mode indicator when active; switching back to paper requires the same confirmation
**Plans**: 4 plans
Plans:
- [ ] 07-01-PLAN.md — Alembic migration 006 (unique index) + benchmarks/__init__.py + benchmarks/job.py (CronTrigger snapshot job)
- [ ] 07-02-PLAN.md — benchmarks/router.py (GET /benchmarks) + trading/router.py patch (POST /set-mode) + core/app.py wiring
- [ ] 07-03-PLAN.md — npm deps + api.ts patch + router.tsx + BenchmarksPage.tsx (Recharts LineChart)
- [ ] 07-04-PLAN.md — LiveModeModal.tsx + AppShell patches + SettingsPage Trading Mode section + human verify

### Phase 8: Deployment
**Goal**: The app runs continuously on a cloud VM with no PC dependency, auto-restarts on crash, and is manageable over SSH
**Depends on**: Phase 7
**Requirements**: (operational, no code requirements)
**Success Criteria** (what must be TRUE):
  1. App runs as a `systemd` service on Oracle Cloud Free Tier (or equivalent VPS); survives reboots automatically
  2. SQLite database persists on the VM's block storage; no data loss on restart
  3. `.env` secrets are stored securely on the VM and absent from version control
  4. Deployment checklist covers: OS setup, Python env, clone + install, `.env` population, `systemd` unit file, `journalctl` log access, and Nginx reverse proxy for the dashboard
  5. Dashboard is reachable from a browser without port-forwarding or an SSH tunnel
**Plans**: 1 plan
Plans:
- [ ] 08-01-PLAN.md — systemd service + Nginx reverse proxy + Oracle Cloud Free Tier setup checklist

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 5/5 | Complete | 2026-04-19 |
| 2. Alpaca Executor | 2/2 | Complete | 2026-04-20 |
| 3. Ingestion Pipeline | 4/4 | Complete | 2026-04-21 |
| 4. LLM Analysis Engine | 3/3 | Complete | 2026-04-21 |
| 5. Risk Guard + Integration | 3/3 | Complete | 2026-04-21 |
| 6. Web Dashboard | 5/5 | Complete | 2026-04-21 |
| 7. Benchmarks + Live Trading | 0/4 | Not started | - |
| 8. Deployment | 0/1 | Not started | - |
