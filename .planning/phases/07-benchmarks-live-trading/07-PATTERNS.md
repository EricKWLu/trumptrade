# Phase 7: Benchmarks + Live Trading - Pattern Map

**Mapped:** 2026-04-23
**Files analyzed:** 10 new/modified files
**Analogs found:** 9 / 10 (BenchmarkChart has no codebase analog — new library)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `trumptrade/benchmarks/__init__.py` | package-init | batch | `trumptrade/analysis/__init__.py` | exact |
| `trumptrade/benchmarks/job.py` | worker | batch + file-I/O (Alpaca API) | `trumptrade/analysis/worker.py` | role-match |
| `trumptrade/benchmarks/router.py` | controller | request-response (CRUD read) | `trumptrade/dashboard/router.py` | exact |
| `alembic/versions/006_benchmark_unique.py` | migration | — | `alembic/versions/005_risk_settings.py` | exact |
| `trumptrade/trading/router.py` (patch) | controller | request-response | `trumptrade/trading/router.py` (kill-switch) | self |
| `trumptrade/core/app.py` (patch) | config | — | `trumptrade/core/app.py` (existing pattern) | self |
| `frontend/src/pages/BenchmarksPage.tsx` | page component | request-response | `frontend/src/pages/PortfolioPage.tsx` | role-match |
| `frontend/src/components/BenchmarkChart.tsx` | sub-component | transform | no codebase analog | none |
| `frontend/src/components/LiveModeModal.tsx` | modal component | request-response | `frontend/src/pages/SettingsPage.tsx` (mutation pattern) | partial |
| `frontend/src/components/AppShell.tsx` (patch) | shell component | request-response | `frontend/src/components/AppShell.tsx` (self) | self |
| `frontend/src/pages/SettingsPage.tsx` (patch) | page component | request-response | `frontend/src/pages/SettingsPage.tsx` (self) | self |
| `frontend/src/lib/api.ts` (patch) | utility | request-response | `frontend/src/lib/api.ts` (self) | self |

---

## Pattern Assignments

### `trumptrade/benchmarks/__init__.py` (package-init, batch)

**Analog:** `trumptrade/analysis/__init__.py`

**Full file pattern** (lines 1-32):
```python
from __future__ import annotations

"""Benchmarks package — shadow portfolio snapshot job + APScheduler registration (Phase 7)."""

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from trumptrade.benchmarks.job import benchmark_snapshot_job


def register_benchmark_jobs(scheduler: AsyncIOScheduler) -> None:
    """Register the daily EOD benchmark snapshot job.

    Called from create_app() via local import to avoid circular imports.
    CronTrigger fires Mon-Fri at 4:01pm ET (1 min after market close).
    """
    from apscheduler.triggers.cron import CronTrigger
    scheduler.add_job(
        benchmark_snapshot_job,
        trigger=CronTrigger(
            day_of_week="mon-fri",
            hour=16,
            minute=1,
            timezone="US/Eastern",
        ),
        id="benchmarks_snapshot",
        replace_existing=True,
        misfire_grace_time=300,   # 5 min grace — cron jobs may miss briefly
        coalesce=True,
        max_instances=1,
    )


__all__ = ["register_benchmark_jobs"]
```

**Key difference from `analysis/__init__.py`:** Uses `CronTrigger` import (not interval trigger). The trigger is imported locally inside the function body to mirror the pattern of keeping non-essential imports deferred. The job id `"benchmarks_snapshot"` must be stable for `replace_existing=True` to work across hot-reloads.

---

### `trumptrade/benchmarks/job.py` (worker, batch + Alpaca API)

**Analog:** `trumptrade/analysis/worker.py` for overall structure; `trumptrade/dashboard/router.py` for `run_in_executor` pattern.

