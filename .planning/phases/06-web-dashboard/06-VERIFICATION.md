---
phase: 06-web-dashboard
verified: 2026-04-21T00:00:00Z
status: human_needed
score: 10/10 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Open http://localhost:5173 in browser and confirm sidebar renders with Kill Switch button, 4 nav links (Feed, Trades, Portfolio, Settings), Alert panel (when alerts exist), and PAPER/LIVE badge at bottom"
    expected: "Sidebar layout visible, KillSwitchBtn shows 'Stop Bot' or 'Start Bot' based on current bot_enabled DB value, PAPER badge shows in yellow"
    why_human: "Visual rendering and CSS token correctness cannot be verified programmatically; sidebar CSS custom properties (--sidebar, --sidebar-accent) require browser evaluation"
  - test: "With backend running, navigate to / (Feed) and verify that existing posts load on mount and new posts appear at top without page refresh when analysis_worker processes a post"
    expected: "REST initial load shows up to 50 posts; WebSocket pushes prepend new post cards with slide-in animation; reconnecting chip shows amber when backend WS is down"
    why_human: "Real-time WebSocket push requires live backend + ingestion pipeline; cannot simulate in static file check"
  - test: "Click 'Stop Bot' and confirm POST /trading/kill-switch is called and button changes to 'Start Bot'; then click 'Start Bot' and confirm it reverts"
    expected: "Optimistic UI update occurs immediately; server confirms with bot_enabled field; AppSettings DB row updates"
    why_human: "Requires live backend interaction and real DB state change to verify optimistic + reconcile flow"
  - test: "Navigate to /trades, expand a row by clicking it, and verify audit chain: post text, signal details, fill info, and LLM prompt/response are visible in collapsible detail row"
    expected: "Row expands showing AuditDetail with post content, SentimentBadge, confidence %, affected tickers, fill info, and LlmAudit toggle with pre-formatted prompt/response blocks"
    why_human: "UI interaction (click to expand) and visual audit chain layout require browser testing"
  - test: "Navigate to /portfolio and verify 3 summary cards (Total Equity, P&L Today, Buying Power) show live Alpaca data, positions table renders, and page auto-refreshes every 15s"
    expected: "Live Alpaca account data shown; P&L Today uses green for positive, red for negative; page polls every 15s without user action"
    why_human: "Requires live Alpaca paper credentials to verify real data flows; 15s poll observable only in browser"
  - test: "Navigate to /settings, add a ticker (e.g. TSLA), verify chip appears; click X on chip, verify it disappears; change Max Position Size and click Save Changes"
    expected: "POST /watchlist adds ticker and invalidates cache (chip appears); DELETE /watchlist/{symbol} removes it; PATCH /settings/risk shows inline 'Settings saved.' for 3s"
    why_human: "Requires live backend with DB and Alpaca credentials; mutation + cache invalidation behavior requires interactive testing"
---

# Phase 6: Web Dashboard Verification Report

