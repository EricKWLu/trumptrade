# Phase 7: Benchmarks + Live Trading - Research

**Researched:** 2026-04-23
**Domain:** Shadow portfolio NAV math, Alpaca historical bars API, Recharts line chart, APScheduler CronTrigger, live mode unlock UX
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Y-axis shows % return from start — all lines begin at 0% on the first snapshot date
- **D-02:** Time range is since bot start (full history always visible). No user-selectable range for v1.
- **D-03:** All 4 lines on one chart: Bot, SPY, QQQ, Random. Recharts. Legend below chart.
- **D-04:** Chart lives on a new Benchmarks page (new sidebar nav item)
- **D-05:** Shadow portfolios start from first app run — no historical backfill. Use existing `ShadowPortfolioSnapshot` model as-is.
- **D-06:** NAV updated daily at market close via APScheduler CronTrigger(hour=16, minute=1, timezone='US/Eastern')
- **D-07:** SPY/QQQ use Alpaca historical bars API (StockHistoricalDataClient) for daily closing prices
- **D-08:** Random baseline: random buy/sell one watchlist ticker at close (50/50, mirrors max_position_size_pct). Skip day if watchlist empty.
- **D-09:** Live mode unlock: type "ENABLE LIVE TRADING" + Confirm modal
- **D-10:** Paper mode switch: type "ENABLE PAPER TRADING" + same deliberateness
- **D-11:** Live mode: red LIVE badge in sidebar + red banner on every page. Cannot be missed.
- **D-12:** New POST /trading/set-mode endpoint writes trading_mode to app_settings

### Claude's Discretion
- Recharts line chart styling (colors, dot size, tooltip format, grid lines)
- Exact random baseline algorithm tie-breaking (1 ticker in watchlist → always that ticker)
- Chart loading skeleton while data fetches
- Empty state when no snapshot data exists yet (first day)
- Whether Benchmarks page is sidebar nav item or tab within PortfolioPage (D-04 says sidebar nav item)

### Deferred Ideas (OUT OF SCOPE)
- User-selectable chart date range (1W / 1M / All buttons)
- Historical backfill from user-set start date
- Random baseline configuration exposed in Settings UI
- Congress member trade tracking
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TRADE-02 | User can switch to live trading via explicit two-step confirmation | POST /trading/set-mode + typed modal pattern; trading_mode already in app_settings |
| COMP-01 | System maintains SPY shadow portfolio (pure NAV math) for benchmark comparison | Alpaca StockHistoricalDataClient.get_stock_bars() + ShadowPortfolioSnapshot model |
| COMP-02 | System maintains QQQ shadow portfolio (pure NAV math) for benchmark comparison | Same as COMP-01, parallel portfolio_name="QQQ" |
| COMP-03 | System maintains random-trade baseline shadow portfolio | Python random module, watchlist read, max_position_size_pct from app_settings |
| COMP-04 | User can view comparison chart: bot vs SPY vs QQQ vs random | GET /benchmarks endpoint + Recharts LineChart with 4 series |
</phase_requirements>

---

## Summary

Phase 7 adds two independent capabilities: (1) three shadow portfolio benchmarks (SPY, QQQ, random) tracked daily via a CronTrigger job writing to the existing `ShadowPortfolioSnapshot` table, exposed on a new Benchmarks page via Recharts; and (2) a live trading mode unlock via a typed-confirmation modal calling a new `POST /trading/set-mode` endpoint.

The backend work is straightforward: a new `benchmarks/` package with one APScheduler job (CronTrigger 4:01pm ET Mon-Fri), one synchronous Alpaca `StockHistoricalDataClient` call wrapped in `run_in_executor` for SPY/QQQ closing prices, pure Python NAV math, and a `GET /benchmarks` endpoint that returns all snapshot rows normalized to % return from start. The `POST /trading/set-mode` endpoint is a near-copy of the kill-switch pattern — write `trading_mode` to `app_settings`.

The frontend work adds one new page (`BenchmarksPage` with a Recharts `LineChart`), a `LiveModeModal` component with exact-string validation, and augments `AppShell` with a red banner (when live) and a new nav item. Recharts 3.8.1 is installable and compatible with React 19. The `Dialog` shadcn component is not yet installed and must be added in Wave 0.