**Imports pattern** — copy from `analysis/worker.py` lines 1-12 + `dashboard/router.py` lines 1-20:
```python
from __future__ import annotations

import asyncio
import json
import logging
import random
from datetime import date, datetime, timedelta
from math import floor

from sqlalchemy import select

from trumptrade.core.db import AsyncSessionLocal
from trumptrade.core.models import AppSettings, ShadowPortfolioSnapshot, Watchlist

logger = logging.getLogger(__name__)

STARTING_NAV = 100_000.0   # module-level constant — never stored in settings
```

**`_read_setting` helper** — copy verbatim from `trumptrade/dashboard/router.py` lines 48-55:
```python
async def _read_setting(key: str, default: str) -> str:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AppSettings.value).where(AppSettings.key == key)
        )
        val = result.scalar_one_or_none()
        return val if val is not None else default
```

**`run_in_executor` pattern** — copy from `trumptrade/dashboard/router.py` lines 194-196:
```python
loop = asyncio.get_running_loop()
account = await loop.run_in_executor(None, client.get_account)
positions = await loop.run_in_executor(None, client.get_all_positions)
```

**Adapt for StockHistoricalDataClient (sync SDK, same constraint):**
```python
loop = asyncio.get_running_loop()
spy_close = await loop.run_in_executor(None, _fetch_close_sync, settings.alpaca_api_key, settings.alpaca_secret_key, "SPY", today)
qqq_close = await loop.run_in_executor(None, _fetch_close_sync, settings.alpaca_api_key, settings.alpaca_secret_key, "QQQ", today)
```

**Dedup guard pattern** — check before insert (no unique constraint exists yet; migration 006 adds it, but job must also guard for safety):
```python
# Pattern from analysis/worker.py early-exit:
existing = await session.execute(
    select(ShadowPortfolioSnapshot.id)
    .where(ShadowPortfolioSnapshot.portfolio_name == portfolio_name)
    .where(ShadowPortfolioSnapshot.snapshot_date == today)
)
if existing.scalar_one_or_none() is not None:
    logger.info("Snapshot already exists for %s on %s — skipping", portfolio_name, today)
    return
```

**DB write pattern** — copy from `analysis/worker.py` lines 276-278 (session.add + commit):
```python
async with AsyncSessionLocal() as session:
    session.add(ShadowPortfolioSnapshot(
        portfolio_name=portfolio_name,
        snapshot_date=today,
        nav_value=nav,
        cash=cash,
        positions_json=json.dumps(positions),
    ))
    await session.commit()
```

**Error handling pattern** — copy from `analysis/worker.py` lines 225-237 (try/except with log + continue):
```python
try:
    spy_close = await loop.run_in_executor(...)
except Exception as exc:
    logger.error("benchmark_snapshot_job: Alpaca API error: %s", exc)
    return   # abort whole tick — do not write partial snapshots
```

---

### `trumptrade/benchmarks/router.py` (controller, request-response CRUD read)

**Analog:** `trumptrade/dashboard/router.py`

**Imports pattern** (copy from `dashboard/router.py` lines 1-21):
```python
from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from trumptrade.core.db import AsyncSessionLocal
from trumptrade.core.models import ShadowPortfolioSnapshot

logger = logging.getLogger(__name__)

router = APIRouter()
```

**DB read + response pattern** (copy from `dashboard/router.py` lines 60-94 — get_posts structure):
```python
@router.get("/benchmarks")
async def get_benchmarks() -> list[dict]:
    """Return all shadow portfolio snapshots normalized to % return from start.

    Returns [{date, bot, spy, qqq, random}, ...] sorted by date ascending.
    All values are percentage returns (e.g. 1.23 means +1.23%).
    """
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ShadowPortfolioSnapshot)
                .order_by(ShadowPortfolioSnapshot.snapshot_date.asc())
            )
            rows = list(result.scalars().all())
    except Exception as exc:
        logger.error("get_benchmarks: DB error: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to read benchmark data")

    if not rows:
        return []

    # Pivot and normalize — compute % return server-side (D-01, RESEARCH Pattern 4)
    # ... (pivot logic here)
    return out
```

