# Phase 6: Web Dashboard - Pattern Map

**Mapped:** 2026-04-21
**Files analyzed:** 19 new/modified files
**Analogs found:** 17 / 19

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `trumptrade/dashboard/__init__.py` | package init / export | — | `trumptrade/trading/__init__.py` | exact |
| `trumptrade/dashboard/ws.py` | WebSocket manager + endpoint | event-driven | `trumptrade/risk_guard/__init__.py` (module-level singleton) | role-match |
| `trumptrade/dashboard/router.py` | controller | request-response + CRUD | `trumptrade/risk_guard/router.py` | exact |
| `trumptrade/dashboard/watchlist.py` | controller | CRUD | `trumptrade/risk_guard/router.py` | exact |
| `trumptrade/core/app.py` (modify) | app factory | — | `trumptrade/core/app.py` (self) | exact |
| `trumptrade/core/config.py` (modify) | config | — | `trumptrade/core/config.py` (self) | exact |
| `trumptrade/analysis/worker.py` (modify) | background worker | event-driven | `trumptrade/analysis/worker.py` (self) | exact |
| `frontend/src/App.tsx` (rewrite) | router entry point | request-response | `frontend/src/main.tsx` | partial |
| `frontend/src/router.tsx` | route config | request-response | no analog (new pattern) | none |
| `frontend/src/components/AppShell.tsx` | layout component | — | `frontend/src/App.tsx` (scaffold) | partial |
| `frontend/src/components/KillSwitchBtn.tsx` | component | request-response | `frontend/src/components/ui/button.tsx` | role-match |
| `frontend/src/components/AlertPanel.tsx` | component | request-response | no close analog | none |
| `frontend/src/components/PostCard.tsx` | component | — | `frontend/src/components/ui/button.tsx` (structure) | partial |
| `frontend/src/components/TradeRow.tsx` | component | CRUD | no analog | partial |
| `frontend/src/components/PortfolioCard.tsx` | component | request-response | no analog | partial |
| `frontend/src/pages/FeedPage.tsx` | page component | event-driven | no analog | partial |
| `frontend/src/pages/TradesPage.tsx` | page component | CRUD | no analog | partial |
| `frontend/src/pages/PortfolioPage.tsx` | page component | request-response | no analog | partial |
| `frontend/src/pages/SettingsPage.tsx` | page component | CRUD | no analog | partial |
| `frontend/src/hooks/usePostFeed.ts` | hook | event-driven | no analog | none |
| `frontend/src/lib/api.ts` | utility | request-response | `frontend/src/lib/utils.ts` | partial |

---

## Pattern Assignments

### `trumptrade/dashboard/__init__.py` (package init, export)

**Analog:** `trumptrade/trading/__init__.py` (lines 1-6)

**Export pattern** (lines 1-6 of analog):
```python
"""Trading package — AlpacaExecutor service and FastAPI router."""
from __future__ import annotations

from trumptrade.trading.router import router as trading_router

__all__ = ["trading_router"]
```

**Apply as:** Export two routers — `dashboard_router` (REST) and `ws_router` (WebSocket). The dashboard package also needs to export the `ConnectionManager` singleton (`manager`) so `analysis/worker.py` can import it cleanly.

```python
# trumptrade/dashboard/__init__.py
"""Dashboard package — REST endpoints, WebSocket feed, and watchlist CRUD (Phase 6)."""
from __future__ import annotations

from trumptrade.dashboard.router import router as dashboard_router
from trumptrade.dashboard.watchlist import router as watchlist_router
from trumptrade.dashboard.ws import router as ws_router

__all__ = ["dashboard_router", "watchlist_router", "ws_router"]
```

---

### `trumptrade/dashboard/ws.py` (WebSocket manager + endpoint, event-driven)

**Analog:** `trumptrade/risk_guard/__init__.py` (module-level singleton pattern, lines 15-17) combined with `trumptrade/trading/router.py` (APIRouter pattern)

**Module-level singleton pattern** from `trumptrade/risk_guard/__init__.py` lines 15-17:
```python
# Module-level queue — safe in Python 3.11+ (no loop binding at creation time).
# D-02: maxsize=100 (blocks producer if backlogged; handles signal bursts).
signal_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
```

