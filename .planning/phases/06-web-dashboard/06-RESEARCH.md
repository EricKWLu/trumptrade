# Phase 6: Web Dashboard - Research

**Researched:** 2026-04-21
**Domain:** React 18 + FastAPI WebSocket + shadcn/ui + TanStack Query v5
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Sidebar navigation — persistent left sidebar with icon + label for each section. Four main sections: Feed, Trades, Portfolio, Settings. These are separate routes (React Router).
- **D-02:** PAPER/LIVE trading mode badge sits at the bottom of the sidebar, always visible.
- **D-03:** Portfolio view: summary cards row at top (total equity, P&L today, buying power), then positions table below. Data reads live from Alpaca API — never from bot's internal state.
- **D-04:** Post cards show full post text, platform icon, relative timestamp, colored sentiment badge (BULLISH/BEARISH/NEUTRAL + confidence %). Affected tickers listed.
- **D-05:** Filtered posts shown grayed out with filter reason displayed.
- **D-06:** WebSocket push — new posts auto-insert at top of feed without user action.
- **D-07:** Expandable row table — one row per order. Clicking expands to show full audit chain: post content, signal details, fill price, raw LLM prompt + response.
- **D-08:** Raw LLM prompt and response ARE visible in expanded audit detail.
- **D-09:** Kill switch is prominent at top of sidebar — always visible. Red "Stop Bot" when running, green "Start Bot" when stopped. Single click, no confirmation modal. Calls `POST /trading/kill-switch`.
- **D-10:** Active errors appear in persistent alert panel below sidebar nav. Errors persist until resolved. Surfaced errors include: scraper silence, Alpaca API errors, LLM failures.
- **D-11:** Settings page with two sections: Watchlist (chips + add input) and Risk Controls (4 numeric fields + Save button).

### Claude's Discretion
- Exact color palette for BULLISH/BEARISH/NEUTRAL badges (resolved in UI-SPEC)
- shadcn/ui component choices (resolved in UI-SPEC)
- Loading skeleton design
- Empty state designs
- Exact WebSocket message format and reconnect behavior
- Error boundary handling for Alpaca API failures on Portfolio page
- How the alert panel clears resolved alerts

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DASH-01 | Live post feed via WebSocket push | FastAPI ConnectionManager pattern + `usePostFeed()` hook |
| DASH-02 | Full trade log with post→signal→order→fill audit chain | shadcn Collapsible + Table pattern; `GET /trades` join query |
| DASH-03 | Portfolio positions + P&L reading live from Alpaca API | `run_in_executor` pattern for sync Alpaca SDK; `GET /portfolio` route |
| DASH-04 | Kill switch toggle + error/alert panel | Existing `POST /trading/kill-switch`; optimistic useMutation; `GET /alerts` polling |
| SETT-01 | Watchlist add/remove from dashboard | New `GET/POST/DELETE /watchlist` routes; mutation + cache invalidation |
| SETT-02 | Risk controls form from dashboard | Existing `GET/PATCH /settings/risk`; already implemented |
</phase_requirements>

---

## Summary

Phase 6 is a full-stack wiring phase: no new business logic, but significant surface area across both the FastAPI backend (6 new routers/routes + 1 WebSocket endpoint) and the React frontend (4 pages, sidebar shell, custom WebSocket hook, 10+ shadcn components). The frontend scaffold exists (`frontend/src/App.tsx`) with React 19, TanStack Query v5, Tailwind v4, shadcn `base-nova` style, and `@base-ui/react` installed. React Router is NOT yet installed — it must be added.

The dominant technical challenge is the WebSocket broadcast architecture: the `analysis/worker.py` APScheduler job inserts Post rows and must notify all connected browser clients. The correct pattern is a module-level `ConnectionManager` singleton in `trumptrade/dashboard/` that the WebSocket endpoint and the analysis worker both import. The worker calls `await connection_manager.broadcast(json.dumps(post_data))` after inserting a Post row. This is single-process (single uvicorn worker) — no Redis needed.

The second challenge is the Alpaca SDK sync-in-async issue: `TradingClient.get_account()` and `get_all_positions()` are synchronous. The established project pattern (already used in `trading/executor.py`) is `asyncio.get_event_loop().run_in_executor(None, sync_fn)`. The portfolio route must follow this pattern.