**`_read_setting` helper** — copy verbatim from `dashboard/router.py` lines 48-55 (same pattern used throughout codebase):
```python
async def _read_setting(key: str, default: str) -> str:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AppSettings.value).where(AppSettings.key == key)
        )
        val = result.scalar_one_or_none()
        return val if val is not None else default
```

---

### `alembic/versions/006_benchmark_unique.py` (migration)

**Analog:** `alembic/versions/005_risk_settings.py`

**Full file pattern** (copy header from `005_risk_settings.py` lines 1-23, adapt body):
```python
"""benchmark_unique_index

Revision ID: 006
Revises: 005
Create Date: 2026-04-23

Adds UNIQUE INDEX on (portfolio_name, snapshot_date) in shadow_portfolio_snapshots.
Uses CREATE UNIQUE INDEX IF NOT EXISTS — safe on first run and after re-run.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "006"
down_revision: Union[str, Sequence[str], None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_shadow_portfolio_unique "
        "ON shadow_portfolio_snapshots (portfolio_name, snapshot_date)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_shadow_portfolio_unique")
```

**Key pattern:** Raw SQL via `op.execute()` — same approach used in `005_risk_settings.py` for INSERT OR IGNORE. `IF NOT EXISTS` / `IF EXISTS` guards make it idempotent (safe for re-runs).

---

### `trumptrade/trading/router.py` patch — add `POST /trading/set-mode`

**Analog:** `trumptrade/trading/router.py` kill-switch endpoint (lines 27-59, self-analog)

**Pydantic model pattern** (copy from `trading/router.py` lines 27-34 — KillSwitch models):
```python
class SetModeRequest(BaseModel):
    mode: str        # "paper" | "live"
    confirmed: bool  # must be True — extra safety gate (D-09)

class SetModeResponse(BaseModel):
    trading_mode: str
    ok: bool
```

**Endpoint pattern** (copy from `trading/router.py` lines 50-59 — kill_switch handler):
```python
@router.post("/set-mode", response_model=SetModeResponse)
async def set_trading_mode(body: SetModeRequest) -> SetModeResponse:
    """Write trading_mode to app_settings (D-12).

    Requires mode in {"paper", "live"} and confirmed=True.
    Changes take effect immediately — executor reads trading_mode per-request.
    """
    if body.mode not in ("paper", "live"):
        raise HTTPException(status_code=422, detail="mode must be 'paper' or 'live'")
    if not body.confirmed:
        raise HTTPException(status_code=422, detail="confirmed must be true")

    from sqlalchemy import update
    from trumptrade.core.db import AsyncSessionLocal
    from trumptrade.core.models import AppSettings
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(AppSettings)
            .where(AppSettings.key == "trading_mode")
            .values(value=body.mode)
        )
        await session.commit()
    logger.info("Trading mode changed to %s", body.mode)
    return SetModeResponse(trading_mode=body.mode, ok=True)
```

**app_settings write pattern** (verified from `risk_guard/router.py` lines 96-103):
```python
async with AsyncSessionLocal() as session:
    await session.execute(
        update(AppSettings)
        .where(AppSettings.key == key)
        .values(value=str(value))
    )
    await session.commit()
```

**Local imports** — `from sqlalchemy import update` is added inside the function body, consistent with `trading/router.py` lines 70-74 where `select` is imported locally.

---

### `trumptrade/core/app.py` patch — include benchmarks router + register jobs

**Analog:** `trumptrade/core/app.py` (self — existing Phase 4 pattern, lines 113-118)

**Router registration pattern** (copy from lines 105-110):
```python
# ── Phase 7: benchmarks router ───────────────────────────────────────────────
from trumptrade.benchmarks.router import router as benchmarks_router  # local import
app.include_router(benchmarks_router, tags=["benchmarks"])
```

**Job registration pattern** (copy from lines 117-118):
```python
# ── Phase 7: benchmark snapshot jobs ────────────────────────────────────────
from trumptrade.benchmarks import register_benchmark_jobs  # local import
register_benchmark_jobs(scheduler)
```