**APIRouter pattern** from `trumptrade/trading/router.py` lines 1-5:
```python
from __future__ import annotations
import logging
from fastapi import APIRouter, HTTPException
...
logger = logging.getLogger(__name__)
router = APIRouter()
```

**Core pattern to implement** (from RESEARCH.md Pattern 1 — validated against FastAPI docs):
```python
# trumptrade/dashboard/ws.py
from __future__ import annotations

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


# Module-level singleton — imported by analysis worker to trigger broadcast.
# CRITICAL: import `manager` (the instance), never `ConnectionManager` (the class).
manager = ConnectionManager()


@router.websocket("/ws/feed")
async def websocket_feed(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep-alive; client is receive-only
    except WebSocketDisconnect:
        manager.disconnect(websocket)
```

**Critical constraint:** `ws.py` must import ONLY from FastAPI and Python stdlib. No imports from `analysis/`, `risk_guard/`, or `trading/` — avoids circular import (Pitfall 8 in RESEARCH.md).

---

### `trumptrade/dashboard/router.py` (controller, request-response + CRUD)

**Analog:** `trumptrade/risk_guard/router.py` (all lines)

**Imports pattern** (from analog lines 1-25):
```python
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, update

from trumptrade.core.db import AsyncSessionLocal
from trumptrade.core.models import AppSettings
```

**DB helper pattern** (from analog lines 47-54):
```python
async def _read_setting(key: str, default: str) -> str:
    """Read a single app_settings value. Returns default if key missing."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AppSettings.value).where(AppSettings.key == key)
        )
        val = result.scalar_one_or_none()
        return val if val is not None else default
```

**GET route pattern** (from analog lines 73-80):
```python
@router.get("/risk", response_model=RiskSettingsResponse)
async def get_risk_settings() -> RiskSettingsResponse:
    """Return current values of all risk settings from app_settings."""
    try:
        return await _read_all_risk_settings()
    except Exception as exc:
        logger.error("get_risk_settings: DB error: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to read risk settings")
```

**Query with pagination pattern** (from RESEARCH.md Code Examples — follows analog DB pattern):
```python
@router.get("/posts")
async def get_posts(
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    stmt = (
        select(Post)
        .order_by(Post.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    async with AsyncSessionLocal() as session:
        result = await session.execute(stmt)
        posts = result.scalars().all()
    return [{"id": p.id, "platform": p.platform, ...} for p in posts]
```

**Alpaca run_in_executor pattern** (from `trumptrade/trading/executor.py` lines 55-68 — established project pattern):
```python
# STEP 4: Fetch with run_in_executor — alpaca-py has NO async methods
loop = asyncio.get_running_loop()
try:
    trade_map = await loop.run_in_executor(
        None,
        partial(
            data_client.get_stock_latest_trade,
            StockLatestTradeRequest(symbol_or_symbols=symbol),
        ),
    )
except APIError as exc:
    logger.error("Alpaca data API error: %s", exc)
    raise HTTPException(status_code=502, detail=f"Alpaca data error: {exc.message}")
```

**Apply for GET /portfolio as:**
```python
loop = asyncio.get_running_loop()
account = await loop.run_in_executor(None, client.get_account)
positions = await loop.run_in_executor(None, client.get_all_positions)
```

**TradingClient per-request pattern** (from `trumptrade/trading/executor.py` lines 41-48):
```python
# Per-request instantiation (NOT cached — D-06 requires mode re-read)
settings = get_settings()
trading_client = TradingClient(
    api_key=settings.alpaca_api_key,
    secret_key=settings.alpaca_secret_key,
    paper=is_paper,
)
```

**Join query pattern** (from RESEARCH.md Pattern 4 — SQLAlchemy 2.x async, matches `analysis/worker.py` select pattern):
```python
from sqlalchemy import select
# multi-table join:
stmt = (
    select(Order, Signal, Post, Fill)
    .outerjoin(Signal, Order.signal_id == Signal.id)
    .outerjoin(Post, Signal.post_id == Post.id)
    .outerjoin(Fill, Fill.order_id == Order.id)
    .order_by(Order.submitted_at.desc())
    .limit(200)
)
result = await session.execute(stmt)
rows = result.all()
```