**Phase Goal:** Users can monitor the full pipeline, review all trades, see live portfolio state, and control the bot from a browser
**Verified:** 2026-04-21
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | Dashboard displays incoming Trump posts in real time with LLM sentiment pushed via WebSocket | VERIFIED | `trumptrade/dashboard/ws.py` ConnectionManager + `/ws/feed` endpoint; `analysis/worker.py` broadcasts after `await session.commit()` with type/platform/content/signal JSON; `frontend/src/hooks/usePostFeed.ts` connects to `ws://localhost:8000/ws/feed` with exponential backoff; `FeedPage.tsx` merges WS live posts with REST initial load via `useMemo` |
| 2 | Trade log shows full audit chain: post → signal → order → fill with all audit fields | VERIFIED | `trumptrade/dashboard/router.py` GET /trades uses LEFT OUTER JOINs across Order, Signal, Post, Fill; returns `llm_prompt` and `llm_response`; `TradesPage.tsx` renders `TradeRow` components; `TradeRow.tsx` has `AuditDetail` with post, signal, fill, and `LlmAudit` sub-component with `<pre>` blocks |
| 3 | Portfolio view reads live positions and P&L from Alpaca API, not bot internal state | VERIFIED | `router.py` GET /portfolio instantiates `TradingClient` per-request, uses `asyncio.get_running_loop().run_in_executor(None, client.get_account)` and `run_in_executor(None, client.get_all_positions)`; returns equity, last_equity, pl_today, buying_power, positions[]; `PortfolioPage.tsx` uses `refetchInterval: 15_000` |
| 4 | Kill-switch toggle stops trade execution; alert panel surfaces scraper and API errors | VERIFIED | `trading/router.py` has POST /kill-switch + GET /status; `KillSwitchBtn.tsx` fetches initial state from GET /trading/status, posts to POST /trading/kill-switch with optimistic update; `heartbeat.py` calls `append_alert("heartbeat", ...)` on silence; `guard.py` calls `append_alert("alpaca", ...)` in both `_check_daily_cap` and `_get_equity` except blocks; `AlertPanel.tsx` polls GET /alerts every 10s |
| 5 | Watchlist and risk settings editable from settings panel | VERIFIED | `trumptrade/dashboard/watchlist.py` GET/POST/DELETE /watchlist with `WatchlistAdd(Field(pattern=r"^[A-Z]{1,5}$"))`; `SettingsPage.tsx` has WatchlistSection (ticker chips + add input with `/^[A-Z]{1,5}$/` validation + `invalidateQueries`) and RiskControlsSection (4 numeric fields + PATCH /settings/risk + `invalidateQueries`) |
| 6 | GET /watchlist, GET /posts, GET /trades, GET /portfolio, GET /alerts all exist and return real data | VERIFIED | All 5 endpoints in `trumptrade/dashboard/router.py` with real DB queries (SQLAlchemy) or Alpaca API; no static returns or hardcoded empty values |
| 7 | CORS allows http://localhost:5173 on all endpoints | VERIFIED | `trumptrade/core/app.py` `create_app()` adds `CORSMiddleware` with `allow_origins=["http://localhost:5173"]` immediately after `FastAPI()` construction, before all `include_router` calls |
| 8 | WebSocket feed uses ConnectionManager singleton with dead-connection cleanup | VERIFIED | `trumptrade/dashboard/ws.py` `broadcast()` wraps each `ws.send_text()` in try/except, collects `dead` list, removes after loop — one dead client cannot block others |
| 9 | Frontend builds without TypeScript errors | VERIFIED | SUMMARY-03, SUMMARY-04, SUMMARY-05 all confirm `npm run build` PASSED; Post-04 fix for removed `Twitter` lucide-react export (replaced with `X as XIcon`); Post-05 fix for `asChild` not supported by base-ui Collapsible (state-based conditional rendering used instead) |
| 10 | All phase 6 requirement IDs covered: DASH-01, DASH-02, DASH-03, DASH-04, SETT-01, SETT-02 | VERIFIED | See Requirements Coverage section below |

