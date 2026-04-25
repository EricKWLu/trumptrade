---
phase: 07-benchmarks-live-trading
verified: 2026-04-23T21:00:00Z
status: human_needed
score: 4/4 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Switch to LIVE trading mode via Settings > Trading Mode"
    expected: "Modal opens with 'ENABLE LIVE TRADING' phrase, Confirm button disabled until exact phrase typed, red LIVE banner appears on all pages after confirmation, sidebar badge turns red LIVE"
    why_human: "Visual rendering and interactive typed-confirmation flow cannot be verified programmatically. 07-04 human checkpoint was auto-approved in auto mode — no human has confirmed the UI end-to-end."
  - test: "Switch back to PAPER trading mode from LIVE"
    expected: "Modal shows 'ENABLE PAPER TRADING' phrase, Keep LIVE mode dismiss button, LIVE banner disappears after confirmation, badge returns to yellow PAPER"
    why_human: "Requires live state toggle and visual inspection of banner disappearance across page navigations."
  - test: "Navigate to /benchmarks in the sidebar"
    expected: "Benchmarks nav item with LineChart icon appears between Portfolio and Settings, clicking it loads BenchmarksPage showing 'No benchmark data yet' empty state"
    why_human: "Sidebar rendering and navigation requires a running browser session."
---

# Phase 7: Benchmarks + Live Trading Verification Report