**Primary recommendation:** Build the `benchmarks/` package (job + router) as a single backend wave, then the frontend Benchmarks page and mode-switch UI as a second wave. The `ShadowPortfolioSnapshot` table has no unique constraint on `(portfolio_name, snapshot_date)` — the job must use upsert-or-skip logic to be idempotent.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Daily NAV snapshot job | API/Backend (APScheduler) | — | In-process scheduler; pure math + DB write |
| SPY/QQQ closing price fetch | API/Backend | — | alpaca-py is sync; run_in_executor in async context |
| Random baseline simulation | API/Backend | — | Stateful cash/positions tracked in positions_json |
| GET /benchmarks data endpoint | API/Backend | — | Reads ShadowPortfolioSnapshot, joins with bot NAV |
| Bot NAV source | API/Backend | Alpaca API | See "Bot NAV" section — use account equity from Alpaca |
| Recharts line chart | Browser/Client (React) | — | Pure frontend rendering of pre-computed % returns |
| % return normalization | API/Backend | — | Computed server-side; frontend only renders values |
| Mode-switch endpoint | API/Backend | — | Writes trading_mode to app_settings; same as kill-switch |
| Live mode modal | Browser/Client (React) | — | UI state machine; exact-string match is client-side |
| Red LIVE badge + banner | Browser/Client (React) | — | AppShell reads trading_mode from /portfolio response |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| alpaca-py | 0.43.2 [VERIFIED: installed] | StockHistoricalDataClient for SPY/QQQ bars | Project-mandated; already installed |
| APScheduler | 3.11.2 [VERIFIED: installed] | CronTrigger daily snapshot job | Already used for ingestion and analysis jobs |
| recharts | 3.8.1 [VERIFIED: npm registry] | LineChart with 4 series for benchmark comparison | Decision D-03; compatible with React 19 |
| react-is | 19.2.5 [VERIFIED: npm registry] | Recharts peer dependency | Required by recharts 3.x; not yet in frontend |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python stdlib `random` | built-in | 50/50 buy/sell decision, random ticker selection | Random baseline simulation |
| shadcn Dialog | via `npx shadcn add dialog` | Typed confirmation modal for mode switch | Live/paper mode toggle UX |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| recharts | Chart.js / Victory / Tremor | Recharts chosen per D-03; native React components, composable API |
| CronTrigger(mon-fri) | CronTrigger(daily) + market holiday check | Market-hours trigger is simpler; holiday gaps are acceptable (skip day, not a bug) |

**Installation:**
```bash
# Backend: already installed (alpaca-py, APScheduler)

# Frontend
cd frontend
npm install recharts react-is
npx shadcn add dialog
```

---

## Architecture Patterns

### System Architecture Diagram

```
APScheduler CronTrigger (4:01pm ET, Mon-Fri)
         │
         ▼
benchmark_snapshot_job()
    ├─► fetch_spy_qqq_close()
    │       └─► StockHistoricalDataClient.get_stock_bars() [sync, run_in_executor]
    │           Returns: bar.close for today (SPY), bar.close for today (QQQ)
    │           Returns: None on holiday/weekend (job skips, no snapshot written)
    │
    ├─► simulate_random_trade()
    │       └─► read watchlist from DB
    │           read max_position_size_pct from app_settings
    │           random.choice(watchlist) → ticker
    │           random.random() < 0.5 → buy or sell
    │           update positions_json, cash
    │           compute new NAV
    │
    ├─► write ShadowPortfolioSnapshot(portfolio_name="SPY", ...)
    ├─► write ShadowPortfolioSnapshot(portfolio_name="QQQ", ...)
    └─► write ShadowPortfolioSnapshot(portfolio_name="random", ...)
                │
                ▼
         shadow_portfolio_snapshots table

GET /benchmarks
    ├─► read all ShadowPortfolioSnapshot rows (SPY, QQQ, random) ordered by date
    ├─► read bot NAV per day from Alpaca account equity history OR app_settings snapshot
    └─► normalize all 4 series to % return from first shared date
        └─► return: [{date, bot, spy, qqq, random}, ...]

BenchmarksPage (React)
    ├─► useQuery(["benchmarks"]) → GET /benchmarks
    └─► <ResponsiveContainer>
            <LineChart data={chartData}>
              <Line dataKey="bot" stroke="#3b82f6" />
              <Line dataKey="spy" stroke="#22c55e" />
              <Line dataKey="qqq" stroke="#a855f7" />
              <Line dataKey="random" stroke="#f59e0b" />
            </LineChart>
        </ResponsiveContainer>

POST /trading/set-mode
    ├─► validate body: { mode: "live" | "paper", confirmed: true }
    ├─► write trading_mode to app_settings
    └─► return { trading_mode, ok }

LiveModeModal (React)
    ├─► state: { open, inputValue }
    ├─► exact match: inputValue === "ENABLE LIVE TRADING" (or PAPER)
    └─► on Confirm → POST /trading/set-mode → invalidate ["portfolio-mode"] query
```