**Primary recommendation:** Build from the outside in — shell layout first, then each page in dependency order: Feed (simplest, REST only) → Portfolio (Alpaca integration) → Settings (mutations) → Trades (join query + collapsible). Wire WebSocket last after all REST endpoints work.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Live post feed (WebSocket) | API / Backend (connection mgr) | Browser (usePostFeed hook) | Server initiates push; browser consumes |
| Post/trade data display | Browser / Client | API / Backend | React state drives rendering |
| Portfolio P&L | API / Backend | — | Must proxy Alpaca sync SDK via run_in_executor |
| Kill switch toggle | Browser (optimistic) | API / Backend | Immediate UI feedback; backend is source of truth |
| Watchlist CRUD | API / Backend | Browser (cache invalidation) | DB is authoritative; TQ invalidates on success |
| Risk settings form | Browser (form state) | API / Backend | Local form state → PATCH on save |
| Alert panel | Browser | API / Backend (GET /alerts polling) | Browser polls; no push needed |
| Sidebar layout + routing | Browser / Client | — | Pure frontend concern |

---

## Standard Stack

### Core — Backend
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | existing | WebSocket endpoint + new REST routers | Already installed; `WebSocket` + `WebSocketDisconnect` built-in |
| SQLAlchemy 2.x async | existing | DB queries for posts, trades joins | Already installed; all existing routers use this |
| alpaca-py | existing | `get_account()`, `get_all_positions()` | Project mandate; already in executor.py |

### Core — Frontend
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| react-router-dom | 6.30.3 (pin v6) | Sidebar routing, `createBrowserRouter`, `NavLink`, `Outlet` | CONTEXT.md locks "React Router v6"; v7 API is compatible but pin v6 to match decision |
| @tanstack/react-query | 5.99.1 (installed) | All REST data fetching, mutations, cache management | Already installed in package.json |
| shadcn/ui (base-nova) | installed | All UI components via `npx shadcn add` | Already initialized; components.json configured |
| lucide-react | 1.8.0 (installed) | Icons throughout | Already installed |

**Note on react-router version:** CONTEXT.md specifies "React Router v6". Current npm `latest` is v7 (7.14.1). Install `react-router-dom@6` (latest v6 = 6.30.3) to honor the locked decision. Core APIs (`createBrowserRouter`, `NavLink`, `Outlet`, `RouterProvider`) exist in both and behave identically for this use case. [VERIFIED: npm registry — `npm view react-router-dom@6 version`]

### shadcn Components to Install
All from official `base-nova` registry. Install command below.

| Component | shadcn name | Used In |
|-----------|-------------|---------|
| Badge | `badge` | Sentiment, mode, alert count |
| Card | `card` | Portfolio summary, post cards |
| Table | `table` | Trade log, positions |
| Collapsible | `collapsible` | Expandable trade rows |
| Input | `input` | Add ticker, risk fields |
| Separator | `separator` | Sidebar dividers |
| Skeleton | `skeleton` | Loading states |
| Alert | `alert` | Alert panel items |
| Tooltip | `tooltip` | Sidebar nav icon labels |
| ScrollArea | `scroll-area` | Feed, trade log |

**Installation:**
```bash
# React Router v6
npm install react-router-dom@6

# shadcn components (run from frontend/)
npx shadcn add badge card table collapsible input separator skeleton alert tooltip scroll-area
```

**Version verification (current npm):** [VERIFIED: npm registry]
- `react-router-dom`: latest v6 = 6.30.3
- `react-router-dom`: latest v7 = 7.14.1 (do NOT install — use @6 pin)

---

## Architecture Patterns

### System Architecture Diagram

```
Browser (React)                     FastAPI Backend
─────────────────                   ──────────────────────────────────────

App.tsx                             create_app()
  └─ RouterProvider                   ├─ GET /posts           (new)
       └─ AppShell (sidebar)          ├─ GET /trades          (new)
            ├─ KillSwitchBtn ─────── POST /trading/kill-switch (existing)
            ├─ NavLinks              ├─ GET /portfolio         (new, Alpaca proxy)
            ├─ AlertPanel ─────────  GET /alerts              (new)
            └─ <Outlet>             ├─ GET /watchlist         (new)
                 ├─ FeedPage        ├─ POST /watchlist         (new)
                 │    └─ usePostFeed() ──── ws://…/ws/feed ──► ConnectionManager
                 ├─ TradesPage ──── GET /trades               (new)
                 ├─ PortfolioPage ─ GET /portfolio            (new)
                 └─ SettingsPage    ├─ GET/PATCH /settings/risk (existing)
                                    └─ DELETE /watchlist/{sym} (new)

Analysis Worker (APScheduler)
  └─ insert Post → await manager.broadcast(post_json)
                              ▲
                   ConnectionManager (module-level singleton)
                   trumptrade/dashboard/ws.py
```

