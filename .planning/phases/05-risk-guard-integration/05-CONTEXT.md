# Phase 5: Risk Guard + Integration - Context

**Gathered:** 2026-04-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire the asyncio.Queue risk chokepoint between analysis_worker's Signal output and
AlpacaExecutor — enforcing market hours, position sizing, and daily loss cap before
any order is placed. Deliver a fully end-to-end pipeline: Trump post → ingestion →
analysis → risk guard → paper trade execution, with a settings endpoint for the
three configurable risk controls.

</domain>

<decisions>
## Implementation Decisions

### Signal Dispatch Pipeline

- **D-01:** `analysis_worker` enqueues BUY/SELL signals **directly** onto a module-level
  `asyncio.Queue` after the Signal DB write — no separate polling job needed. Signals
  with `final_action = SKIP` are never enqueued (they're already in the DB for audit).
- **D-02:** Queue capacity: ~100 (handles bursts; blocks producer if backlogged).
- **D-03:** Consumer lives as an `asyncio.create_task()` started in the FastAPI lifespan
  alongside the APScheduler start — not a scheduler job. Consumer loop:
  `await queue.get()` → run risk checks → call `AlpacaExecutor.execute()`.
- **D-04:** If the server restarts, signals already in the queue (not yet executed) are
  lost. This is acceptable — `analysis_worker` will re-analyze any unprocessed posts
  on its next tick (LEFT JOIN anti-join pattern already handles this).
- **D-05:** The queue is instantiated in a new `trumptrade/risk_guard/` module and
  imported by `analysis_worker` (same local-import pattern used across the codebase to
  avoid circular imports).

### Position Sizing

- **D-06:** Position size expressed as a **direct percentage of live portfolio equity**
  (`max_position_size_pct` in `app_settings`). No low/medium/high label mapping.
- **D-07:** LLM confidence is used as a **multiplier** on max position size:
  `trade_dollars = equity × (max_position_size_pct / 100) × confidence`
  `qty = floor(trade_dollars / share_price)`
  At confidence=0.9 with max_pct=3% → uses 2.7% of portfolio.
  At confidence=0.7 (minimum passing gate) → uses 2.1%.
- **D-08:** When a Signal has multiple `affected_tickers`, **one trade per ticker** is
  placed. Position sizing applies independently per ticker (not split across tickers).
- **D-09:** Default `max_position_size_pct`: Claude's discretion (seed in migration —
  suggest 2.0 as a conservative default for a personal paper bot).

### Daily Loss Cap

- **D-10:** Start-of-day baseline: use Alpaca's **`last_equity` field** from
  `trading_client.get_account()`. No snapshot storage, no scheduled job. This field is
  updated by Alpaca at each market close.
- **D-11:** Cap expressed in **dollar amount** (`max_daily_loss_dollars` in
  `app_settings`). Check: `if (last_equity - equity) >= max_daily_loss_dollars: block`.
- **D-12:** When the cap is reached, log reason code `DAILY_CAP_HIT` and block all
  subsequent signals for the rest of the day. The cap resets automatically the next
  day when Alpaca updates `last_equity`.
- **D-13:** Default `max_daily_loss_dollars`: Claude's discretion (suggest 500.0).

### Market Hours + Staleness

- **D-14:** Market hours: NYSE 9:30 AM – 4:00 PM ET. Use `pytz` (already a project
  dependency from Phase 2) with `America/New_York` timezone.
- **D-15:** Staleness threshold: **configurable**, stored in `app_settings` as
  `signal_staleness_minutes`. Default: 5. Stale check compares
  `post.posted_at` (when Trump actually posted) to current time — not when the Signal
  was inserted.
- **D-16:** **After-hours behavior — confidence-gated hold:**
  - Signals with `confidence < 0.85`: discard with `MARKET_CLOSED` reason code.
  - Signals with `confidence >= 0.85`: held in the asyncio.Queue (the queue persists
    in-process while the server is running). At market open (9:30 AM ET), held signals
    are executed oldest-first, one per ticker, with normal position sizing applied.
  - Held signals older than 24 hours are discarded as `STALE` when market opens.