**In-memory alert store pattern** (no analog — new; follow module-level list pattern from `risk_guard/__init__.py`):
```python
# Module-level in-memory alert store
_alerts: list[dict] = []

def append_alert(source: str, message: str) -> None:
    """Called by risk guard / ingestion heartbeat to surface errors."""
    _alerts.append({"source": source, "message": message, "ts": datetime.utcnow().isoformat()})

@router.get("/alerts")
async def get_alerts() -> list[dict]:
    return list(_alerts)
```

---

### `trumptrade/dashboard/watchlist.py` (controller, CRUD)

**Analog:** `trumptrade/risk_guard/router.py` — Pydantic model + PATCH pattern

**Imports pattern** (from analog lines 1-24):
```python
from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, delete

from trumptrade.core.db import AsyncSessionLocal
from trumptrade.core.models import Watchlist

logger = logging.getLogger(__name__)
router = APIRouter()
```

**Pydantic validation model** (from analog lines 37-42 — adapt for symbol):
```python
class WatchlistAdd(BaseModel):
    symbol: str = Field(pattern=r"^[A-Z]{1,5}$")  # uppercase alpha 1-5 chars; SQL-injection safe
```

**Session write pattern** (from `trumptrade/trading/executor.py` lines 127-135):
```python
async with AsyncSessionLocal() as session:
    session.add(Order(...))
    await session.commit()
```

**Apply for POST /watchlist:**
```python
@router.post("/watchlist", status_code=201)
async def add_watchlist(body: WatchlistAdd) -> dict:
    try:
        async with AsyncSessionLocal() as session:
            session.add(Watchlist(symbol=body.symbol))
            await session.commit()
        return {"symbol": body.symbol, "added": True}
    except Exception as exc:  # IntegrityError if duplicate
        raise HTTPException(status_code=409, detail=f"Symbol already in watchlist: {body.symbol}")
```

**Error handling pattern** (from analog lines 79-80):
```python
    except Exception as exc:
        logger.error("watchlist_delete: DB error: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to update watchlist")
```

---

### `trumptrade/core/app.py` (modify — add CORS + dashboard routers)

**Analog:** `trumptrade/core/app.py` itself (lines 73-111)

**Local import + include_router pattern** (lines 88-93):
```python
# ── Phase 2: trading router ──────────────────────────────────────────────
from trumptrade.trading import trading_router          # local import avoids circular import
app.include_router(trading_router, prefix="/trading", tags=["trading"])

# ── Phase 5: risk settings router ───────────────────────────────────────
from trumptrade.risk_guard import settings_router      # local import avoids circular import
app.include_router(settings_router, prefix="/settings", tags=["settings"])
```

**New block to add after existing routers:**
```python
# ── Phase 6: dashboard + WebSocket routers ──────────────────────────────
from trumptrade.dashboard import dashboard_router, watchlist_router, ws_router  # local import
app.include_router(dashboard_router, tags=["dashboard"])
app.include_router(watchlist_router, tags=["watchlist"])
app.include_router(ws_router, tags=["websocket"])
```

**CORS middleware** (add before router registration, inside `create_app()`):
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

### `trumptrade/core/config.py` (modify — add CORS origins setting)

**Analog:** `trumptrade/core/config.py` itself (lines 1-43)

**Existing pattern** (lines 9-14):
```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
```

**New field to add in the "Non-secret app config" block (after line 30):**
```python
    # CORS — comma-separated origins; default covers Vite dev server
    cors_origins: str = "http://localhost:5173"
```

Note: The RESEARCH.md hardcodes `["http://localhost:5173"]` directly in `create_app()`. Either approach works. Prefer the hardcoded version in `app.py` for simplicity (single-user tool, not configurable).

---

### `trumptrade/analysis/worker.py` (modify — broadcast after Post insert)