### Recommended Project Structure
```
trumptrade/dashboard/
├── __init__.py          # exports: dashboard_router, ws_router
├── ws.py                # ConnectionManager singleton + /ws/feed endpoint
├── router.py            # GET /posts, GET /trades, GET /portfolio, GET /alerts
└── watchlist.py         # GET/POST/DELETE /watchlist

frontend/src/
├── router.tsx           # createBrowserRouter config
├── components/
│   ├── AppShell.tsx     # sidebar + <Outlet>
│   ├── KillSwitchBtn.tsx
│   ├── AlertPanel.tsx
│   └── ui/              # shadcn components (auto-generated)
├── hooks/
│   └── usePostFeed.ts   # WebSocket hook
├── pages/
│   ├── FeedPage.tsx
│   ├── TradesPage.tsx
│   ├── PortfolioPage.tsx
│   └── SettingsPage.tsx
└── lib/
    ├── api.ts           # typed fetch wrappers
    └── utils.ts         # existing cn() utility
```

### Pattern 1: FastAPI ConnectionManager (Module-Level Singleton)

The key design: one `ConnectionManager` instance is module-level in `ws.py`. The WebSocket endpoint imports and uses it. The analysis worker also imports it to broadcast after inserting posts.

```python
# trumptrade/dashboard/ws.py
# Source: https://fastapi.tiangolo.com/advanced/websockets/
import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter()


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("WS client connected — total: %d", len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.remove(websocket)
        logger.info("WS client disconnected — total: %d", len(self.active_connections))

    async def broadcast(self, message: str) -> None:
        """Broadcast to all clients; silently remove dead connections."""
        dead: list[WebSocket] = []
        for ws in self.active_connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active_connections.remove(ws)


# Module-level singleton — imported by analysis worker to trigger broadcast
manager = ConnectionManager()


@router.websocket("/ws/feed")
async def websocket_feed(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive; client is receive-only
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
```

### Pattern 2: Broadcast from Analysis Worker

The analysis worker imports `manager` and calls broadcast after inserting a Post row. This works because both are in the same asyncio event loop (single uvicorn process).

```python
# trumptrade/analysis/worker.py  (addition — after Post insert)
# Source: [VERIFIED: FastAPI WebSocket docs pattern] [ASSUMED: import pattern]
from trumptrade.dashboard.ws import manager  # import singleton

async def _broadcast_post(post: Post) -> None:
    """Serialize post + signal to JSON and push to all WS clients."""
    payload = {
        "id": post.id,
        "platform": post.platform,
        "content": post.content,
        "posted_at": post.posted_at.isoformat(),
        "is_filtered": post.is_filtered,
        "filter_reason": post.filter_reason,
        # signal fields added after Signal row is created
    }
    await manager.broadcast(json.dumps(payload))
```

**Important:** The broadcast call must happen AFTER `await session.commit()` so the data is persisted before clients receive it.

### Pattern 3: Alpaca Sync SDK in Async FastAPI Route (run_in_executor)

The project already uses this pattern in `trading/executor.py`. Copy it exactly.

```python
# trumptrade/dashboard/router.py
# Source: established project pattern from trading/executor.py
import asyncio
from functools import partial
from alpaca.trading.client import TradingClient
from trumptrade.core.config import get_settings

@router.get("/portfolio")
async def get_portfolio() -> dict:
    settings = get_settings()
    trading_mode = await _read_setting("trading_mode")
    is_paper = (trading_mode == "paper")

    client = TradingClient(
        api_key=settings.alpaca_api_key,
        secret_key=settings.alpaca_secret_key,
        paper=is_paper,
    )

    loop = asyncio.get_event_loop()
    account = await loop.run_in_executor(None, client.get_account)
    positions = await loop.run_in_executor(None, client.get_all_positions)

    return {
        "equity": float(account.equity),
        "last_equity": float(account.last_equity),
        "buying_power": float(account.buying_power),
        "positions": [
            {
                "symbol": p.symbol,
                "qty": float(p.qty),
                "market_value": float(p.market_value),
                "avg_entry_price": float(p.avg_entry_price),
                "unrealized_pl": float(p.unrealized_pl),
                "unrealized_plpc": float(p.unrealized_plpc),
            }
            for p in positions
        ],
    }
```