- **D-17:** The hold threshold `0.85` is a hardcoded constant (not configurable) to
  keep settings surface minimal. Can be made configurable in a future phase if needed.

### Settings Endpoint (SETT-02)

- **D-18:** A new FastAPI router `settings_router` exposes:
  - `GET /settings/risk` — returns current values of all risk settings
  - `PATCH /settings/risk` — updates one or more risk settings atomically
  Settings keys exposed: `max_position_size_pct`, `stop_loss_pct` (already in
  app_settings from Phase 2), `max_daily_loss_dollars`, `signal_staleness_minutes`.
- **D-19:** Settings changes take effect on the **next signal** (consumer reads
  app_settings per-cycle, matching the pattern established in Phase 4 analysis_worker).

### Claude's Discretion

- Default seed values for new app_settings keys (max_position_size_pct, max_daily_loss_dollars)
- Exact Pydantic schema for PATCH /settings/risk request/response bodies
- Error handling for AlpacaExecutor failures in the consumer (log + continue, never crash the loop)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Implementation (read before touching)
- `trumptrade/trading/executor.py` — AlpacaExecutor.execute(symbol, side, qty); already reads stop_loss_pct from app_settings; uses run_in_executor for all Alpaca SDK calls
- `trumptrade/analysis/worker.py` — analysis_worker(); produces Signal rows; enqueues to risk_guard after this phase
- `trumptrade/core/app.py` — create_app() wiring pattern; lifespan for starting background tasks
- `trumptrade/core/models.py` — Signal model (final_action, confidence, affected_tickers JSON); AppSettings key-value store

### Established Patterns (must follow)
- `trumptrade/ingestion/__init__.py` — register_*_jobs() pattern for APScheduler wiring
- `trumptrade/analysis/__init__.py` — same pattern; Phase 5 follows this for risk_guard registration
- All Alpaca SDK calls use `asyncio.get_running_loop().run_in_executor(None, partial(...))` — never call sync SDK directly from async context

### Requirements
- `.planning/REQUIREMENTS.md` — TRADE-04, RISK-01, RISK-02, RISK-03, SETT-02
- `.planning/ROADMAP.md` Phase 5 — success criteria SC1-SC5

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `AlpacaExecutor._get_setting(key)` — reads app_settings by key; reuse in risk guard for position sizing and cap checks
- `AlpacaExecutor.execute(symbol, side, qty)` — already handles kill-switch, stop-loss, bracket order, and DB logging; risk guard just needs to call it with the right qty
- `trading_client.get_account()` — returns `equity` and `last_equity`; use for daily cap check; must be wrapped in run_in_executor (sync SDK)
- `pytz` already installed (Phase 2 dependency)

### Established Patterns
- All settings read per-cycle from `app_settings` (never cached at module level) — risk guard must follow this
- Local imports inside `create_app()` to avoid circular imports
- `asyncio.get_running_loop().run_in_executor(None, partial(...))` for every Alpaca SDK call
- Signal rows use `affected_tickers` as a JSON string (e.g. `'["TSLA","AAPL"]'`) — parse with `json.loads()`

### Integration Points
- `analysis_worker()` in `trumptrade/analysis/worker.py` — needs a `queue.put_nowait()` call after Signal DB insert (only for BUY/SELL)
- `create_app()` in `trumptrade/core/app.py` — needs `asyncio.create_task(risk_consumer())` in the lifespan startup block
- New module: `trumptrade/risk_guard/` with `guard.py` (consumer + risk checks), `__init__.py` (exports), `router.py` (settings endpoint)

</code_context>

<specifics>
## Specific Ideas

- User explicitly requested confidence-scaled position sizing: `trade_dollars = equity × max_pct/100 × confidence`. This is a deliberate product decision, not a default.
- User explicitly requested confidence-gated after-hours hold (≥0.85 held, <0.85 discarded). The 0.85 threshold is fixed.
- "One trade per ticker" for multi-ticker signals — not split across tickers.
- Dollar-amount daily loss cap (not percentage) to keep it concrete and easy to reason about.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 05-risk-guard-integration*
*Context gathered: 2026-04-21*