**Score:** 10/10 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `trumptrade/dashboard/ws.py` | ConnectionManager singleton + /ws/feed | VERIFIED | `class ConnectionManager`, `manager = ConnectionManager()`, `@router.websocket("/ws/feed")`; zero imports from analysis/, risk_guard/, or trading/ |
| `trumptrade/dashboard/watchlist.py` | GET/POST/DELETE /watchlist | VERIFIED | `WatchlistAdd` with `Field(pattern=r"^[A-Z]{1,5}$")`; three route functions; proper 409/404/201/200 status codes |
| `trumptrade/dashboard/router.py` | GET /posts, /trades, /portfolio, /alerts + append_alert | VERIFIED | All 4 routes present; `append_alert(source, message)` and `clear_alerts()` exported; `run_in_executor` on both Alpaca calls; LEFT OUTER JOINs in GET /trades |
| `trumptrade/dashboard/__init__.py` | Exports watchlist_router, ws_router | VERIFIED | `__all__ = ["watchlist_router", "ws_router"]`; correctly does NOT import dashboard_router (created by Plan 02, imported directly by app.py) |
| `trumptrade/core/app.py` | CORSMiddleware + all dashboard routers | VERIFIED | CORSMiddleware with `allow_origins=["http://localhost:5173"]`; `include_router` for `dashboard_router`, `watchlist_router`, `ws_router` |
| `trumptrade/analysis/worker.py` | Broadcasts post+signal after Signal commit | VERIFIED | `from trumptrade.dashboard.ws import manager as _ws_manager` local import inside loop body at line 282; `await _ws_manager.broadcast(...)` with full post+signal JSON |
| `trumptrade/ingestion/heartbeat.py` | Calls append_alert on scraper silence | VERIFIED | Lines 71-72: `from trumptrade.dashboard.router import append_alert` + `append_alert("heartbeat", "No Truth Social posts in last 30 minutes (scraper silence)")` |
| `trumptrade/risk_guard/guard.py` | Calls append_alert on Alpaca APIError | VERIFIED | Lines 131-132 (`_check_daily_cap`) and 144-145 (`_get_equity`): both have `append_alert("alpaca", ...)` in except blocks |
| `trumptrade/trading/router.py` | GET /trading/status returns {bot_enabled: bool} | VERIFIED | `async def trading_status()` reads AppSettings where key=="bot_enabled", returns `{"bot_enabled": val == "true"}` |
| `frontend/src/components/AppShell.tsx` | Sidebar with kill switch + alert panel | VERIFIED | `<KillSwitchBtn />` at sidebar top, `<AlertPanel />` below nav, `<TradingModeBadge />` at bottom, `<Outlet />` in main, 4 NavLink items |
| `frontend/src/components/KillSwitchBtn.tsx` | Reads initial state from GET /trading/status | VERIFIED | `useQuery` with `queryKey: ["trading-status"]`, `queryFn: () => apiFetch("/trading/status")`; optimistic mutation with rollback on error |
| `frontend/src/components/AlertPanel.tsx` | Polls GET /alerts every 10s | VERIFIED | `refetchInterval: 10_000`, `staleTime: 0`; returns null when alerts empty; count badge + ScrollArea |
| `frontend/src/components/PostCard.tsx` | Sentiment badge, filtered-gray, platform icon | VERIFIED | `opacity-40` for filtered, `bg-green-500/10 text-green-400` BULLISH, `bg-red-500/10 text-red-400` BEARISH, `Globe`/`XIcon` platform icons, `animate-in slide-in-from-top-2 fade-in duration-200` for new posts |
| `frontend/src/pages/FeedPage.tsx` | WebSocket push + REST initial load | VERIFIED | `usePostFeed()` for WS, `useQuery(["posts"])` for REST, `useMemo` merge with `liveIds.has(p.id)` dedup, `isPending` (TQ v5), loading skeletons, empty state |
| `frontend/src/pages/TradesPage.tsx` | Expandable rows with LLM audit | VERIFIED | `useQuery(["trades"])`, `TradeRow` components in Table, empty state with "No trades yet" |
| `frontend/src/pages/PortfolioPage.tsx` | 3 summary cards + positions table from Alpaca | VERIFIED | `refetchInterval: 15_000`, 3 Card summary cards (equity, pl_today, buying_power), `<Alert variant="destructive">` on isError, positions table with P&L coloring |
| `frontend/src/pages/SettingsPage.tsx` | Watchlist chips + risk controls form | VERIFIED | WatchlistSection with ticker chips + X button + add input; RiskControlsSection with 4 numeric fields + Save Changes + "Settings saved." feedback; both sections use `invalidateQueries` |
| `frontend/src/hooks/usePostFeed.ts` | WebSocket with exponential backoff | VERIFIED | `new WebSocket("ws://localhost:8000/ws/feed")`, `retryDelayRef.current = delay * 2`, cap at 30s, `unmountedRef` guard for cleanup |
| `frontend/src/lib/api.ts` | Typed fetch wrappers for all endpoints | VERIFIED | `apiFetch<T>()` generic wrapper; `api` object with 10 typed methods; full TypeScript interfaces for all data shapes |
| `frontend/src/router.tsx` | createBrowserRouter with 4 child routes | VERIFIED | `createBrowserRouter`, `index: true` for FeedPage, trades/portfolio/settings paths under AppShell |
| `frontend/src/components/TradeRow.tsx` | Expandable trade row with LLM audit | VERIFIED | State-based conditional rendering (`{open && <TableRow>}`); `CollapsibleContent` present inside detail cell; `LlmAudit` with `<pre className="font-mono">` for prompt and response; `AuditDetail` with post/signal/fill sections |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `analysis/worker.py` | `dashboard/ws.py` | local import of manager singleton | WIRED | Line 282: `from trumptrade.dashboard.ws import manager as _ws_manager`; `await _ws_manager.broadcast(...)` called |
| `core/app.py` | `dashboard/router.py` | local import inside create_app() | WIRED | `from trumptrade.dashboard.router import router as dashboard_router`; `app.include_router(dashboard_router, ...)` |
| `frontend/src/App.tsx` | `frontend/src/router.tsx` | RouterProvider | WIRED | `<RouterProvider router={router} />` |
| `frontend/src/components/AppShell.tsx` | `KillSwitchBtn.tsx` | import and render | WIRED | `import KillSwitchBtn from "./KillSwitchBtn"`; `<KillSwitchBtn />` in sidebar aside |
| `frontend/src/hooks/usePostFeed.ts` | `ws://localhost:8000/ws/feed` | new WebSocket() | WIRED | `new WebSocket("ws://localhost:8000/ws/feed")` |
| `frontend/src/pages/FeedPage.tsx` | `usePostFeed.ts` | hook call | WIRED | `const { posts: livePosts, status } = usePostFeed()` |
| `frontend/src/pages/FeedPage.tsx` | GET /posts | useQuery queryKey ["posts"] | WIRED | `useQuery({ queryKey: ["posts"], queryFn: () => api.posts(50, 0) })` |
| `frontend/src/pages/TradesPage.tsx` | GET /trades | useQuery queryKey ["trades"] | WIRED | `useQuery({ queryKey: ["trades"], queryFn: () => api.trades() })` |
| `frontend/src/pages/PortfolioPage.tsx` | GET /portfolio | refetchInterval: 15_000 | WIRED | `useQuery({ queryKey: ["portfolio"], refetchInterval: 15_000 })` |
| `frontend/src/pages/SettingsPage.tsx` | POST/DELETE /watchlist | useMutation + invalidateQueries | WIRED | `api.addWatchlist(symbol)` and `api.removeWatchlist(symbol)` mutations with `invalidateQueries({ queryKey: ["watchlist"] })` |
| `heartbeat.py` | `dashboard/router.py append_alert` | local import in function body | WIRED | Lines 71-72 confirmed |
| `guard.py` | `dashboard/router.py append_alert` | local import in except blocks | WIRED | Lines 131-132 and 144-145 confirmed |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `FeedPage.tsx` | `restPosts` | GET /posts → `Post` SQLAlchemy query | Yes — `select(Post).order_by(Post.created_at.desc())` | FLOWING |
| `FeedPage.tsx` | `livePosts` | WebSocket → `usePostFeed` → `analysis/worker.py` broadcast | Yes — broadcast fires after `await session.commit()` of real Signal record | FLOWING |
| `TradesPage.tsx` | `trades` | GET /trades → LEFT OUTER JOIN Order+Signal+Post+Fill | Yes — real DB query with outerjoin; includes `llm_prompt`/`llm_response` | FLOWING |
| `PortfolioPage.tsx` | `data` | GET /portfolio → Alpaca `run_in_executor` | Yes — live `client.get_account()` + `client.get_all_positions()` calls | FLOWING |
| `SettingsPage.tsx WatchlistSection` | `watchlist` | GET /watchlist → Watchlist SQLAlchemy query | Yes — `select(Watchlist).order_by(Watchlist.symbol.asc())` | FLOWING |
| `SettingsPage.tsx RiskControlsSection` | `riskSettings` | GET /settings/risk → AppSettings | Yes — existing Phase 5 endpoint reads AppSettings rows | FLOWING |
| `AlertPanel.tsx` | `alerts` | GET /alerts → `_alerts` module-level list | Yes — populated by `append_alert()` calls from heartbeat.py and guard.py | FLOWING |
| `KillSwitchBtn.tsx` | `statusData` | GET /trading/status → AppSettings | Yes — reads `bot_enabled` key from AppSettings DB | FLOWING |