**Analog:** `trumptrade/analysis/worker.py` itself — local import pattern at lines 283-286:
```python
# Local import inside loop body avoids circular import (established codebase pattern).
if final_action in ("BUY", "SELL") and final_tickers:
    from trumptrade.risk_guard import signal_queue, QueueItem  # local import
    item = QueueItem(...)
```

**New broadcast block to add after `await session.commit()` of the Signal row (lines 276-278):**
```python
        # Phase 6: broadcast post to WebSocket clients after commit.
        # CRITICAL: broadcast AFTER commit — client must be able to fetch the row.
        # Local import avoids circular import (ws.py must never import from analysis/).
        from trumptrade.dashboard.ws import manager  # local import — singleton instance
        import json as _json
        await manager.broadcast(_json.dumps({
            "type": "post",
            "id": post.id,
            "platform": post.platform,
            "content": post.content,
            "posted_at": post.posted_at.isoformat(),
            "is_filtered": post.is_filtered,
            "filter_reason": post.filter_reason,
            "signal": {
                "sentiment": signal_result.sentiment,
                "confidence": signal_result.confidence,
                "affected_tickers": final_tickers,
                "final_action": final_action,
                "reason_code": reason_code,
            },
        }))
```

**Important:** Import `manager` (the module-level instance), never `ConnectionManager` (the class). Importing inside the loop body (per existing local-import convention) avoids startup circular import.

---

### `frontend/src/App.tsx` (rewrite — RouterProvider entry)

**Analog:** `frontend/src/main.tsx` (lines 1-24) — how QueryClientProvider wraps the tree

**Existing QueryClientProvider wrapper in main.tsx** (lines 1-24):
```tsx
import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { ReactQueryDevtools } from "@tanstack/react-query-devtools"
import "./index.css"
import App from "./App.tsx"

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 30,
      retry: 1,
    },
  },
})
```

**Rewrite App.tsx as RouterProvider consumer:**
```tsx
import { RouterProvider } from "react-router-dom"
import { router } from "./router"

export default function App() {
  return <RouterProvider router={router} />
}
```

Note: `main.tsx` stays unchanged (owns `QueryClientProvider`). `App.tsx` becomes a thin shell that hands off to `RouterProvider`. The existing `queryClient` config in `main.tsx` (staleTime 30s, retry 1) applies to all pages.

---

### `frontend/src/router.tsx` (route config — no analog)

**Closest pattern:** RESEARCH.md Pattern 5 (React Router v6 `createBrowserRouter`)

```tsx
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
      { index: true, element: <FeedPage /> },       // CRITICAL: index:true, not path:"/"
      { path: "trades", element: <TradesPage /> },
      { path: "portfolio", element: <PortfolioPage /> },
      { path: "settings", element: <SettingsPage /> },
    ],
  },
])
```

**Pitfall:** Use `{ index: true }` not `{ path: "/" }` for FeedPage child — see RESEARCH.md Pitfall 5.

---

### `frontend/src/components/AppShell.tsx` (layout component)

**Analog:** `frontend/src/components/ui/button.tsx` — component export structure (lines 43-58)

**Component export pattern** (analog lines 43-58):
```tsx
function Button({
  className,
  variant = "default",
  size = "default",
  ...props
}: ButtonPrimitive.Props & VariantProps<typeof buttonVariants>) {
  return (
    <ButtonPrimitive
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
```

**cn() usage pattern** from `frontend/src/lib/utils.ts` (lines 1-5):
```ts
import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

**Apply AppShell structure** (from RESEARCH.md Pattern 5):
```tsx
import { NavLink, Outlet } from "react-router-dom"
import { cn } from "@/lib/utils"
import KillSwitchBtn from "./KillSwitchBtn"
import AlertPanel from "./AlertPanel"