Place router inclusion after the Phase 6 dashboard block. Place job registration after the Phase 4 analysis block. Both use local imports with comments explaining the phase — established pattern throughout `app.py`.

---

### `frontend/src/pages/BenchmarksPage.tsx` (page component, request-response)

**Analog:** `frontend/src/pages/PortfolioPage.tsx`

**Imports pattern** (copy from `PortfolioPage.tsx` lines 1-15, adapt):
```tsx
import { useQuery } from "@tanstack/react-query"
import { Skeleton } from "@/components/ui/skeleton"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { api } from "@/lib/api"
import type { BenchmarkPoint } from "@/lib/api"
// + Recharts imports (see BenchmarkChart pattern below)
```

**`useQuery` pattern** (copy from `PortfolioPage.tsx` lines 130-135, adapt):
```tsx
const { data, isPending, isError } = useQuery({
  queryKey: ["benchmarks"],
  queryFn: () => api.benchmarks(),
  staleTime: 300_000,       // 5 minutes — updates only at market close
  refetchInterval: 300_000,
})
```

**Loading skeleton pattern** (copy from `PortfolioPage.tsx` lines 118-127 — `LoadingSkeletons` component structure):
```tsx
function LoadingSkeletons() {
  return (
    <div className="p-6 space-y-4">
      <Skeleton className="h-6 w-48" />
      <Skeleton className="h-[400px] w-full rounded-lg" />
      <div className="flex justify-center gap-8 mt-4">
        {["Bot", "SPY", "QQQ", "Random"].map(s => (
          <Skeleton key={s} className="h-4 w-16" />
        ))}
      </div>
    </div>
  )
}
```

**Empty state pattern** (copy from `PortfolioPage.tsx` lines 69-76 — `PositionsTable` empty branch):
```tsx
<div className="text-center py-12">
  <p className="text-xl font-semibold mb-2">No benchmark data yet</p>
  <p className="text-sm text-muted-foreground">
    Check back after today's market close (4:01 PM ET).
    <br />
    The bot, SPY, QQQ, and random baseline all start together on the first snapshot.
  </p>
</div>
```

**Error state pattern** (copy from `PortfolioPage.tsx` lines 139-148):
```tsx
<div className="p-6">
  <Alert variant="destructive">
    <AlertDescription>
      <strong>Benchmarks unavailable.</strong>{" "}
      Unable to load benchmark data. Check that the backend is running and try again.
    </AlertDescription>
  </Alert>
</div>
```

**Page wrapper pattern** (copy from `PortfolioPage.tsx` lines 152-158):
```tsx
return (
  <div className="p-6">
    <h1 className="text-xl font-semibold mb-6">Benchmarks</h1>
    {data.length === 0 ? <EmptyState /> : <BenchmarkChart data={data} />}
  </div>
)
```

---

### `frontend/src/components/BenchmarkChart.tsx` (sub-component, transform — new pattern, no analog)

**No codebase analog.** Use RESEARCH.md Pattern 5 and UI-SPEC.md Section 2d directly.

**Recharts imports** (from RESEARCH.md lines 319-326):
```tsx
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ReferenceLine,
} from "recharts"
```