### Recommended Project Structure
```
trumptrade/
├── benchmarks/              # new package
│   ├── __init__.py          # register_benchmark_jobs()
│   ├── job.py               # benchmark_snapshot_job() — CronTrigger worker
│   └── router.py            # GET /benchmarks endpoint
frontend/src/
├── pages/
│   └── BenchmarksPage.tsx   # new page with LineChart
├── components/
│   └── LiveModeModal.tsx    # typed-confirmation modal component
```

### Pattern 1: APScheduler CronTrigger (daily at 4:01pm ET, weekdays only)

**What:** Register a cron job that fires once per trading day, 1 minute after market close
**When to use:** Any daily at-close snapshot job

```python
# Source: verified against APScheduler 3.11.2 installed in project
from apscheduler.triggers.cron import CronTrigger

def register_benchmark_jobs(scheduler: AsyncIOScheduler) -> None:
    scheduler.add_job(
        benchmark_snapshot_job,
        trigger=CronTrigger(
            day_of_week="mon-fri",   # weekdays only; holidays produce no bar (skip)
            hour=16,
            minute=1,
            timezone="US/Eastern",   # confirmed working: pytz.timezone('US/Eastern')
        ),
        id="benchmarks_snapshot",
        replace_existing=True,
        misfire_grace_time=300,   # 5 min grace — cron jobs can miss briefly at startup
        coalesce=True,
        max_instances=1,
    )
```

**Note on market holidays:** CronTrigger fires Mon-Fri regardless of US market holidays (MLK Day, etc.). When the job calls `get_stock_bars()` on a holiday, the API returns no bar for that date — the job must detect this and skip writing a snapshot. This is correct behavior: no bar = no snapshot = no gap in % return chart (chart just skips that date).

### Pattern 2: Alpaca StockHistoricalDataClient — daily closing price

**What:** Fetch the closing price for a symbol on a specific date using the free data feed
**When to use:** SPY/QQQ NAV calculation in the snapshot job

```python
# Source: [VERIFIED: alpaca-py 0.43.2 installed — Bar model has .close field]
import asyncio
from datetime import datetime, date, timedelta
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

def _fetch_close_price_sync(api_key: str, secret_key: str, symbol: str, target_date: date) -> float | None:
    """Synchronous — must be called via run_in_executor in async context."""
    client = StockHistoricalDataClient(api_key=api_key, secret_key=secret_key)
    start = datetime(target_date.year, target_date.month, target_date.day, 20, 0)  # 8pm UTC = 4pm ET
    end = datetime(target_date.year, target_date.month, target_date.day, 23, 59)
    request = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame.Day,
        start=start,
        end=end,
        limit=1,
    )
    bar_set = client.get_stock_bars(request)
    bars = bar_set.data.get(symbol, [])
    if not bars:
        return None   # holiday or weekend — caller must skip snapshot
    return bars[-1].close   # Bar.close is a float [VERIFIED: Bar model fields]

async def fetch_close_price(api_key: str, secret_key: str, symbol: str, target_date: date) -> float | None:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _fetch_close_price_sync, api_key, secret_key, symbol, target_date)
```

**Response shape:** `BarSet.data` is `Dict[str, List[Bar]]`. `Bar` fields: `symbol`, `timestamp` (datetime), `open`, `high`, `low`, `close` (float), `volume`, `trade_count`, `vwap`. [VERIFIED: inspect of Bar model]

**Key concern:** `StockHistoricalDataClient` is synchronous. Calling it directly in an async function blocks the event loop. Always wrap in `run_in_executor` — this is the established pattern from `dashboard/router.py`. [VERIFIED: codebase]

### Pattern 3: NAV Math for Shadow Portfolios

**SPY/QQQ NAV (index-tracking approach):**
```python
# If start_close is None (first snapshot ever):
#   nav_value = STARTING_NAV (e.g., 100_000.0)
#   start_close = today_close
# Subsequent days:
#   nav_value = STARTING_NAV * (today_close / start_close)
#
# % return for chart (computed in GET /benchmarks, not stored):
#   pct_return = (nav_value / first_nav - 1) * 100
#   All portfolios start at 0.0 on their first snapshot date.
```

The `ShadowPortfolioSnapshot` stores `nav_value` in dollars. The `positions_json` for SPY/QQQ tracks `{"SPY": {"qty": X, "avg_price": Y}}` — the qty is computed as `STARTING_NAV / start_close`. This makes NAV math consistent with the random baseline which explicitly tracks shares.