**Phase Goal:** Users can measure whether the bot beats the market and optionally unlock live trading with real money
**Verified:** 2026-04-23T21:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A SPY shadow portfolio and a QQQ shadow portfolio each track NAV math from bot start date — no Alpaca orders placed, pure calculation | VERIFIED | `job.py`: `_compute_index_nav()` computes NAV as qty * today_close; writes `portfolio_name="spy"` and `portfolio_name="qqq"` rows to `shadow_portfolio_snapshots`. `StockHistoricalDataClient.get_stock_bars()` fetched via `run_in_executor` (non-blocking). No Alpaca trading calls for shadow portfolios. |
| 2 | A random-trade baseline shadow portfolio executes random buy/sell decisions on watchlist tickers over the same period | VERIFIED | `job.py`: `_simulate_random_trade()` reads watchlist, uses `random.choice()` and `random.random()` to pick ticker and direction, computes buy/sell qty, carries state via `positions_json["cash"]` across days. Writes `portfolio_name="random"` row. |
| 3 | The dashboard comparison chart shows bot performance vs. SPY, QQQ, and random baseline on the same time axis | VERIFIED | `BenchmarksPage.tsx` renders 4-series Recharts `LineChart` (bot #3b82f6, SPY #22c55e, QQQ #a855f7, random #f59e0b) on shared X-axis (date). Y-axis shows normalized % return from start. `api.benchmarks()` calls `GET /benchmarks` which pivots and normalizes all 4 series. Route `/benchmarks` wired in `router.tsx`. |
| 4 | Switching to live trading mode requires explicit two-step confirmation from the dashboard; the UI shows a persistent LIVE mode indicator when active; switching back to paper requires the same confirmation | VERIFIED (code) / NEEDS HUMAN (UI) | `LiveModeModal.tsx`: exact case-sensitive phrase match (`input === targetPhrase`), Confirm `disabled={!isMatch}`, destructive variant for paper→live. `AppShell.tsx`: conditional LIVE banner at top of main when `mode === "live"`. `SettingsPage.tsx`: Trading Mode card with switch button and LiveModeModal. `POST /trading/set-mode` validates mode and confirmed=True, returns 422 otherwise. Human checkpoint required for end-to-end visual verification (07-04 auto-approved in auto mode). |

**Score:** 4/4 truths verified (1 requires human UI confirmation)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `alembic/versions/006_benchmark_unique.py` | Unique index on shadow_portfolio_snapshots(portfolio_name, snapshot_date) | VERIFIED | File exists; `CREATE UNIQUE INDEX IF NOT EXISTS ix_shadow_portfolio_unique` present; `alembic current` shows `006 (head)`; SQLite confirms index exists: `('ix_shadow_portfolio_unique',)` |
| `trumptrade/benchmarks/__init__.py` | `register_benchmark_jobs()` function exported | VERIFIED | File exists; exports `register_benchmark_jobs`; uses `CronTrigger(day_of_week="mon-fri", hour=16, minute=1, timezone="US/Eastern")`; `__all__ = ["register_benchmark_jobs"]` |
| `trumptrade/benchmarks/job.py` | `benchmark_snapshot_job()` async coroutine | VERIFIED | File exists; `STARTING_NAV = 100_000.0`; `_already_snapshotted()` idempotency guard; `run_in_executor` used for all sync Alpaca calls (SPY fetch, QQQ fetch, bot equity); writes 4 portfolio rows atomically; holiday skip via None from `_fetch_close_sync` |
| `trumptrade/benchmarks/router.py` | `GET /benchmarks` endpoint returning normalized % return series | VERIFIED | File exists; `@router.get("/benchmarks")`; pivots by date via `defaultdict`; normalizes via `(nav / first_nav - 1.0) * 100.0`; returns `{"snapshots": []}` when empty; exports `router` |
| `trumptrade/trading/router.py` | `POST /trading/set-mode` endpoint with two-gate validation | VERIFIED | `SetModeRequest`/`SetModeResponse` Pydantic models present; `set_trading_mode` validates `body.mode not in ("paper", "live")` → 422 and `not body.confirmed` → 422; writes to `app_settings` via `update(AppSettings)`; logs mode change |
| `trumptrade/core/app.py` | Benchmarks router included, `register_benchmark_jobs()` called | VERIFIED | Lines 121-126: `register_benchmark_jobs(scheduler)` and `app.include_router(benchmarks_router, tags=["benchmarks"])`; confirmed by `create_app()` test: routes include `/benchmarks` and `/trading/set-mode` |
| `frontend/src/lib/api.ts` | `BenchmarkPoint`, `SetModeResponse` types; `benchmarks()`, `setMode()` methods | VERIFIED | `BenchmarkPoint` interface with nullable bot/spy/qqq/random fields; `SetModeResponse` interface; `api.benchmarks()` unwraps `r.snapshots`; `api.setMode()` posts `{mode, confirmed: true}` |
| `frontend/src/router.tsx` | `/benchmarks` route mapping to `BenchmarksPage` | VERIFIED | `import BenchmarksPage`; `{ path: "benchmarks", element: <BenchmarksPage /> }` between portfolio and settings routes |
| `frontend/src/pages/BenchmarksPage.tsx` | BenchmarksPage with Recharts LineChart, 4 series, loading/empty/error states | VERIFIED | All 4 `<Line>` components with correct stroke colors; `<Legend verticalAlign="bottom">`; `<ReferenceLine y={0} strokeDasharray="4 4">`; Y-axis label "Return since start (%)"; empty state "No benchmark data yet"; loading skeletons; error Alert; `isPending`/`isError` states handled |
| `frontend/src/components/LiveModeModal.tsx` | Two-direction typed confirmation modal | VERIFIED | `LIVE_PHRASE = "ENABLE LIVE TRADING"` and `PAPER_PHRASE = "ENABLE PAPER TRADING"` constants; `isMatch = input === targetPhrase`; `disabled={!isMatch || modeMutation.isPending}`; `variant="destructive"` for paper→live; `variant="default"` for live→paper; "Keep PAPER mode" / "Keep LIVE mode" dismiss buttons; "Failed to switch mode. Try again." error; `queryClient.invalidateQueries({ queryKey: ["portfolio-mode"] })` on success |
| `frontend/src/components/AppShell.tsx` | Benchmarks nav item with LineChart icon, LIVE banner | VERIFIED | `import { ..., LineChart } from "lucide-react"`; `{ to: "/benchmarks", end: false, icon: LineChart, label: "Benchmarks" }` between Portfolio and Settings in `NAV_ITEMS`; `{mode === "live" && <div className="bg-red-500/10 ...">LIVE TRADING ACTIVE — real money at risk</div>}` before `<Outlet />` |
| `frontend/src/pages/SettingsPage.tsx` | Trading Mode section with LiveModeModal | VERIFIED | `import { LiveModeModal } from "@/components/LiveModeModal"`; `TradingModeSection` function component with `useQuery(["portfolio-mode"])`; PAPER/LIVE badge; switch button; `<LiveModeModal isLive={mode === "live"} open={modalOpen} onClose={...} />`; section rendered as third card in `SettingsPage` |
| `frontend/src/components/ui/dialog.tsx` | shadcn Dialog component | VERIFIED | Exists; uses `@base-ui/react/dialog` (this project's shadcn uses base-ui, not radix — consistent with existing codebase). Exports `Dialog`, `DialogContent`, `DialogHeader`, `DialogTitle`, `DialogFooter`. API compatible with LiveModeModal usage (`open`/`onOpenChange` props supported by `DialogRoot.Props`). |
| `frontend/package.json` | recharts and react-is installed | VERIFIED | `"recharts": "^3.8.1"` and `"react-is": "^19.2.5"` in dependencies |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `benchmarks/__init__.py` | `benchmarks/job.py` | `from trumptrade.benchmarks.job import benchmark_snapshot_job` | WIRED | Import present on line 7; `register_benchmark_jobs()` passes `benchmark_snapshot_job` to `scheduler.add_job()` |
| `core/app.py` | `benchmarks/router.py` | `app.include_router(benchmarks_router)` | WIRED | Lines 124-126; confirmed by `create_app()` test showing `/benchmarks` in routes |
| `core/app.py` | `benchmarks/__init__.py` | `register_benchmark_jobs(scheduler)` | WIRED | Lines 121-122; confirmed by `create_app()` test |
| `benchmarks/router.py` | `shadow_portfolio_snapshots` | `select(ShadowPortfolioSnapshot)` | WIRED | Lines 38-45; queries all rows, pivots by date, normalizes |
| `benchmarks/job.py` | `StockHistoricalDataClient` | `loop.run_in_executor(None, _fetch_close_sync, ...)` | WIRED | Lines 522-528, 534-541; SPY and QQQ fetches both use `run_in_executor` |
| `benchmarks/job.py` | `shadow_portfolio_snapshots` | `session.add(ShadowPortfolioSnapshot(...))` | WIRED | Lines 591-619; writes all 4 portfolio rows in single session |
| `frontend/BenchmarksPage.tsx` | `frontend/lib/api.ts` | `api.benchmarks()` | WIRED | Line 132: `queryFn: () => api.benchmarks()` |
| `frontend/router.tsx` | `frontend/BenchmarksPage.tsx` | `import BenchmarksPage` | WIRED | Line 7 import; line 17 route element |
| `frontend/LiveModeModal.tsx` | `frontend/lib/api.ts` | `api.setMode(targetMode)` | WIRED | Line 33: `mutationFn: () => api.setMode(targetMode)` |
| `frontend/SettingsPage.tsx` | `frontend/LiveModeModal.tsx` | `import { LiveModeModal }` | WIRED | Line 3 import; lines 263-267 JSX usage |
| `frontend/AppShell.tsx` | `lucide-react` | `import { ..., LineChart }` | WIRED | Line 2; used in `NAV_ITEMS` array line 15 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `BenchmarksPage.tsx` | `data` (BenchmarkPoint[]) | `api.benchmarks()` → `GET /benchmarks` → `select(ShadowPortfolioSnapshot)` from SQLite | Yes — queries real DB rows, normalizes to % return | FLOWING |
| `AppShell.tsx` (LIVE banner) | `mode` | `useQuery(["portfolio-mode"])` → `api.portfolio()` → `GET /portfolio` → Alpaca live API | Yes — reads `trading_mode` from AppSettings via Alpaca account call in existing dashboard router | FLOWING |
| `SettingsPage.tsx` (TradingModeSection) | `mode` | Same `["portfolio-mode"]` query via TanStack Query deduplication | Yes — same source as AppShell; single network call | FLOWING |
| `LiveModeModal.tsx` (mutation) | `SetModeResponse` | `api.setMode()` → `POST /trading/set-mode` → `update(AppSettings)` | Yes — writes real `trading_mode` value to `app_settings` table | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Python benchmarks package imports | `python -c "from trumptrade.benchmarks import register_benchmark_jobs; from trumptrade.benchmarks.job import benchmark_snapshot_job; print('imports OK')"` | `imports OK` | PASS |
| App starts and exposes /benchmarks route | `python -c "from trumptrade.core.app import create_app; app = create_app(); routes = [r.path for r in app.routes]; assert '/benchmarks' in routes and '/trading/set-mode' in routes"` | Both routes present | PASS |
| Alembic at head (006) | `alembic current` | `006 (head)` | PASS |
| Unique index exists in SQLite | `sqlite3 trumptrade.db "SELECT name FROM sqlite_master WHERE type='index' AND name='ix_shadow_portfolio_unique'"` | `('ix_shadow_portfolio_unique',)` | PASS |
| TypeScript compiles clean | `npx tsc --noEmit --skipLibCheck` (in frontend/) | 0 errors (no output) | PASS |
| Benchmarks router has 1 route | `python -c "from trumptrade.benchmarks.router import router; print(len(router.routes))"` | `1` | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| COMP-01 | 07-01 | System maintains a SPY shadow portfolio (pure NAV math, no Alpaca orders) | SATISFIED | `job.py` `_compute_index_nav("SPY")` writes `portfolio_name="spy"` rows daily; no Alpaca orders placed for shadow portfolios |
| COMP-02 | 07-01 | System maintains a QQQ shadow portfolio (pure NAV math) | SATISFIED | `job.py` `_compute_index_nav("QQQ")` writes `portfolio_name="qqq"` rows daily; pure math, no orders |
| COMP-03 | 07-01 | System maintains a random-trade baseline shadow portfolio | SATISFIED | `job.py` `_simulate_random_trade()` writes `portfolio_name="random"` rows with simulated buys/sells of watchlist tickers |
| COMP-04 | 07-02, 07-03 | User can view a comparison chart showing bot performance vs. SPY, QQQ, and random baseline | SATISFIED | `GET /benchmarks` returns normalized % return series; `BenchmarksPage.tsx` renders 4-series Recharts LineChart at `/benchmarks` route |
| TRADE-02 | 07-02, 07-04 | User can switch to live trading mode via Alpaca after paper pipeline is validated (explicit two-step confirmation required) | SATISFIED (code) / NEEDS HUMAN (UI) | `POST /trading/set-mode` with mode+confirmed validation; `LiveModeModal.tsx` typed phrase confirmation; `SettingsPage` Trading Mode section. Human check needed for UI flow. |

### Anti-Patterns Found

No blockers or warnings detected. Scanned: `benchmarks/__init__.py`, `benchmarks/job.py`, `benchmarks/router.py`, `trading/router.py` (set-mode section), `BenchmarksPage.tsx`, `LiveModeModal.tsx`, `AppShell.tsx`, `SettingsPage.tsx`.

The `placeholder={targetPhrase}` on line 83 of `LiveModeModal.tsx` is an HTML input placeholder attribute — not a code stub.

### Human Verification Required

#### 1. Live Mode Activation Flow

**Test:** Start backend (`python -m trumptrade`) and frontend (`npm run dev`). Navigate to Settings. Click "Switch to LIVE Trading". Type "ENABLE LIVE TRADING" character by character.
**Expected:** Confirm button remains disabled until the full exact phrase is typed (case-sensitive). On click, POST /trading/set-mode is called. A red banner "LIVE TRADING ACTIVE — real money at risk" appears at the top of all pages. The sidebar badge changes from yellow PAPER to red LIVE.
**Why human:** Interactive typed-confirmation flow and visual banner rendering cannot be verified programmatically. The 07-04 human-verify checkpoint was auto-approved in auto mode — no human has confirmed this end-to-end.

#### 2. Paper Mode Return Flow

**Test:** While in LIVE mode, go to Settings > Trading Mode. Click "Switch to PAPER Trading". Type "ENABLE PAPER TRADING".
**Expected:** Modal shows "Keep LIVE mode" dismiss button, "ENABLE PAPER TRADING" phrase, non-destructive Confirm button. After confirmation, LIVE banner disappears from all pages and badge returns to yellow PAPER.
**Why human:** State toggle and cross-page banner persistence requires live browser inspection.

#### 3. Benchmarks Sidebar Navigation

**Test:** Look at the sidebar navigation order.
**Expected:** Feed, Trades, Portfolio, Benchmarks (LineChart icon), Settings — in that order. Clicking Benchmarks navigates to `/benchmarks` and shows the "No benchmark data yet" empty state (since no job has run yet on a live market day).
**Why human:** Visual layout and icon rendering requires browser inspection.

### Gaps Summary

No gaps blocking goal achievement. All 13 required artifacts exist, are substantive, and are wired with real data flowing. All 6 behavioral spot-checks pass. TypeScript compiles with 0 errors.

The `human_needed` status reflects the LIVE banner and typed confirmation UX that must be verified by a human — the 07-04 human checkpoint was bypassed by auto mode. All automated checks pass.

---

_Verified: 2026-04-23T21:00:00Z_
_Verifier: Claude (gsd-verifier)_