export default function AppShell() {
  return (
    <div className="flex h-screen bg-background">
      <aside className="w-60 flex-shrink-0 flex flex-col border-r border-border">
        <KillSwitchBtn />
        <nav className="flex-1 px-2 py-4 space-y-1">
          <NavLink to="/" end className={({ isActive }) => cn("flex items-center gap-2 px-3 py-2 rounded-md text-sm", isActive ? "bg-accent text-accent-foreground" : "hover:bg-accent/50")}>
            Feed
          </NavLink>
          {/* Trades, Portfolio, Settings NavLinks same pattern */}
        </nav>
        <AlertPanel />
        {/* Trading mode badge at bottom */}
      </aside>
      <main className="flex-1 overflow-auto p-6">
        <Outlet />
      </main>
    </div>
  )
}
```

---

### `frontend/src/components/KillSwitchBtn.tsx` (component, request-response)

**Analog:** `frontend/src/components/ui/button.tsx` — Button component with variant prop

**Button import pattern:**
```tsx
import { Button } from "@/components/ui/button"
```

**useMutation pattern** (from RESEARCH.md Pattern 8 — TanStack Query v5):
```tsx
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

const { data: status } = useQuery({
  queryKey: ["bot-status"],
  queryFn: () => fetch("/settings/risk").then(r => r.json()),
})

const mutation = useMutation({
  mutationFn: (enabled: boolean) =>
    fetch("/trading/kill-switch", {
      method: "POST",
      body: JSON.stringify({ enabled }),
      headers: { "Content-Type": "application/json" },
    }).then(r => r.json()),
  onMutate: async (enabled) => {
    setOptimisticEnabled(enabled)
    return { previousEnabled: !enabled }
  },
  onError: (_err, _vars, context) => {
    if (context) setOptimisticEnabled(context.previousEnabled)
  },
})
```

**Destructive variant** (from button.tsx line 22):
```tsx
// Red stop button uses "destructive" variant
<Button variant="destructive" onClick={() => mutation.mutate(false)}>Stop Bot</Button>
// Green start uses default or a custom green class via cn()
```

---

### `frontend/src/hooks/usePostFeed.ts` (hook, event-driven — no analog)

**Pattern:** RESEARCH.md Pattern 6 (browser native WebSocket with exponential backoff)

```tsx
import { useState, useEffect, useRef, useCallback } from "react"

type ConnectionStatus = "connected" | "reconnecting" | "disconnected"

export interface PostMessage {
  type: "post"
  id: number
  platform: string
  content: string
  posted_at: string
  is_filtered: boolean
  filter_reason: string | null
  signal: {
    sentiment: string
    confidence: number
    affected_tickers: string[]
    final_action: string
    reason_code: string | null
  } | null
}

export function usePostFeed() {
  const [posts, setPosts] = useState<PostMessage[]>([])
  const [status, setStatus] = useState<ConnectionStatus>("disconnected")
  const wsRef = useRef<WebSocket | null>(null)
  const retryDelayRef = useRef(1000)

  const connect = useCallback(() => {
    const ws = new WebSocket("ws://localhost:8000/ws/feed")
    wsRef.current = ws

    ws.onopen = () => { setStatus("connected"); retryDelayRef.current = 1000 }
    ws.onmessage = (event) => {
      const msg: PostMessage = JSON.parse(event.data)
      setPosts(prev => [msg, ...prev])  // prepend — newest at top
    }
    ws.onclose = () => {
      setStatus("reconnecting")
      const delay = Math.min(retryDelayRef.current, 30_000)
      retryDelayRef.current = delay * 2
      setTimeout(connect, delay)
    }
  }, [])

  useEffect(() => {
    connect()
    return () => { wsRef.current?.close() }
  }, [connect])

  return { posts, status }
}
```

---

### `frontend/src/pages/FeedPage.tsx` (page component, event-driven)

**Pattern:** TanStack Query v5 `useQuery` for initial load + `usePostFeed` hook for live updates

**useQuery pattern** (from `frontend/src/main.tsx` — QueryClient already configured):
```tsx
import { useQuery } from "@tanstack/react-query"