### Pattern 4: GET /trades — Join Query (Post + Signal + Order + Fill)

```python
# trumptrade/dashboard/router.py
# Source: SQLAlchemy 2.x async pattern established in project
from sqlalchemy import select, outerjoin
from trumptrade.core.models import Order, Signal, Post, Fill

@router.get("/trades")
async def get_trades(db: AsyncSession = Depends(get_db)) -> list[dict]:
    stmt = (
        select(Order, Signal, Post, Fill)
        .outerjoin(Signal, Order.signal_id == Signal.id)
        .outerjoin(Post, Signal.post_id == Post.id)
        .outerjoin(Fill, Fill.order_id == Order.id)
        .order_by(Order.submitted_at.desc())
        .limit(200)
    )
    result = await db.execute(stmt)
    rows = result.all()
    # serialize each (Order, Signal, Post, Fill) tuple
    ...
```

### Pattern 5: React Router v6 Sidebar Layout (Outlet)

```tsx
// Source: https://reactrouter.com/en/6.30.3/start/tutorial
// frontend/src/router.tsx
import { createBrowserRouter } from "react-router-dom"
import AppShell from "./components/AppShell"
import FeedPage from "./pages/FeedPage"
import TradesPage from "./pages/TradesPage"
import PortfolioPage from "./pages/PortfolioPage"
import SettingsPage from "./pages/SettingsPage"

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <FeedPage /> },
      { path: "trades", element: <TradesPage /> },
      { path: "portfolio", element: <PortfolioPage /> },
      { path: "settings", element: <SettingsPage /> },
    ],
  },
])

// frontend/src/components/AppShell.tsx
import { NavLink, Outlet } from "react-router-dom"

export default function AppShell() {
  return (
    <div className="flex h-screen">
      <aside className="w-60 flex-shrink-0 flex flex-col bg-sidebar border-r border-sidebar-border">
        <KillSwitchBtn />
        <nav>
          <NavLink to="/" end className={({ isActive }) => isActive ? "active-nav" : "nav"}>
            <Zap size={16} /> Feed
          </NavLink>
          {/* ... other nav items */}
        </nav>
        <AlertPanel />
        <TradingModeBadge />
      </aside>
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
```

### Pattern 6: usePostFeed Hook (Browser Native WebSocket)

```tsx
// Source: [VERIFIED: MDN WebSocket API] — [ASSUMED: reconnect backoff implementation]
// frontend/src/hooks/usePostFeed.ts
import { useState, useEffect, useRef, useCallback } from "react"

type ConnectionStatus = "connected" | "reconnecting" | "disconnected"

export function usePostFeed() {
  const [posts, setPosts] = useState<Post[]>([])
  const [status, setStatus] = useState<ConnectionStatus>("disconnected")
  const wsRef = useRef<WebSocket | null>(null)
  const retryDelayRef = useRef(1000)

  const connect = useCallback(() => {
    const ws = new WebSocket("ws://localhost:8000/ws/feed")
    wsRef.current = ws

    ws.onopen = () => {
      setStatus("connected")
      retryDelayRef.current = 1000 // reset backoff
    }

    ws.onmessage = (event) => {
      const post: Post = JSON.parse(event.data)
      setPosts(prev => [post, ...prev])  // prepend — newest at top
    }

    ws.onclose = () => {
      setStatus("reconnecting")
      const delay = Math.min(retryDelayRef.current, 30000)
      retryDelayRef.current = delay * 2
      setTimeout(connect, delay)
    }
  }, [])

  useEffect(() => {
    connect()
    return () => {
      wsRef.current?.close()
    }
  }, [connect])

  return { posts, status }
}
```

### Pattern 7: shadcn Collapsible + Table Row (Expandable)

The shadcn Table does NOT natively support accordion rows. The pattern wraps `<TableRow>` in `<Collapsible asChild>` with `CollapsibleContent asChild` rendering a second `<TableRow>`.