**STARTING_NAV constant:** Use `100_000.0` (100k virtual dollars) for all three portfolios. This is never stored in settings — it's a module-level constant.

**Random baseline NAV:**
```python
# State stored in positions_json: {"TSLA": {"qty": 10, "avg_price": 150.0}, "cash": 95000.0}
# On each trading day:
#   1. Read current positions_json and cash from last snapshot
#   2. Randomly pick ticker from watchlist (random.choice)
#   3. Randomly buy or sell (random.random() < 0.5)
#   4. BUY: qty = floor((cash * max_pos_pct) / current_price); cash -= qty * price; positions[ticker].qty += qty
#   5. SELL: if ticker in positions and qty > 0: cash += qty * price; del positions[ticker]
#   6. NAV = cash + sum(qty * current_price for each position)
#   7. current_price for held positions: fetch from Alpaca bars (same call, include all held tickers)
```

### Pattern 4: GET /benchmarks endpoint response shape

**What Recharts LineChart expects:** An array of objects where each object has a `date` key plus one key per series. All values must be pre-computed % returns.

```python
# Backend response: list of dicts
[
  {"date": "2026-04-01", "bot": 0.0,  "spy": 0.0,  "qqq": 0.0,  "random": 0.0},
  {"date": "2026-04-02", "bot": 1.2,  "spy": 0.8,  "qqq": 1.1,  "random": -0.5},
  {"date": "2026-04-03", "bot": -0.3, "spy": 1.2,  "qqq": 0.9,  "random": 2.1},
]
```

**Bot NAV source decision:** The bot's own portfolio NAV history is NOT stored as `ShadowPortfolioSnapshot`. The cleanest approach is to add a `portfolio_name="bot"` entry to the daily job — storing the Alpaca account equity (from `TradingClient.get_account().equity`) at 4:01pm ET each day. This keeps all four series in one table with identical query patterns. [ASSUMED — this is the recommended approach; alternative is querying Alpaca equity history endpoint but that's more complex]

**Endpoint query logic:**
```python
# 1. Read all shadow_portfolio_snapshots rows ordered by (snapshot_date, portfolio_name)
# 2. Pivot into {date: {portfolio_name: nav_value}}
# 3. Find the first date where ALL 4 portfolios have a snapshot (or just the first available date)
# 4. For each portfolio, compute pct_return = (nav / first_nav - 1) * 100
# 5. Return list of dicts sorted by date
```

### Pattern 5: Recharts LineChart with 4 series

**Data shape:** Array of objects with `date` (string) and per-series numeric keys.
**Recharts version:** 3.8.1 (React 19 compatible — verified peerDependencies). [VERIFIED: npm registry]

```tsx
// Source: [VERIFIED: recharts npm 3.8.1, peer dep check, search results]
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ReferenceLine,
} from "recharts"

interface BenchmarkPoint {
  date: string     // "2026-04-01"
  bot: number      // % return, e.g. 1.23
  spy: number
  qqq: number
  random: number
}

function BenchmarkChart({ data }: { data: BenchmarkPoint[] }) {
  return (
    <ResponsiveContainer width="100%" height={400}>
      <LineChart data={data} margin={{ top: 8, right: 24, left: 0, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
          tickFormatter={(v) => v.slice(5)}   // "04-01" from "2026-04-01"
        />
        <YAxis
          tickFormatter={(v) => `${v.toFixed(1)}%`}
          tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
          label={{ value: "Return since start (%)", angle: -90, position: "insideLeft", offset: 12 }}
        />
        <ReferenceLine y={0} stroke="hsl(var(--muted-foreground))" strokeDasharray="4 4" />
        <Tooltip
          formatter={(value: number, name: string) => [`${value.toFixed(2)}%`, name.toUpperCase()]}
          labelFormatter={(label) => `Date: ${label}`}
          contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))" }}
        />
        <Legend verticalAlign="bottom" />
        <Line type="monotone" dataKey="bot"    stroke="#3b82f6" dot={false} strokeWidth={2} name="Bot" />
        <Line type="monotone" dataKey="spy"    stroke="#22c55e" dot={false} strokeWidth={2} name="SPY" />
        <Line type="monotone" dataKey="qqq"    stroke="#a855f7" dot={false} strokeWidth={2} name="QQQ" />
        <Line type="monotone" dataKey="random" stroke="#f59e0b" dot={false} strokeWidth={2} name="Random" />
      </LineChart>
    </ResponsiveContainer>
  )
}
```

**`dot={false}`**: Removes per-point dots for cleaner appearance with daily data over weeks/months.
**`type="monotone"`**: Smooth curve interpolation (standard for financial charts).