### Behavioral Spot-Checks

Step 7b: SKIPPED for most items — backend requires live Alpaca credentials and SQLite DB with migrations applied. Frontend requires running Vite dev server.

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| ws.py has no forbidden imports | grep analysis/risk_guard/trading in ws.py | No matches found | PASS |
| manager singleton is module-level | grep "^manager = ConnectionManager" in ws.py | Line 46 confirmed | PASS |
| append_alert in heartbeat.py | grep in heartbeat.py | Lines 71-72 confirmed | PASS |
| append_alert in guard.py (2 sites) | grep in guard.py | Lines 131-132, 144-145 confirmed | PASS |
| CORSMiddleware with localhost:5173 | grep in app.py | Lines 88-95 confirmed | PASS |
| run_in_executor in router.py | grep in router.py | Lines 187-188 confirmed | PASS |
| FeedPage uses isPending not isLoading | grep isLoading in FeedPage.tsx | Not present | PASS |
| PortfolioPage refetchInterval 15_000 | grep refetchInterval in PortfolioPage.tsx | Line 134 confirmed | PASS |
| invalidateQueries in SettingsPage | grep invalidateQueries in SettingsPage.tsx | Lines 29, 44, 153 confirmed | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| DASH-01 | 06-01, 06-02, 06-03, 06-04 | Live post feed with LLM analysis via WebSocket | SATISFIED | WS endpoint + worker broadcast + usePostFeed + FeedPage + PostCard all wired |
| DASH-02 | 06-02, 06-03, 06-05 | Full trade log with post→signal→order→fill audit chain | SATISFIED | GET /trades with LEFT OUTER JOINs + TradesPage + TradeRow with LlmAudit |
| DASH-03 | 06-02, 06-03, 06-05 | Portfolio view from live Alpaca API | SATISFIED | GET /portfolio with run_in_executor + PortfolioPage with refetchInterval |
| DASH-04 | 06-01, 06-02, 06-03 | Kill switch toggle + alert panel for scraper/API errors | SATISFIED | GET+POST /trading/status+kill-switch + append_alert in heartbeat+guard + AlertPanel 10s poll |
| SETT-01 | 06-01, 06-03, 06-05 | Add/remove tickers from watchlist | SATISFIED | GET/POST/DELETE /watchlist endpoints + SettingsPage WatchlistSection with chips + add/remove mutations |
| SETT-02 | 06-03, 06-05 | Set risk controls from dashboard | SATISFIED | GET/PATCH /settings/risk (Phase 5 backend) + SettingsPage RiskControlsSection with 4 fields + Save Changes |