```tsx
// Source: https://dev.to/mfts/build-an-expandable-data-table-with-2-shadcnui-components-4nge
// [VERIFIED: shadcn/ui docs + community pattern]
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Table, TableBody, TableCell, TableRow } from "@/components/ui/table"

function TradeRow({ trade }: { trade: TradeWithAudit }) {
  return (
    <Collapsible asChild>
      <>
        <TableRow className="cursor-pointer">
          <TableCell className="font-semibold">{trade.symbol}</TableCell>
          <TableCell className={trade.side === "buy" ? "text-green-400" : "text-red-400"}>
            {trade.side.toUpperCase()}
          </TableCell>
          <TableCell className="tabular-nums">{trade.qty}</TableCell>
          <TableCell>
            <StatusBadge status={trade.status} />
          </TableCell>
          <TableCell className="text-xs text-muted-foreground">
            {relativeTime(trade.submitted_at)}
          </TableCell>
          <TableCell>
            <CollapsibleTrigger asChild>
              <button>
                <ChevronDown className="h-4 w-4" />
              </button>
            </CollapsibleTrigger>
          </TableCell>
        </TableRow>
        <CollapsibleContent asChild>
          <TableRow className="bg-secondary/50">
            <TableCell colSpan={6}>
              <AuditDetail trade={trade} />
            </TableCell>
          </TableRow>
        </CollapsibleContent>
      </>
    </Collapsible>
  )
}
```

### Pattern 8: TanStack Query v5 useMutation with Optimistic Update

```tsx
// Source: https://tanstack.com/query/v5/docs/framework/react/guides/mutations
// Kill switch optimistic update
const mutation = useMutation({
  mutationFn: (enabled: boolean) =>
    fetch("/trading/kill-switch", {
      method: "POST",
      body: JSON.stringify({ enabled }),
      headers: { "Content-Type": "application/json" },
    }).then(r => r.json()),
  onMutate: async (enabled) => {
    // Optimistic: update local state immediately
    setOptimisticEnabled(enabled)
    return { previousEnabled: !enabled }
  },
  onError: (_err, _vars, context) => {
    // Revert on error
    if (context) setOptimisticEnabled(context.previousEnabled)
  },
})
```

### Pattern 9: FastAPI CORS for Vite Dev Server