### Pattern 6: POST /trading/set-mode endpoint

**What:** Writes `trading_mode` to `app_settings`. Near-identical to kill-switch pattern. [VERIFIED: codebase]

```python
# Source: mirrors trumptrade/trading/router.py kill-switch pattern [VERIFIED: codebase]
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import update
from trumptrade.core.db import AsyncSessionLocal
from trumptrade.core.models import AppSettings

class SetModeRequest(BaseModel):
    mode: str       # "paper" | "live"
    confirmed: bool  # must be True (extra safety gate)

class SetModeResponse(BaseModel):
    trading_mode: str
    ok: bool

@router.post("/set-mode", response_model=SetModeResponse)
async def set_trading_mode(body: SetModeRequest) -> SetModeResponse:
    if body.mode not in ("paper", "live"):
        raise HTTPException(status_code=422, detail="mode must be 'paper' or 'live'")
    if not body.confirmed:
        raise HTTPException(status_code=422, detail="confirmed must be true")
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

**Where to add:** In `trumptrade/trading/router.py` (same file as kill-switch) — keeps trading control endpoints co-located. Register at `prefix="/trading"`, so route is `POST /trading/set-mode`.

### Pattern 7: Live mode modal — React typed confirmation

```tsx
// Source: [ASSUMED — standard React state pattern, no library needed]
import { useState } from "react"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

const LIVE_PHRASE = "ENABLE LIVE TRADING"
const PAPER_PHRASE = "ENABLE PAPER TRADING"