**Note on SETT-01 and SETT-02:** REQUIREMENTS.md traceability table maps SETT-01 to Phase 1 (DB schema) and SETT-02 to Phase 5 (backend endpoints). Phase 6 delivers the *UI surfaces* for both — watchlist chip management and risk controls form — which are the user-facing completion of those requirements. All 6 plan-declared requirement IDs are accounted for.

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `frontend/src/components/TradeRow.tsx` | `Collapsible asChild` not supported by base-ui; replaced with state-based conditional rendering + `{open && <TableRow>}` | Info | Documented deviation; expand/collapse behavior is fully functional; `CollapsibleContent` is present inside detail cell for animation within cell bounds |
| `frontend/src/components/PostCard.tsx` | `Twitter` icon removed from lucide-react; replaced with `X as XIcon` | Info | Cosmetic — both icons convey same meaning; documented in SUMMARY-04 |
| `frontend/src/components/TradeRow.tsx` | `XCircle` used as X/Twitter platform icon in AuditDetail | Info | `Twitter` not exported from installed lucide-react version; documented in SUMMARY-05 |

None of the above anti-patterns are blockers — all are documented deviations from plan text that do not affect functionality.

### Human Verification Required

#### 1. Sidebar Layout Visual Rendering

**Test:** Start the backend (`python -m trumptrade`) and the frontend (`cd frontend && npm run dev`). Open http://localhost:5173 in a browser.
**Expected:** Sidebar renders with KillSwitchBtn at top ("Stop Bot" destructive or "Start Bot" green based on DB state), 4 nav links (Feed, Trades, Portfolio, Settings) with active state highlighting, AlertPanel below nav (hidden when no alerts), and PAPER badge in yellow at sidebar bottom. Main area shows FeedPage.
**Why human:** Visual rendering, CSS custom property tokens (`--sidebar`, `--sidebar-accent`, `--primary`), and layout correctness require browser evaluation.