```python
# trumptrade/core/app.py — add inside create_app()
# Source: https://fastapi.tiangolo.com/tutorial/cors/
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Note:** Vite already has a proxy configured (`/api → localhost:8000`) but it only intercepts `/api`-prefixed paths. Since backend routes are `/posts`, `/trades`, `/ws/feed` etc. (no `/api` prefix), CORS middleware is required for dev. For production, Vite builds to static files served behind the same origin — CORS not needed in prod.

### Anti-Patterns to Avoid

- **Calling sync Alpaca SDK from async context without run_in_executor:** Will block the entire event loop. Every Alpaca call in the new portfolio router must go through `run_in_executor`.
- **Creating TradingClient at module level (cached):** Project decision is per-request instantiation (D-06 from Phase 2). Executor already does this; copy the same pattern.
- **Using `queryClient.invalidateQueries` for WebSocket-delivered posts:** Triggers a redundant GET /posts fetch. Instead, use `queryClient.setQueryData` or manage posts in local React state via `usePostFeed`.
- **Importing ConnectionManager inside the WebSocket endpoint function:** Must be module-level so the analysis worker can import the same instance.
- **Broadcasting before session.commit():** Race condition — client receives a post ID it can't yet fetch. Always broadcast after commit.
- **Using `react-router-dom` v7 imports:** If react-router-dom@6 is installed, use `from "react-router-dom"`. Do not mix with `from "react-router"` v7 imports.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Relative timestamps ("3 min ago") | Custom formatter | `date-fns` `formatDistanceToNow` or `Intl.RelativeTimeFormat` | Edge cases with timezones, DST, plural forms |
| WebSocket reconnect with backoff | Custom retry loop | Pattern 6 above (simple, proven) | Already well-understood; `date-fns` is available |
| Expandable table rows | Custom accordion | shadcn `Collapsible` + `Table` (Pattern 7) | Handles animation, accessibility, keyboard nav |
| Loading states | Custom spinner | shadcn `Skeleton` | Consistent shimmer animation via `tw-animate-css` (already installed) |
| Form state for risk settings | Custom form lib | React `useState` + controlled inputs | Simple 4-field form; no need for react-hook-form |

**Key insight:** `date-fns` should be installed — it is not in package.json currently but `formatDistanceToNow` is the standard for relative timestamps. Alternative: `Intl.RelativeTimeFormat` (browser built-in, no install needed). Use the built-in to avoid adding a dependency.

---

## Common Pitfalls

### Pitfall 1: WebSocket Broadcast Blocks on Dead Connection
**What goes wrong:** A client disconnects without sending a close frame. The `send_text()` call hangs or raises immediately. Without try/except in the broadcast loop, the entire broadcast fails for all other clients.
**Why it happens:** Mobile clients, browser tab crashes, network interruption.
**How to avoid:** Wrap each `send_text()` in try/except inside `broadcast()`. Collect dead connections, remove after the loop (not during iteration). [VERIFIED: Pattern confirmed in FastAPI docs and community examples]
**Warning signs:** Feed stops updating for some clients; no error in logs.

### Pitfall 2: Importing ConnectionManager Creates a New Instance
**What goes wrong:** Analysis worker does `from trumptrade.dashboard.ws import ConnectionManager; manager = ConnectionManager()` instead of `from trumptrade.dashboard.ws import manager`. Two separate instances — broadcast from worker goes to zero clients.
**Why it happens:** Forgetting the singleton is the module-level instance, not the class.
**How to avoid:** Always import `manager` (the instance), never `ConnectionManager` (the class), in the analysis worker.

### Pitfall 3: Alpaca SDK Blocks Event Loop
**What goes wrong:** `client.get_account()` or `client.get_all_positions()` is called directly in an `async def` route. This blocks the uvicorn event loop for the duration of the HTTP call (typically 100-500ms), freezing all other requests including WebSocket pings.
**Why it happens:** `alpaca-py` `TradingClient` is a sync SDK with no `async` equivalent.
**How to avoid:** Always wrap in `await loop.run_in_executor(None, sync_fn)`. The project already does this in `executor.py` — copy that exact pattern. [VERIFIED: established project pattern]

### Pitfall 4: CORS Blocks WebSocket Upgrade
**What goes wrong:** CORSMiddleware is added but WebSocket connections still fail with 403. CORSMiddleware does not apply to WebSocket upgrades (protocol switch happens at the HTTP layer before CORS response headers).
**Why it happens:** WebSocket connections from `localhost:5173` to `localhost:8000` are a cross-origin request. Browser sends an Origin header in the upgrade request.
**How to avoid:** FastAPI's built-in WebSocket handling accepts connections from any origin by default (no `allowed_origins` parameter on the websocket decorator). The browser does NOT block WebSocket upgrades via CORS — CORS only applies to XHR/fetch. This is a non-issue: WebSocket from Vite to FastAPI works without special config.
**Warning signs:** `ws.onclose` fires immediately on connect.

### Pitfall 5: React Router Nested Route Index Mismatch
**What goes wrong:** The root path `/` renders blank `<Outlet>` instead of FeedPage.
**Why it happens:** Child route for Feed is specified as `path: "/"` instead of `index: true`.
**How to avoid:** Use `{ index: true, element: <FeedPage /> }` for the default child route, not `{ path: "/" }`. [VERIFIED: React Router v6 docs]

### Pitfall 6: TanStack Query v5 API Differences from v4
**What goes wrong:** Using v4 API patterns (e.g., `cacheTime`, `keepPreviousData`, `isLoading` before first load).
**Why it happens:** Training data or tutorials reference v4.
**How to avoid:** In v5: `cacheTime` → `gcTime`, `keepPreviousData` → `placeholderData`, `isLoading` → `isPending`. The project already has v5 installed (5.99.1). [VERIFIED: package.json]

### Pitfall 7: shadcn Component Version Mismatch (base-nova style)
**What goes wrong:** `npx shadcn add` installs base style components instead of base-nova style.
**Why it happens:** Running add command without ensuring components.json is present and correct.
**How to avoid:** `components.json` already exists with `"style": "base-nova"`. Run `npx shadcn add <component>` from the `frontend/` directory — shadcn reads components.json automatically.

### Pitfall 8: Analysis Worker Circular Import
**What goes wrong:** `trumptrade/dashboard/ws.py` imports something from `trumptrade/analysis/`, and `trumptrade/analysis/worker.py` imports from `trumptrade/dashboard/ws.py` → circular import.
**Why it happens:** Shared dependency not properly isolated.
**How to avoid:** `ws.py` must import only from FastAPI and Python stdlib. The analysis worker imports from `ws.py` — this is a one-way dependency. Keep `ws.py` free of any import from `analysis/` or `risk_guard/`.

---

## Code Examples

### GET /posts Endpoint Pattern

```python
# trumptrade/dashboard/router.py
# Source: established project pattern (risk_guard/router.py)
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trumptrade.core.db import get_db
from trumptrade.core.models import Post