export function LiveModeModal({ isLive, onClose }: { isLive: boolean; onClose: () => void }) {
  const [input, setInput] = useState("")
  const targetPhrase = isLive ? PAPER_PHRASE : LIVE_PHRASE
  const targetMode = isLive ? "paper" : "live"
  const isMatch = input === targetPhrase    // exact, case-sensitive per D-09

  async function handleConfirm() {
    await api.setMode(targetMode)           // POST /trading/set-mode
    queryClient.invalidateQueries({ queryKey: ["portfolio-mode"] })
    onClose()
  }

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Switch to {targetMode.toUpperCase()} mode</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">
          Type <code className="font-mono font-bold">{targetPhrase}</code> to confirm.
        </p>
        <Input value={input} onChange={(e) => setInput(e.target.value)} placeholder={targetPhrase} />
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button
            variant={targetMode === "live" ? "destructive" : "default"}
            disabled={!isMatch}
            onClick={handleConfirm}
          >
            Confirm
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
```

### Pattern 8: AppShell changes for LIVE badge and banner

**Existing:** `TradingModeBadge` component in `AppShell.tsx` already shows LIVE/PAPER badge at sidebar bottom. The red LIVE styling is already coded (Phase 6). [VERIFIED: codebase — see AppShell.tsx lines 21-42]

**What to add:**
1. A red banner at the top of `<main>` when `trading_mode === "live"` — visible on every page regardless of route.
2. A new `Benchmarks` nav item in `NAV_ITEMS` pointing to `/benchmarks`.
3. A mode-switch button somewhere on the Settings page (or Portfolio page) that opens `LiveModeModal`.

```tsx
// In AppShell.tsx — add to <main> content area:
{mode === "live" && (
  <div className="bg-red-500/10 border-b border-red-500/30 px-4 py-2 text-center text-red-400 text-sm font-semibold">
    LIVE TRADING ACTIVE — real money at risk
  </div>
)}
```

### Anti-Patterns to Avoid

- **Calling StockHistoricalDataClient directly in async def:** Blocks the event loop. Always use `run_in_executor`. [VERIFIED: codebase pattern from dashboard/router.py]
- **Storing % return values in ShadowPortfolioSnapshot:** Store raw NAV in dollars. Compute % return at read time in GET /benchmarks. Easier to re-normalize if start date changes.
- **Writing duplicate snapshots:** `ShadowPortfolioSnapshot` has no unique constraint on `(portfolio_name, snapshot_date)` [VERIFIED: migration]. The job must check if a row already exists before inserting (use SELECT first, or INSERT OR IGNORE via raw SQL).
- **Passing the scheduler instance across modules via global import:** Always use the `from trumptrade.core.app import scheduler` pattern established in Phase 3. [VERIFIED: codebase]
- **Using `request` library:** Project rule — use `httpx` or alpaca-py SDK. The benchmark job uses alpaca-py SDK — no httpx needed.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Time-series chart | Custom SVG/canvas | Recharts `LineChart` | Handles resize, tooltip, legend, axis formatting out of box |
| Cron scheduling | asyncio.sleep() loop | APScheduler `CronTrigger` | Already in project; handles misfire, coalesce, hot-reload |
| Confirmation modal | Custom `<div>` overlay | shadcn `Dialog` | Focus trap, keyboard close, accessibility, animation |
| Alpaca data fetch | httpx + manual JSON parse | `StockHistoricalDataClient` | Handles auth, pagination, rate limits, response parsing |
| % return normalization | Complex frontend math | Server-side in GET /benchmarks | Single source of truth; chart just renders numbers |

**Key insight:** All complex date/time handling (market hours, timezone, misfire) is handled by APScheduler CronTrigger. The job code only needs to handle the empty-bars case (holiday) gracefully.

---

## Common Pitfalls

### Pitfall 1: No bar returned on market holidays

**What goes wrong:** CronTrigger fires Mon-Fri including holidays. `get_stock_bars()` returns an empty list for the holiday date. If the job writes a snapshot with `nav_value=None` or crashes, subsequent days have a gap.

**Why it happens:** US market holidays (MLK Day, Presidents' Day, Good Friday, etc.) fall on weekdays. The API correctly returns no data.

**How to avoid:** After calling `fetch_close_price()`, check `if price is None: logger.info("Holiday detected, skipping snapshot"); return`. No snapshot written = no chart point for that day. Recharts skips missing dates naturally (or connect dots across gaps).

**Warning signs:** Snapshot count is less than calendar weekdays since start.

### Pitfall 2: ShadowPortfolioSnapshot duplicate rows

**What goes wrong:** If the job runs twice (hot-reload during dev, misfire + catch-up), two rows for the same `(portfolio_name, snapshot_date)` are inserted. GET /benchmarks returns duplicate date points causing a zigzag in the chart.

**Why it happens:** The table has no unique constraint on `(portfolio_name, snapshot_date)` — confirmed from migration inspection.

**How to avoid:** Two options:
1. (Recommended) Add a new Alembic migration adding `UniqueConstraint("portfolio_name", "snapshot_date")` and use `INSERT OR IGNORE`.
2. At minimum: in the job, `SELECT COUNT(*) WHERE portfolio_name=X AND snapshot_date=today` and skip if > 0.

**Warning signs:** Chart shows V-shapes or spikes on certain days.

### Pitfall 3: Bot NAV has no daily history before Phase 7 starts

**What goes wrong:** The bot's own portfolio NAV wasn't tracked as `ShadowPortfolioSnapshot(portfolio_name="bot")` before Phase 7. First day the job runs, there's 0 historical bot data.

**Why it happens:** Phase 7 starts tracking bot NAV from the first run — this is by design (D-05).

**How to avoid:** The first snapshot day becomes the start date (0% return) for ALL series including bot. Accept that the chart is empty until after the first job run. Show empty state: "No benchmark data yet. Check back after today's market close."

### Pitfall 4: Random baseline with empty watchlist

**What goes wrong:** Job tries `random.choice([])` → raises `IndexError`.

**Why it happens:** User may not have added any watchlist tickers yet.

**How to avoid:** Check `if not watchlist: logger.info("Watchlist empty, skipping random trade"); skip`.

### Pitfall 5: Recharts `react-is` peer dependency missing

**What goes wrong:** `recharts` 3.x requires `react-is` as a peer dependency. It's not in the current `frontend/package.json` and not in `node_modules`. Without it, recharts may throw a runtime error or fail to render.

**Why it happens:** `react-is` was bundled with React DOM in older versions but is now a separate package.

**How to avoid:** Install both: `npm install recharts react-is`.

### Pitfall 6: Timezone offset — fetching "today's close" in UTC

**What goes wrong:** Market closes at 4:00pm ET. In UTC, this is 9:00pm (EDT) or 8:00pm (EST). If the bar request uses a naive UTC `start` that's before the close, the bar may not be available yet.

**Why it happens:** The job fires at 4:01pm ET = 20:01 or 21:01 UTC. The bar timestamp from Alpaca for a daily bar is typically midnight UTC of the next day or EOD of the bar date — API behavior varies slightly.

**How to avoid:** Set `start` to the target date at 00:00 UTC and `end` to the target date at 23:59 UTC (or just target date + 1 day). Request `limit=1` and take `bars[-1].close`. This always gets the complete day bar regardless of timezone.

### Pitfall 7: shadcn Dialog not installed

**What goes wrong:** `LiveModeModal` imports from `@/components/ui/dialog` which doesn't exist in the current frontend.

**Why it happens:** Dialog is not in the shadcn/ui component list currently installed. [VERIFIED: frontend/src/components/ui/ directory listing]

**How to avoid:** Wave 0 task: `cd frontend && npx shadcn add dialog`.

---

## Code Examples

### Verified: run_in_executor pattern (from dashboard/router.py)
```python
# Source: [VERIFIED: trumptrade/dashboard/router.py lines 194-196]
loop = asyncio.get_running_loop()
account = await loop.run_in_executor(None, client.get_account)
positions = await loop.run_in_executor(None, client.get_all_positions)
```

### Verified: app_settings write pattern (from risk_guard/router.py)
```python
# Source: [VERIFIED: trumptrade/risk_guard/router.py lines 96-102]
async with AsyncSessionLocal() as session:
    for key, value in updates.items():
        await session.execute(
            update(AppSettings)
            .where(AppSettings.key == key)
            .values(value=str(value))
        )
    await session.commit()
```

### Verified: APScheduler job registration pattern (from ingestion/__init__.py)
```python
# Source: [VERIFIED: trumptrade/ingestion/__init__.py lines 24-33]
scheduler.add_job(
    poll_truth_social,
    trigger="interval",
    seconds=60,
    id="ingestion_truth_social",
    replace_existing=True,
    misfire_grace_time=30,
    coalesce=True,
    max_instances=1,
)
```

### Verified: ShadowPortfolioSnapshot fields
```python
# Source: [VERIFIED: trumptrade/core/models.py lines 159-174]
class ShadowPortfolioSnapshot(Base):
    __tablename__ = "shadow_portfolio_snapshots"
    id: Mapped[int]                  # autoincrement PK
    portfolio_name: Mapped[str]      # "SPY" | "QQQ" | "random" | "bot"
    snapshot_date: Mapped[date]      # Python date (SQLAlchemy Date column)
    nav_value: Mapped[float]         # portfolio NAV in dollars
    cash: Mapped[float]              # uninvested cash (0.0 for SPY/QQQ index approach)
    positions_json: Mapped[str]      # JSON: {"SPY": {"qty": 333.0, "avg_price": 300.0}}
    created_at: Mapped[datetime]     # auto-set
# NOTE: No UniqueConstraint on (portfolio_name, snapshot_date) [VERIFIED: migration]
# Phase 7 MUST add one (new Alembic migration) or handle in job logic.
```

### Verified: App scheduler import pattern
```python
# Source: [VERIFIED: trumptrade/core/app.py lines 44, 113-118]
# In create_app():
from trumptrade.benchmarks import register_benchmark_jobs
register_benchmark_jobs(scheduler)
# And in lifespan, scheduler is already started via scheduler.start()
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `alpaca-trade-api` (deprecated) | `alpaca-py` 0.43.x | ~2022 | Project mandates alpaca-py — do not use old package |
| Recharts 2.x | Recharts 3.x (3.8.1) | 2024 | React 19 compat; requires `react-is` peer dep |
| APScheduler on_event | lifespan context manager | FastAPI 0.95+ | Project already uses lifespan pattern correctly |

**Deprecated/outdated:**
- `alpaca-trade-api`: forbidden per CLAUDE.md
- `@app.on_event("startup")`: replaced by lifespan context in this project (app.py)

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Bot daily NAV should be stored as `ShadowPortfolioSnapshot(portfolio_name="bot")` in the same daily job | Architecture / Bot NAV Source | If wrong, need separate endpoint to fetch historical Alpaca account equity (more complex) |
| A2 | STARTING_NAV of $100,000 for all three shadow portfolios | NAV Math pattern | Cosmetic only — % return is scale-invariant |
| A3 | recharts 3.x `dot={false}` and `type="monotone"` are the correct prop names | Recharts chart pattern | Chart may not render dots-off or may use different interpolation name |
| A4 | Alpaca daily bar for `target_date` is available at 4:01pm ET when queried | Alpaca bars API | Bar may be delayed; if so, `bars[-1].close` returns previous day's bar. Mitigation: use `limit=1` with broad date range and verify `bar.timestamp.date() == target_date` |

**Note on A4 (critical):** Verify the bar timestamp matches `target_date` before using it. Alpaca may return the previous day's bar if today's hasn't settled yet. If timestamp mismatch, treat as holiday (skip).

---

## Open Questions

1. **Bot NAV historical source before Phase 7**
   - What we know: Bot's Alpaca equity history is available from the Alpaca account API but is not stored locally
   - What's unclear: Does Alpaca provide historical account equity endpoint, or only current?
   - Recommendation: Store bot NAV as `ShadowPortfolioSnapshot(portfolio_name="bot")` in the daily snapshot job. Accept that pre-Phase 7 history is unavailable — chart starts from first run.

2. **Unique constraint migration**
   - What we know: No unique constraint on `(portfolio_name, snapshot_date)` exists
   - What's unclear: Whether to add it in a new Alembic migration or handle in job code
   - Recommendation: Add a new migration (006_benchmark_unique.py) with `CREATE UNIQUE INDEX IF NOT EXISTS` — safer than job-level guarding

3. **Mode-switch UI placement**
   - What we know: Settings page has watchlist + risk controls. No "switch mode" button exists.
   - What's unclear: D-12 says add endpoint but doesn't specify where the button lives in Settings
   - Recommendation: Add a "Trading Mode" section at bottom of SettingsPage with current mode display + "Switch to LIVE / Switch to PAPER" button that opens LiveModeModal

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| alpaca-py | SPY/QQQ bar fetch | Yes | 0.43.2 | — |
| APScheduler | CronTrigger job | Yes | 3.11.2 | — |
| recharts | BenchmarksPage chart | No (npm install needed) | 3.8.1 latest | — |
| react-is | recharts peer dep | No (npm install needed) | 19.2.5 | — |
| shadcn Dialog | LiveModeModal | No (npx shadcn add dialog needed) | via shadcn CLI | — |
| pytz | US/Eastern timezone | Yes | in stdlib via APScheduler | — |

**Missing dependencies with no fallback:**
- recharts + react-is: `npm install recharts react-is` in Wave 0
- shadcn Dialog: `npx shadcn add dialog` in Wave 0

**Missing dependencies with fallback:**
- None

---

## Security Domain

> `security_enforcement` not set to false in config — section included.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Single-user local tool; no auth layer |
| V3 Session Management | No | No sessions |
| V4 Access Control | No | Single-user; no roles |
| V5 Input Validation | Yes | Pydantic `SetModeRequest`: `mode` validated against enum `{"paper", "live"}`; `confirmed: bool` required |
| V6 Cryptography | No | No new secrets or encryption in this phase |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Accidental live mode activation | Spoofing/Tampering | Two-step: typed phrase + `confirmed: true` in request body; server validates both |
| Duplicate snapshot insertion | Tampering (data integrity) | Unique DB constraint + job idempotency check |
| Blocking event loop (Alpaca sync SDK) | Denial of Service | Always use `run_in_executor` — established pattern, verified in codebase |

---

## Sources

### Primary (HIGH confidence)
- `trumptrade/core/models.py` — ShadowPortfolioSnapshot schema, AppSettings pattern [VERIFIED: codebase]
- `trumptrade/dashboard/router.py` — run_in_executor pattern, _read_setting helper [VERIFIED: codebase]
- `trumptrade/risk_guard/router.py` — PATCH settings pattern [VERIFIED: codebase]
- `trumptrade/trading/router.py` — kill-switch endpoint pattern [VERIFIED: codebase]
- `trumptrade/ingestion/__init__.py` + `analysis/__init__.py` — APScheduler job registration [VERIFIED: codebase]
- `trumptrade/core/app.py` — scheduler import, create_app() pattern [VERIFIED: codebase]
- `alembic/versions/6e3709bc5279_initial_schema.py` — trading_mode seed, no unique constraint on shadow table [VERIFIED: codebase]
- alpaca-py 0.43.2 installed — `StockHistoricalDataClient`, `StockBarsRequest`, `TimeFrame.Day`, `BarSet`, `Bar` fields [VERIFIED: Python inspect]
- APScheduler 3.11.2 — `CronTrigger(day_of_week='mon-fri', hour=16, minute=1, timezone='US/Eastern')` [VERIFIED: Python import]
- recharts 3.8.1 — latest on npm, React 19 compatible [VERIFIED: npm view]
- `frontend/src/components/ui/` — Dialog component NOT present [VERIFIED: directory listing]
- `frontend/package.json` — recharts not installed [VERIFIED: dependencies list]

### Secondary (MEDIUM confidence)
- Recharts LineChart API (props, data format, component names) [CITED: recharts.github.io + WebSearch cross-verification]

### Tertiary (LOW confidence)
- Alpaca daily bar availability at exactly 4:01pm ET [ASSUMED — not verified via live API call]

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified as installed or available on npm
- Architecture: HIGH — patterns directly derived from verified codebase
- Pitfalls: HIGH for codebase-verifiable ones (no unique constraint, no dialog installed); MEDIUM for Alpaca API timing behavior

**Research date:** 2026-04-23
**Valid until:** 2026-05-23 (stable libraries; alpaca-py API unlikely to change)