const { data: initialPosts, isPending } = useQuery({  // v5: isPending not isLoading
  queryKey: ["posts"],
  queryFn: () => fetch("/posts?limit=50").then(r => r.json()),
})
```

Note: TanStack Query v5 API differences from v4 per RESEARCH.md Pitfall 6:
- `isLoading` → `isPending`
- `cacheTime` → `gcTime`
- `keepPreviousData` → `placeholderData`

---

### `frontend/src/pages/PortfolioPage.tsx` (page component, request-response)

**Pattern:** TanStack Query `useQuery` with `refetchInterval`

```tsx
const { data, isPending, isError } = useQuery({
  queryKey: ["portfolio"],
  queryFn: () => fetch("/portfolio").then(r => r.json()),
  staleTime: 10_000,
  refetchInterval: 15_000,  // poll every 15s — live Alpaca data
})
```

**Skeleton loading** (shadcn Skeleton component):
```tsx
import { Skeleton } from "@/components/ui/skeleton"

if (isPending) return <div className="space-y-4"><Skeleton className="h-24 w-full" /></div>
```

---

### `frontend/src/pages/SettingsPage.tsx` (page component, CRUD)

**Pattern:** Controlled inputs with local state; PATCH mutation on save

**Risk settings fetch** (same useQuery pattern as PortfolioPage):
```tsx
const { data: riskSettings } = useQuery({
  queryKey: ["risk-settings"],
  queryFn: () => fetch("/settings/risk").then(r => r.json()),
})
```

**Watchlist mutation** (POST + DELETE pattern):
```tsx
const queryClient = useQueryClient()

const addMutation = useMutation({
  mutationFn: (symbol: string) =>
    fetch("/watchlist", {
      method: "POST",
      body: JSON.stringify({ symbol }),
      headers: { "Content-Type": "application/json" },
    }).then(r => r.json()),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ["watchlist"] }),
})

const removeMutation = useMutation({
  mutationFn: (symbol: string) =>
    fetch(`/watchlist/${symbol}`, { method: "DELETE" }).then(r => r.json()),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ["watchlist"] }),
})
```

---

### `frontend/src/components/TradeRow.tsx` (component, CRUD)

**Pattern:** shadcn Collapsible + Table (RESEARCH.md Pattern 7):

```tsx
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { TableRow, TableCell } from "@/components/ui/table"
import { ChevronDown } from "lucide-react"

function TradeRow({ trade }: { trade: TradeWithAudit }) {
  return (
    <Collapsible asChild>
      <>
        <TableRow className="cursor-pointer">
          {/* summary columns */}
          <TableCell>
            <CollapsibleTrigger asChild>
              <button><ChevronDown className="h-4 w-4" /></button>
            </CollapsibleTrigger>
          </TableCell>
        </TableRow>
        <CollapsibleContent asChild>
          <TableRow className="bg-secondary/50">
            <TableCell colSpan={6}>{/* full audit detail */}</TableCell>
          </TableRow>
        </CollapsibleContent>
      </>
    </Collapsible>
  )
}
```

---

### `frontend/src/lib/api.ts` (utility, request-response)

**Analog:** `frontend/src/lib/utils.ts` — typed export module structure

**Utility module pattern** (analog lines 1-6):
```ts
import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

**Apply as typed fetch wrappers:**
```ts
const BASE = ""  // same origin in prod; Vite CORS header in dev

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

export const api = {
  posts: (limit = 50, offset = 0) => apiFetch<PostItem[]>(`/posts?limit=${limit}&offset=${offset}`),
  trades: () => apiFetch<TradeItem[]>("/trades"),
  portfolio: () => apiFetch<PortfolioData>("/portfolio"),
  watchlist: () => apiFetch<WatchlistItem[]>("/watchlist"),
  riskSettings: () => apiFetch<RiskSettings>("/settings/risk"),
  alerts: () => apiFetch<AlertItem[]>("/alerts"),
}
```

---

## Shared Patterns

### Pattern: `from __future__ import annotations`
**Source:** Every backend file in the project — `trumptrade/risk_guard/router.py` line 1, `trumptrade/trading/router.py` line 1, `trumptrade/analysis/worker.py` line 1
**Apply to:** All new Python backend files (`ws.py`, `router.py`, `watchlist.py`)
```python
from __future__ import annotations
```

### Pattern: Logger per module
**Source:** `trumptrade/risk_guard/router.py` line 13, `trumptrade/trading/router.py` line 6
**Apply to:** All new Python backend files
```python
import logging
logger = logging.getLogger(__name__)
```