router = APIRouter()

@router.get("/posts")
async def get_posts(
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    stmt = (
        select(Post)
        .order_by(Post.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    posts = result.scalars().all()
    return [
        {
            "id": p.id,
            "platform": p.platform,
            "content": p.content,
            "posted_at": p.posted_at.isoformat(),
            "created_at": p.created_at.isoformat(),
            "is_filtered": p.is_filtered,
            "filter_reason": p.filter_reason,
        }
        for p in posts
    ]
```

### Registering New Routers in create_app()

```python
# trumptrade/core/app.py — inside create_app() (local import pattern)
# Source: established project pattern
from trumptrade.dashboard import dashboard_router, ws_router
app.include_router(dashboard_router, tags=["dashboard"])
app.include_router(ws_router, tags=["websocket"])
```

### TanStack Query with refetchInterval (Portfolio)

```tsx
// Source: https://tanstack.com/query/v5/docs/framework/react/reference/useQuery
const { data, isLoading, isError } = useQuery({
  queryKey: ["portfolio"],
  queryFn: () => fetch("/portfolio").then(r => r.json()),
  staleTime: 10_000,
  refetchInterval: 15_000,  // poll every 15s — live Alpaca data
})
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `react-router-dom` v5 (`<Switch>`, `<Route>`) | `createBrowserRouter` + `RouterProvider` | v6 (2021) | Data router; nested layouts via `Outlet` |
| TanStack Query v4 (`cacheTime`, `keepPreviousData`) | v5 (`gcTime`, `placeholderData`) | 2023 | Renamed APIs — don't copy v4 examples |
| `alpaca-trade-api` (deprecated) | `alpaca-py` | 2023 | Project mandate — never use the old package |
| `react-router-dom` as separate package | `react-router` (v7 unified) | v7 (2024) | We pin v6 to honor CONTEXT.md decision |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Analysis worker can call `await manager.broadcast()` directly after inserting a Post — they share the same asyncio event loop | Pattern 2, Pitfall 2 | If APScheduler jobs run in a thread pool, `await` calls from a non-async context would fail. Mitigation: APScheduler `AsyncIOScheduler` runs jobs as coroutines in the event loop — this is the established project pattern. [LOW risk] |
| A2 | `Intl.RelativeTimeFormat` (browser built-in) is sufficient for relative timestamps without `date-fns` | Don't Hand-Roll | If browser support matrix requires IE11, it wouldn't work. But this is a personal desktop tool — modern browser assumed. [LOW risk] |
| A3 | `TradingClient.get_all_positions()` returns objects with `.symbol`, `.qty`, `.market_value`, `.avg_entry_price`, `.unrealized_pl`, `.unrealized_plpc` fields | Pattern 3 | Alpaca docs confirmed method exists; field names from alpaca-py SDK — [ASSUMED: field name spellings from training knowledge, not verified against live SDK]. Mitigation: executor.py uses TradingClient successfully — field names discoverable at runtime. |
| A4 | `GET /alerts` can be a simple polling endpoint that reads from app_settings or a new alerts table | Architecture | No alerts table exists in models.py. An alerts endpoint must be designed. May need a new `alerts` table or in-memory error registry. [MEDIUM risk — needs design decision in plan] |

---

## Open Questions

1. **Alert storage mechanism for GET /alerts**
   - What we know: CONTEXT.md D-10 specifies scraper silence (heartbeat), Alpaca API errors (from risk consumer), and LLM failures as alert sources. No `alerts` table exists in `models.py`.
   - What's unclear: Should alerts be persisted (DB table) or in-memory (module-level list)? Persisted alerts survive restarts but add migration complexity. In-memory is simpler but lost on restart.
   - Recommendation: In-memory `List[dict]` in `dashboard/router.py` is sufficient for this personal tool. Add a `GET /alerts` endpoint that returns the list. Error sources (risk guard, ingestion heartbeat) write to it via an `append_alert()` function. Polled every 10s by frontend.

2. **WebSocket message format — should it include signal data?**
   - What we know: Post rows are inserted by ingestion workers; Signal rows are inserted by analysis worker (separate APScheduler job, runs 30s after posts). A post arrives before its signal is ready.
   - What's unclear: Should the WS push include signal data (sentiment, confidence) or just post data?
   - Recommendation: Push post data immediately on insertion. Frontend shows post card with "Analyzing..." placeholder. A second push (or TanStack Query invalidation) delivers signal data when ready. Simpler: just push post data and let the feed reload signals via polling.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | Frontend build | ✓ | v24.14.1 | — |
| npm | Package install | ✓ | 11.12.1 | — |
| Python 3 | Backend | ✓ | (asyncio confirmed) | — |
| react-router-dom@6 | Frontend routing | ✗ (not installed) | — | Install: `npm install react-router-dom@6` |
| shadcn components (badge, card, table, etc.) | UI | ✗ (only button.tsx exists) | — | Install: `npx shadcn add ...` |

**Missing dependencies with no fallback:**
- `react-router-dom@6` — must be installed before routing can be implemented

**Missing dependencies with fallback:**
- shadcn components — button.tsx exists; others must be added via `npx shadcn add`

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Single-user personal tool, no auth required (Out of Scope per REQUIREMENTS.md) |
| V3 Session Management | No | No sessions — personal tool |
| V4 Access Control | No | No multi-user, no role separation |
| V5 Input Validation | Yes | Pydantic models on all POST/PATCH endpoints; watchlist symbol validation (alpha, 1-5 chars) |
| V6 Cryptography | No | No new crypto in this phase |

### Known Threat Patterns for this Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Watchlist symbol injection (e.g., SQL via ticker) | Tampering | Pydantic field validation: `pattern=r"^[A-Z]{1,5}$"` on symbol field; SQLAlchemy parameterized queries |
| WebSocket client sends malicious JSON | Tampering | WS endpoint is receive-only for this app; `receive_text()` result is discarded |
| CORS misconfiguration in production | Elevation of Privilege | Use specific origin list, not `"*"` — `["http://localhost:5173"]` for dev |

---

## Sources

### Primary (HIGH confidence)
- [FastAPI WebSocket docs](https://fastapi.tiangolo.com/advanced/websockets/) — ConnectionManager pattern, WebSocketDisconnect handling
- [FastAPI CORS docs](https://fastapi.tiangolo.com/tutorial/cors/) — CORSMiddleware configuration
- [React Router v6 tutorial](https://reactrouter.com/en/6.30.3/start/tutorial) — createBrowserRouter, NavLink, Outlet patterns
- [React Router v6→v7 upgrade guide](https://reactrouter.com/upgrading/v6) — breaking changes, import path changes
- Codebase: `trumptrade/core/app.py`, `trumptrade/trading/executor.py`, `trumptrade/risk_guard/router.py` — established project patterns
- Codebase: `frontend/package.json`, `frontend/components.json`, `frontend/src/index.css` — installed deps, shadcn config
- npm registry: `npm view react-router-dom@6 version` — confirmed 6.30.3 as latest v6

### Secondary (MEDIUM confidence)
- [TanStack Query v5 mutations docs](https://tanstack.com/query/v5/docs/framework/react/guides/mutations) — useMutation optimistic update pattern
- [shadcn expandable table article](https://dev.to/mfts/build-an-expandable-data-table-with-2-shadcnui-components-4nge) — Collapsible + Table row pattern
- [Leapcell TanStack Query WebSocket integration](https://leapcell.io/blog/advanced-data-fetching-with-tanstack-query-optimistic-updates-pagination-and-websocket-integration) — setQueryData from WebSocket pattern
- [Alpaca positions SDK docs](https://alpaca.markets/sdks/python/api_reference/trading/positions.html) — `get_all_positions()` signature

### Tertiary (LOW confidence)
- [UnfoldAI FastAPI WebSocket guide](https://unfoldai.com/fastapi-and-websockets/) — broadcast pattern (matches official docs)

---

## Metadata

**Confidence breakdown:**
- Standard Stack: HIGH — all deps verified against npm registry and package.json
- Architecture: HIGH — based on existing established patterns in codebase
- Pitfalls: HIGH — WebSocket and Alpaca patterns verified against official docs and codebase
- Alert mechanism: MEDIUM — open question on in-memory vs. DB storage

**Research date:** 2026-04-21
**Valid until:** 2026-05-21 (stable libraries; FastAPI/React Router APIs are stable)