#### 2. WebSocket Live Push in FeedPage

**Test:** With backend running and ingestion pipeline active, wait for analysis_worker to process a post. Observe the FeedPage in the browser.
**Expected:** New post card slides in from the top without page refresh. Post shows platform icon, relative timestamp, sentiment badge, confidence %, and affected ticker chips. If backend WS goes down, amber "Reconnecting to live feed…" chip appears in header.
**Why human:** Requires live ingestion + analysis pipeline processing a real post; real-time behavior cannot be verified statically.

#### 3. Kill Switch Toggle Behavior

**Test:** Click "Stop Bot" button in the sidebar. Verify the button immediately changes to "Start Bot" (optimistic update). Confirm the server returns `bot_enabled: false`. Then click "Start Bot" and verify it reverts.
**Expected:** Optimistic UI update fires immediately on click; server confirms via POST /trading/kill-switch response; AppSettings DB row for `bot_enabled` updates to "false" then "true".
**Why human:** Requires live backend with DB to verify the full optimistic + server reconcile cycle; subsequent trade execution halt also needs live testing.

#### 4. TradesPage Expandable Audit Chain

**Test:** Navigate to /trades (requires at least one order in DB). Click a trade row to expand it.
**Expected:** Row expands to show AuditDetail: post text with platform icon + timestamp, signal section with SentimentBadge/confidence/tickers, fill info if filled, and "Show raw LLM prompt / response" toggle opening `<pre>` blocks with actual prompt/response text.
**Why human:** Requires DB populated with at least one complete trade (order + signal + post + fill); UI interaction (click expand) and audit chain completeness require manual inspection.

#### 5. PortfolioPage Live Data and 15s Refresh

**Test:** Navigate to /portfolio with valid Alpaca paper credentials. Observe 3 summary cards and positions table.
**Expected:** Cards show current equity, P&L Today with green/red coloring (positive/negative), and buying power from live Alpaca account. Positions table shows current open positions with unrealized P&L. Page data refreshes every ~15 seconds automatically.
**Why human:** Requires live Alpaca paper credentials; 15s auto-refresh observable only in running browser session.

#### 6. SettingsPage Watchlist and Risk Controls

**Test:** Navigate to /settings. Add "TSLA" ticker via input + "Add Ticker" button. Verify chip appears. Click X on chip to remove. Change "Max Position Size" value and click "Save Changes".
**Expected:** POST /watchlist adds TSLA chip immediately (cache invalidated); DELETE /watchlist/TSLA removes chip; PATCH /settings/risk succeeds and shows "Settings saved." message for 3 seconds.
**Why human:** Requires live backend with DB; mutation + cache invalidation + inline feedback require interactive browser testing to confirm end-to-end.

### Gaps Summary

No gaps found. All 10 observable truths are verified. All listed artifacts exist, are substantive (not stubs), and are wired to real data sources. Key links traced from browser to DB/Alpaca API for all pages. Anti-patterns found are documented deviations that do not affect goal achievement.

Automated verification is complete. Phase goal is blocked only by items requiring human browser testing to confirm visual rendering, real-time WebSocket behavior, and live Alpaca data flows.

---

_Verified: 2026-04-21_
_Verifier: Claude (gsd-verifier)_
