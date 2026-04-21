# Phase 6: Web Dashboard - Context

**Gathered:** 2026-04-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the React web dashboard that lets the user monitor the full pipeline, review all trades,
see live portfolio state, and control the bot from a browser. All data reads from existing
FastAPI endpoints and a new WebSocket endpoint for the live post feed. No new backend business
logic — this phase wires the UI to the already-built backend.

</domain>

<decisions>
## Implementation Decisions

### Overall Layout
- **D-01:** Sidebar navigation — persistent left sidebar with icon + label for each section.
  Four main sections: Feed, Trades, Portfolio, Settings. These are separate routes (React Router).
- **D-02:** A PAPER/LIVE trading mode badge sits at the bottom of the sidebar, always visible
  regardless of which section is active.
- **D-03:** Portfolio view: summary cards row at top (total equity, P&L today, buying power),
  then a positions table below (symbol, qty, market value, unrealized gain/loss per position).
  Data reads live from Alpaca API — never from bot's internal state.

### Post Feed (DASH-01)
- **D-04:** Post cards show full post text (not truncated), platform icon (Truth Social / X),
  relative timestamp, and a colored sentiment badge (BULLISH/BEARISH/NEUTRAL + confidence %).
  Affected tickers listed below the badge.
- **D-05:** Filtered posts are shown grayed out with the filter reason displayed.
- **D-06:** WebSocket push — new posts auto-insert at the top of the feed without any user action
  or page refresh.

### Trade Log (DASH-02)
- **D-07:** Expandable row table — one row per order (symbol, side, qty, status, submitted time).
  Clicking a row expands to show the full audit chain: linked post content, signal details
  (sentiment, confidence, affected tickers, final action, reason code), order fill price,
  and the raw LLM prompt + response in a collapsible code block.
- **D-08:** Raw LLM prompt and response ARE visible in the expanded audit detail. This is
  intentional — useful for debugging why a signal fired.

### Kill Switch + Alert Panel (DASH-04)
- **D-09:** Kill switch is a prominent button at the top of the sidebar — always visible.
  Red "Stop Bot" when running, green "Start Bot" when stopped. Single click, no confirmation modal.
  Calls `POST /trading/kill-switch`.
- **D-10:** Active errors appear in a persistent alert panel below the sidebar nav. Errors
  persist until resolved (not auto-dismissing toasts). A count badge appears on the sidebar
  when there are active alerts. Surfaced errors include: scraper silence (heartbeat), Alpaca
  API errors from the risk consumer, and LLM failures.

### Settings Panel (SETT-01, SETT-02)
- **D-11:** Dedicated Settings page with two sections:
  1. **Watchlist** — chips showing current tickers with an X to remove, plus a text input
     to add new tickers. Changes submit via `POST/DELETE /watchlist` (new endpoints needed).
  2. **Risk Controls** — editable numeric fields for `max_position_size_pct`, `stop_loss_pct`,
     `max_daily_loss_dollars`, `signal_staleness_minutes`. Single "Save Changes" button submits
     all four via `PATCH /settings/risk`.

### Claude's Discretion
- Exact color palette for BULLISH (green), BEARISH (red), NEUTRAL (gray) badges
- shadcn/ui component choices for each view (Table, Card, Badge, etc.)
- Loading skeleton design while data fetches
- Empty state designs (no posts yet, no trades yet, no positions)
- Exact WebSocket message format and reconnect behavior
- Error boundary handling for Alpaca API failures on the Portfolio page
- How the alert panel clears resolved alerts

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — DASH-01, DASH-02, DASH-03, DASH-04, SETT-01, SETT-02
- `.planning/ROADMAP.md` Phase 6 — success criteria SC1-SC5

### Existing Backend (read before touching)
- `trumptrade/core/app.py` — FastAPI app factory; lifespan wiring pattern; where to add WebSocket route and watchlist router
- `trumptrade/core/models.py` — Post, Signal, Order, Fill, Watchlist, AppSettings ORM models
- `trumptrade/trading/router.py` — `POST /trading/kill-switch` endpoint (already implemented)
- `trumptrade/risk_guard/router.py` — `GET/PATCH /settings/risk` endpoint (already implemented)
- `trumptrade/core/config.py` — Settings (CORS, DB URL, etc.) — may need CORS origins for frontend dev server

### Established Patterns
- `trumptrade/trading/__init__.py` — router export pattern
- `trumptrade/risk_guard/__init__.py` — router export + module-level queue
- `trumptrade/analysis/worker.py` — how Signal rows are written (fields available for trade log)

### Frontend Scaffold
- `frontend/src/App.tsx` — empty scaffold; React 18 + Vite + shadcn/ui + TanStack Query v5 installed
- `frontend/src/components/ui/button.tsx` — shadcn Button component already scaffolded
- `frontend/src/lib/utils.ts` — shadcn cn() utility

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `frontend/src/components/ui/button.tsx` — shadcn Button, already set up
- `frontend/src/lib/utils.ts` — cn() class merge utility
- `trumptrade/risk_guard/router.py` — GET /settings/risk returns all 4 risk fields; PATCH accepts partial updates

### Established Patterns
- Backend: all Alpaca SDK calls use run_in_executor (never call sync SDK from async context)
- Backend: local imports inside create_app() to avoid circular imports
- Backend: per-request app_settings reads (no module-level caching)
- Frontend: TanStack Query v5 is installed — use for all REST data fetching
- Frontend: shadcn/ui is the component library — use its primitives, don't bring in other UI libs

### Integration Points
- New backend needed: `GET /posts` (paginated, newest first) + `GET /signals` for the feed
- New backend needed: `GET /trades` (orders with joined signal + post) for trade log
- New backend needed: `GET /portfolio` (Alpaca positions + account) for portfolio view
- New backend needed: WebSocket `/ws/feed` for live post push
- New backend needed: `POST /watchlist` + `DELETE /watchlist/{symbol}` for watchlist management
- New backend needed: `GET /watchlist` for settings page initial load
- New backend needed: `GET /alerts` or alert state surfaced via WebSocket
- Frontend routing: React Router v6 for sidebar navigation between pages

</code_context>

<specifics>
## Specific Ideas

- Kill switch is always visible in the sidebar — user should never have to navigate to find it
- LLM raw prompt/response exposed in trade log expanded view — for debugging signal quality
- Filtered posts shown grayed out (not hidden) so user can see what was filtered and why
- PAPER/LIVE badge always visible — user should always know which mode they're in

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 06-web-dashboard*
*Context gathered: 2026-04-21*
