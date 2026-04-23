# Phase 7: Benchmarks + Live Trading - Context

**Gathered:** 2026-04-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Add three shadow portfolios (SPY, QQQ, random-trade baseline) that track NAV math from bot
first run — no real Alpaca orders. Add a comparison chart to the dashboard showing bot % return
vs all three benchmarks since bot start. Add a two-step live trading unlock that lets the user
switch from paper to live mode with explicit typed confirmation.

</domain>

<decisions>
## Implementation Decisions

### Comparison Chart
- **D-01:** Y-axis shows **% return from start** — all lines begin at 0% on the first snapshot
  date, showing cumulative return over time. Makes comparison fair regardless of starting NAV.
- **D-02:** Time range is **since bot start** (from first snapshot date) — full history always
  visible. No user-selectable range needed for v1.
- **D-03:** All **4 lines** on one chart: Bot, SPY, QQQ, Random. Distinct colors, legend below
  the chart. Use Recharts (already a candidate in the React stack) for consistency with the
  existing shadcn/ui theme.
- **D-04:** Chart lives on a new **Benchmarks page** (or tab) in the dashboard sidebar. One
  additional nav item.

### Shadow Portfolio Mechanics
- **D-05:** Shadow portfolios start accumulating from **first app run** — no historical backfill.
  The `ShadowPortfolioSnapshot` model already exists in `models.py` (Table 7). Use it as-is.
- **D-06:** NAV updated **daily at market close (4pm ET)** via an APScheduler job. One snapshot
  row per portfolio per trading day. The three portfolios are: `SPY`, `QQQ`, `random`.
- **D-07:** SPY and QQQ shadow portfolios use **Alpaca market data** (historical bars API —
  available free with an Alpaca account) to get daily closing prices. NAV math: `(today_price /
  start_price) * 100` normalized to the same starting NAV.
- **D-08:** Random baseline: on each trading day at market close, randomly buy or sell one
  watchlist ticker (50/50 buy/sell, randomly selected ticker). Position sizing mirrors the bot's
  `max_position_size_pct` setting. If watchlist is empty, skip that day (no random trade).

### Live Trading Unlock UX
- **D-09:** Switching to live mode requires **typing a confirmation phrase + clicking Confirm**
  in a modal. Phrase: `ENABLE LIVE TRADING`. Prevents accidental activation.
- **D-10:** Switching back to paper mode requires the **same typed confirmation** (`ENABLE PAPER
  TRADING`). Both directions are equally deliberate.
- **D-11:** When live mode is active, show a **persistent red LIVE badge** in the sidebar
  (replacing/augmenting the PAPER badge) AND a **red banner** at the top of every page.
  Cannot be missed.
- **D-12:** The mode switch calls the existing `POST /trading/kill-switch` pattern — add a new
  `POST /trading/set-mode` endpoint (or extend kill-switch) that writes `trading_mode` to
  `app_settings`. The existing `trading_mode` setting is already read by the risk guard and
  executor.

### Claude's Discretion
- Recharts line chart styling (colors, dot size, tooltip format, grid lines)
- Exact random baseline algorithm tie-breaking (e.g. if watchlist has 1 ticker, always that ticker)
- Chart loading skeleton while data fetches
- Empty state when no snapshot data exists yet (first day)
- Whether the Benchmarks page is a sidebar nav item or a tab within PortfolioPage

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing schema
- `trumptrade/core/models.py` — `ShadowPortfolioSnapshot` (Table 7, line ~159): `portfolio_name`,
  `snapshot_date`, `nav_value`, `cash`, `positions_json` fields. Already migrated.

### Existing settings infrastructure
- `trumptrade/risk_guard/router.py` — GET/PATCH `/settings/risk` pattern to replicate for mode
  toggle endpoint
- `trumptrade/trading/router.py` — Existing kill-switch + status endpoints; `trading_mode` is
  read from `app_settings`

### Frontend patterns (Phase 6 decisions)
- `.planning/phases/06-web-dashboard/06-CONTEXT.md` — Sidebar nav pattern (D-01), Settings page
  chip pattern (D-11), shadcn/ui + dark theme conventions

### Requirements
- `.planning/REQUIREMENTS.md` — COMP-01, COMP-02, COMP-03, COMP-04 (shadow portfolios + chart),
  TRADE-02 (live trading two-step unlock)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ShadowPortfolioSnapshot` model: already created in Phase 1 DB schema — no new migration needed
- `AppSettings` read/write pattern: used throughout `risk_guard/router.py` and `dashboard/router.py`
  for reading/writing settings via `select(AppSettings.value).where(AppSettings.key == key)`
- APScheduler job registration: `trumptrade/ingestion/__init__.py` and `analysis/__init__.py`
  show the pattern for registering interval jobs via `scheduler.add_job()`
- Kill-switch endpoint: `trumptrade/trading/router.py` — model for the mode-switch endpoint

### Established Patterns
- Daily at-close job: needs `CronTrigger(hour=16, minute=1, timezone='US/Eastern')` (market
  closes 4pm ET; 16:01 gives prices time to settle)
- `run_in_executor` for sync Alpaca calls: established in `dashboard/router.py` get_portfolio
- `_read_setting` / `_set_setting` helpers: available in `truth_social.py`, `dashboard/router.py`

### Integration Points
- New `benchmarks/` package or module within `trumptrade/` — registers snapshot job, exposes
  `GET /benchmarks` REST endpoint returning daily snapshots for all 3 portfolios
- New `BenchmarksPage` React component — new sidebar nav item; fetches `/benchmarks` on mount
- Mode-switch modal: new component in frontend, calls new `POST /trading/set-mode` endpoint

</code_context>

<specifics>
## Specific Ideas

- The chart Y-axis label: "Return since start (%)" with a reference line at 0%
- LIVE badge color: red (`text-red-500` / `bg-red-500/10`) consistent with destructive actions in shadcn/ui
- Confirmation phrase is exact string match (case-sensitive): `ENABLE LIVE TRADING` / `ENABLE PAPER TRADING`

</specifics>

<deferred>
## Deferred Ideas

- User-selectable chart date range (1W / 1M / All buttons) — not needed for v1, easy to add later
- Historical backfill from a user-set start date — deferred; start-from-first-run is simpler
- Random baseline configuration (frequency, sizing) exposed in Settings UI — Claude decides defaults
- Congress member trade tracking — separate milestone per PROJECT.md Out of Scope

</deferred>

---

*Phase: 07-benchmarks-live-trading*
*Context gathered: 2026-04-23*