**Full chart pattern** (from 07-UI-SPEC.md lines 253-293 — authoritative, verified against recharts 3.8.1):
```tsx
<ResponsiveContainer width="100%" height={400}>
  <LineChart data={data} margin={{ top: 8, right: 24, left: 0, bottom: 8 }}>
    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
    <XAxis
      dataKey="date"
      tick={{ fontSize: 12, fill: "hsl(var(--muted-foreground))" }}
      tickFormatter={(v: string) => v.slice(5)}
      minTickGap={40}
    />
    <YAxis
      tickFormatter={(v: number) => `${v.toFixed(1)}%`}
      tick={{ fontSize: 12, fill: "hsl(var(--muted-foreground))" }}
      label={{ value: "Return since start (%)", angle: -90, position: "insideLeft", offset: 12,
               style: { fontSize: 12, fill: "hsl(var(--muted-foreground))" } }}
    />
    <ReferenceLine y={0} stroke="hsl(var(--muted-foreground))" strokeDasharray="4 4" />
    <Tooltip
      formatter={(value: number, name: string) => [`${value.toFixed(2)}%`, name.toUpperCase()]}
      labelFormatter={(label: string) => `Date: ${label}`}
      contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))",
                      borderRadius: "0.5rem", fontSize: 12 }}
    />
    <Legend verticalAlign="bottom" wrapperStyle={{ paddingTop: 16, fontSize: 12 }} />
    <Line type="monotone" dataKey="bot"    stroke="#3b82f6" dot={false} strokeWidth={2} name="Bot" />
    <Line type="monotone" dataKey="spy"    stroke="#22c55e" dot={false} strokeWidth={2} name="SPY" />
    <Line type="monotone" dataKey="qqq"    stroke="#a855f7" dot={false} strokeWidth={2} name="QQQ" />
    <Line type="monotone" dataKey="random" stroke="#f59e0b" dot={false} strokeWidth={2} name="Random" />
  </LineChart>
</ResponsiveContainer>
```

**Critical:** SVG elements do not accept Tailwind classes. All visual properties (`fill`, `fontSize`, `background`) must be inline style strings or CSS variable strings. `hsl(var(--border))` etc. are CSS variable strings — they resolve correctly at runtime.

---

### `frontend/src/components/LiveModeModal.tsx` (modal component, request-response)

**Analog:** `frontend/src/pages/SettingsPage.tsx` — `useMutation` + error state pattern (lines 149-158, 203-221); no modal analog exists.

**Imports pattern** (copy from `SettingsPage.tsx` lines 1-11, extend):
```tsx
import { useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { api } from "@/lib/api"
```

**`useMutation` + error state pattern** (copy from `SettingsPage.tsx` lines 149-158):
```tsx
const queryClient = useQueryClient()
const [error, setError] = useState<string | null>(null)

const modeMutation = useMutation({
  mutationFn: (mode: "paper" | "live") => api.setMode(mode),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ["portfolio-mode"] })
    onClose()
  },
  onError: () => setError("Failed to switch mode. Try again."),
})
```

**Typed confirmation pattern** (new — no analog; use RESEARCH.md Pattern 7):
```tsx
const [input, setInput] = useState("")
const targetPhrase = isLive ? "ENABLE PAPER TRADING" : "ENABLE LIVE TRADING"
const targetMode: "paper" | "live" = isLive ? "paper" : "live"
const isMatch = input === targetPhrase   // exact case-sensitive match (D-09)
```

**Error display pattern** (copy from `SettingsPage.tsx` lines 214-218):
```tsx
{error && (
  <p className="text-sm text-destructive">{error}</p>
)}
```

**Inline error placement:** Below the Input, above DialogFooter — matches SettingsPage input error pattern (`SettingsPage.tsx` lines 107-109).

**Input reset on re-open:** Pass `key={open ? "open" : "closed"}` or clear in `onOpenChange` — standard React unmount/remount trick. No codebase analog; use `key` prop approach.

---

### `frontend/src/components/AppShell.tsx` patches

**Analog:** `frontend/src/components/AppShell.tsx` (self)

**Nav item addition** (insert into `NAV_ITEMS` array, `AppShell.tsx` lines 11-16):
```tsx
import { Zap, BarChart2, TrendingUp, Settings, LineChart } from "lucide-react"

const NAV_ITEMS = [
  { to: "/", end: true, icon: Zap, label: "Feed" },
  { to: "/trades", end: false, icon: BarChart2, label: "Trades" },
  { to: "/portfolio", end: false, icon: TrendingUp, label: "Portfolio" },
  { to: "/benchmarks", end: false, icon: LineChart, label: "Benchmarks" },   // NEW
  { to: "/settings", end: false, icon: Settings, label: "Settings" },
]
```