### Pattern: `AsyncSessionLocal` for background jobs; `Depends(get_db)` for request handlers
**Source:** `trumptrade/risk_guard/router.py` lines 47-54 (background-style: AsyncSessionLocal) vs `trumptrade/core/db.py` lines 36-49 (request: get_db)
**Apply to:**
- Dashboard router endpoints → use `AsyncSessionLocal()` (established pattern in project — all existing routers use this even in FastAPI endpoints rather than `Depends`)
- The `get_db` dependency is defined but risk_guard/router.py does NOT use it — it uses `AsyncSessionLocal` directly. Copy this pattern.

```python
# Established pattern — all existing routers use AsyncSessionLocal, not Depends(get_db)
async with AsyncSessionLocal() as session:
    result = await session.execute(select(Post).order_by(Post.created_at.desc()).limit(50))
    posts = result.scalars().all()
```

### Pattern: Local imports inside function bodies to avoid circular imports
**Source:** `trumptrade/core/app.py` lines 88-97, `trumptrade/analysis/worker.py` lines 283-285
**Apply to:** All new router imports in `create_app()`, broadcast import in `worker.py`
```python
# In create_app():
from trumptrade.dashboard import dashboard_router, watchlist_router, ws_router  # local import

# In analysis/worker.py (inside loop body):
from trumptrade.dashboard.ws import manager  # local import — singleton instance
```

### Pattern: Pydantic `Field` validation on inputs
**Source:** `trumptrade/risk_guard/router.py` lines 37-42, `trumptrade/trading/router.py` lines 17-19
**Apply to:** `WatchlistAdd` in `watchlist.py`
```python
class WatchlistAdd(BaseModel):
    symbol: str = Field(pattern=r"^[A-Z]{1,5}$")  # prevents SQL injection via ticker input
```

### Pattern: TanStack Query v5 — `isPending` (not `isLoading`)
**Source:** `frontend/src/main.tsx` line 8 — v5 already installed (`@tanstack/react-query`)
**Apply to:** All frontend pages using `useQuery`
```tsx
const { data, isPending, isError } = useQuery(...)
if (isPending) return <Skeleton ... />
```

### Pattern: `@/` path alias for frontend imports
**Source:** `frontend/src/components/ui/button.tsx` line 3: `import { cn } from "@/lib/utils"`
**Apply to:** All frontend component and page imports
```tsx
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
```

### Pattern: shadcn `cn()` for conditional class merging
**Source:** `frontend/src/lib/utils.ts` lines 1-6; used in `button.tsx` line 53
**Apply to:** All components with conditional CSS classes (NavLink active state, sentiment badge colors)
```tsx
import { cn } from "@/lib/utils"
className={cn("base-class", isActive && "active-class", isError && "error-class")}
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `frontend/src/router.tsx` | route config | — | No React Router usage exists in codebase yet; use RESEARCH.md Pattern 5 |
| `frontend/src/hooks/usePostFeed.ts` | hook | event-driven | No WebSocket or hook patterns exist in frontend; use RESEARCH.md Pattern 6 |

---

## Metadata

**Analog search scope:** `trumptrade/` (all Python backend files), `frontend/src/` (all TS/TSX files)
**Files scanned:** 27 Python files, 6 frontend files
**Pattern extraction date:** 2026-04-21

**Key constraints enforced:**
- Never use `alpaca-trade-api` — all Alpaca calls use `alpaca-py` `TradingClient` via `run_in_executor`
- Never use `requests` — no frontend `fetch` wrapper uses `requests`; backend uses `AsyncSessionLocal` (httpx not needed for dashboard endpoints)
- `AsyncSessionLocal` (not `Depends(get_db)`) is the established pattern in all existing routers
- `from __future__ import annotations` on every new `.py` file
- Local imports inside function bodies for any cross-package import risk
- TanStack Query v5 API: `isPending` not `isLoading`, `gcTime` not `cacheTime`
- shadcn components installed via `npx shadcn add` from `frontend/` — `components.json` already set to `base-nova` style