**LIVE banner pattern** (insert as first child of `<main>`, `AppShell.tsx` lines 88-90):
```tsx
// Add useQuery for mode — TanStack Query deduplicates the ["portfolio-mode"] key automatically
const { data: modeData } = useQuery({
  queryKey: ["portfolio-mode"],
  queryFn: () => api.portfolio(),
  staleTime: 30_000,
  refetchInterval: 60_000,
})
const mode = modeData?.trading_mode ?? "paper"

// In JSX <main>:
<main className="flex-1 overflow-auto">
  {mode === "live" && (
    <div className="bg-red-500/10 border-b border-red-500/30 px-4 py-2 text-center text-red-400 text-sm font-semibold tracking-wide">
      LIVE TRADING ACTIVE — real money at risk
    </div>
  )}
  <Outlet />
</main>
```

**Note:** `TradingModeBadge` already fetches `["portfolio-mode"]` — adding the same query in `AppShell` is safe. TanStack Query v5 deduplicates identical query keys (`AppShell.tsx` comment in UI-SPEC line 483).

---

### `frontend/src/pages/SettingsPage.tsx` patch — add Trading Mode section

**Analog:** `SettingsPage.tsx` (self) — `RiskControlsSection` Card structure (lines 179-221)

**Card + Badge pattern** (copy from `SettingsPage.tsx` lines 179-185 — Card structure, extend):
```tsx
<Card>
  <CardHeader>
    <CardTitle className="text-xl font-semibold">Trading Mode</CardTitle>
    <p className="text-sm text-muted-foreground">
      Switch between paper (simulated) and live (real money) trading.
    </p>
  </CardHeader>
  <CardContent className="space-y-4">
    <div className="flex items-center gap-3">
      <span className="text-sm font-semibold text-foreground">Current mode:</span>
      {mode === "live"
        ? <Badge className="bg-red-500/10 text-red-400 border border-red-500/20 font-semibold text-xs">LIVE</Badge>
        : <Badge className="bg-yellow-500/10 text-yellow-400 border border-yellow-500/20 font-semibold text-xs">PAPER</Badge>
      }
    </div>
    <Button
      variant={mode === "live" ? "outline" : "destructive"}
      onClick={() => setModalOpen(true)}
    >
      {mode === "live" ? "Switch to PAPER Trading" : "Switch to LIVE Trading"}
    </Button>
    <LiveModeModal isLive={mode === "live"} open={modalOpen} onClose={() => setModalOpen(false)} />
  </CardContent>
</Card>
```

**Badge inline class pattern** (copy from `AppShell.tsx` lines 29-40 — `TradingModeBadge` component).

**Mode source:** Read from existing `["portfolio-mode"]` query (already in AppShell via `TradingModeBadge`). In SettingsPage, add:
```tsx
const { data: portfolioData } = useQuery({
  queryKey: ["portfolio-mode"],
  queryFn: () => api.portfolio(),
  staleTime: 30_000,
})
const mode = portfolioData?.trading_mode ?? "paper"
```

**Section placement:** Add after `<RiskControlsSection />` inside the `space-y-8` div (`SettingsPage.tsx` lines 229-234).

---

### `frontend/src/lib/api.ts` patch — add `benchmarks()` and `setMode()`

**Analog:** `frontend/src/lib/api.ts` (self)

**Type definition pattern** (copy from `api.ts` lines 76-83 — `PortfolioData` interface):
```ts
export interface BenchmarkPoint {
  date: string    // "YYYY-MM-DD"
  bot: number     // % return, e.g. 1.23 (not 0.0123)
  spy: number
  qqq: number
  random: number
}

export interface SetModeResponse {
  trading_mode: string
  ok: boolean
}
```

**API method pattern** (copy from `api.ts` lines 160-165 — `toggleKillSwitch`):
```ts
benchmarks: () =>
  apiFetch<BenchmarkPoint[]>("/benchmarks"),

setMode: (mode: "paper" | "live") =>
  apiFetch<SetModeResponse>("/trading/set-mode", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode, confirmed: true }),
  }),
```

Add `BenchmarkPoint` and `SetModeResponse` in the `// ── Types ──` block. Add `benchmarks` and `setMode` in the `api` object.

---

## Shared Patterns

### `_read_setting` Helper (DB read)
**Source:** `trumptrade/dashboard/router.py` lines 48-55 AND `trumptrade/risk_guard/router.py` lines 47-54 (identical in both)
**Apply to:** `trumptrade/benchmarks/router.py`, `trumptrade/benchmarks/job.py`
```python
async def _read_setting(key: str, default: str) -> str:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AppSettings.value).where(AppSettings.key == key)
        )
        val = result.scalar_one_or_none()
        return val if val is not None else default
```

### `run_in_executor` for Sync SDK Calls
**Source:** `trumptrade/dashboard/router.py` lines 194-196
**Apply to:** `trumptrade/benchmarks/job.py` (StockHistoricalDataClient calls)
```python
loop = asyncio.get_running_loop()
account = await loop.run_in_executor(None, client.get_account)
```

### AppSettings Write (UPDATE)
**Source:** `trumptrade/risk_guard/router.py` lines 96-103
**Apply to:** `trumptrade/trading/router.py` set-mode endpoint
```python
async with AsyncSessionLocal() as session:
    await session.execute(
        update(AppSettings)
        .where(AppSettings.key == key)
        .values(value=str(value))
    )
    await session.commit()
```

### Local Import Pattern in `create_app()`
**Source:** `trumptrade/core/app.py` lines 98-118 (every router and job uses local import)
**Apply to:** All `app.py` patches — benchmarks router and job registration
```python
from trumptrade.benchmarks.router import router as benchmarks_router  # local import
app.include_router(benchmarks_router, tags=["benchmarks"])
```

### TanStack Query `useQuery` with `staleTime` + `refetchInterval`
**Source:** `frontend/src/pages/PortfolioPage.tsx` lines 130-135
**Apply to:** `BenchmarksPage.tsx`
```tsx
const { data, isPending, isError } = useQuery({
  queryKey: ["benchmarks"],
  queryFn: () => api.benchmarks(),
  staleTime: 300_000,
  refetchInterval: 300_000,
})
```

### `useMutation` + `queryClient.invalidateQueries`
**Source:** `frontend/src/pages/SettingsPage.tsx` lines 26-45 (addMutation pattern)
**Apply to:** `LiveModeModal.tsx`
```tsx
const modeMutation = useMutation({
  mutationFn: ...,
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ["portfolio-mode"] })
    onClose()
  },
  onError: () => setError("Failed to switch mode. Try again."),
})
```

### Page Layout Wrapper
**Source:** `frontend/src/pages/PortfolioPage.tsx` lines 152-154 AND `frontend/src/pages/SettingsPage.tsx` line 228
**Apply to:** `BenchmarksPage.tsx`
```tsx
<div className="p-6">
  <h1 className="text-xl font-semibold mb-6">Benchmarks</h1>
  {/* content */}
</div>
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `frontend/src/components/BenchmarkChart.tsx` | sub-component | transform | No charting library exists in codebase yet. Use RESEARCH.md Pattern 5 and 07-UI-SPEC.md Section 2d directly. recharts 3.8.1 must be installed first (`npm install recharts react-is`). |

---

## Metadata

**Analog search scope:** `trumptrade/` (all Python packages), `frontend/src/` (all TSX/TS files), `alembic/versions/`
**Files read:** 13 source files
**Pattern extraction date:** 2026-04-23

**Critical pre-conditions for executor (Wave 0):**
1. `cd frontend && npm install recharts react-is` — BenchmarkChart requires recharts 3.8.1
2. `cd frontend && npx shadcn add dialog` — LiveModeModal requires `@/components/ui/dialog`
3. Run `alembic upgrade 006` after migration file is created — adds unique constraint before job runs
