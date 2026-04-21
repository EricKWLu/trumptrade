# Phase 5: Risk Guard + Integration - Research

**Researched:** 2026-04-21
**Domain:** asyncio.Queue producer-consumer, Alpaca account API, market hours enforcement, FastAPI settings endpoints
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Signal Dispatch Pipeline**
- D-01: `analysis_worker` enqueues BUY/SELL signals directly onto a module-level `asyncio.Queue` after Signal DB write. SKIP signals are never enqueued.
- D-02: Queue capacity ~100.
- D-03: Consumer is `asyncio.create_task()` started in FastAPI lifespan alongside APScheduler. Consumer loop: `await queue.get()` → run risk checks → call `AlpacaExecutor.execute()`.
- D-04: Signals in queue are lost on server restart. Acceptable — analysis_worker re-processes unanalyzed posts on next tick.
- D-05: Queue instantiated in new `trumptrade/risk_guard/` module; imported by `analysis_worker`.

**Position Sizing**
- D-06: Position size = direct percentage of live portfolio equity (`max_position_size_pct` in `app_settings`).
- D-07: `trade_dollars = equity × (max_position_size_pct / 100) × confidence`, `qty = floor(trade_dollars / share_price)`.
- D-08: One trade per ticker for multi-ticker signals. Position sizing applies independently per ticker.
- D-09: Default `max_position_size_pct` = 2.0 (conservative default — Claude's discretion, confirmed).

**Daily Loss Cap**
- D-10: Baseline = Alpaca's `last_equity` field from `trading_client.get_account()`. No snapshot storage needed.
- D-11: Cap in dollars (`max_daily_loss_dollars`). Check: `if (last_equity - equity) >= max_daily_loss_dollars: block`.
- D-12: Log reason code `DAILY_CAP_HIT`. Cap resets automatically when Alpaca updates `last_equity` at next market close.
- D-13: Default `max_daily_loss_dollars` = 500.0 (Claude's discretion, confirmed).

**Market Hours + Staleness**
- D-14: NYSE 9:30 AM – 4:00 PM ET. Use `pytz` with `America/New_York`.
- D-15: Staleness configurable via `signal_staleness_minutes`. Default 5. Compares `post.posted_at` to current time.
- D-16: After-hours behavior: confidence < 0.85 → discard `MARKET_CLOSED`; confidence >= 0.85 → hold in queue until open (24h expiry on open, discarded as `STALE`).
- D-17: Hold threshold 0.85 is hardcoded constant.

**Settings Endpoint (SETT-02)**
- D-18: `GET /settings/risk` + `PATCH /settings/risk`. Keys: `max_position_size_pct`, `stop_loss_pct`, `max_daily_loss_dollars`, `signal_staleness_minutes`.
- D-19: Settings changes take effect on next signal (consumer reads per-cycle).

### Claude's Discretion
- Default seed values for new app_settings keys (max_position_size_pct: 2.0, max_daily_loss_dollars: 500.0)
- Exact Pydantic schema for PATCH /settings/risk request/response bodies
- Error handling for AlpacaExecutor failures in the consumer (log + continue, never crash the loop)

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TRADE-04 | Market hours check before executing; discard stale signals | Pattern 3 (pytz market hours), Pattern 4 (after-hours hold), Pattern 7 (staleness check) |
| RISK-01 | Position size as % of portfolio per trade | Pattern 5 (position sizing math with Alpaca equity) |
| RISK-02 | Stop-loss threshold % attached as bracket stop | Already implemented in AlpacaExecutor.execute(); risk guard just passes stop_loss_pct via app_settings |
| RISK-03 | Max daily loss cap from live Alpaca account | Pattern 2 (get_account() equity/last_equity fields) |
| SETT-02 | Risk controls settable from settings endpoint | Pattern 6 (settings router pattern) |
</phase_requirements>

---

## Summary

Phase 5 wires the asyncio.Queue chokepoint that sits between `analysis_worker` (producer) and `AlpacaExecutor` (consumer). The queue is instantiated at module level in a new `trumptrade/risk_guard/` package and imported by `analysis_worker` to avoid circular imports — the same local-import pattern established in Phases 3 and 4. The consumer runs as a `asyncio.create_task()` started in FastAPI lifespan, matching how APScheduler is started.

All Alpaca SDK calls are sync and must be wrapped in `run_in_executor` — the codebase already does this consistently in `executor.py`. The `get_account()` call returns `equity` and `last_equity` as `Optional[str]` (confirmed from alpaca-py source), so explicit `float()` conversion is required. `get_clock()` returns a `Clock` object with `is_open: bool`, `next_open: datetime`, and `next_close: datetime` — use this instead of hand-rolling a pytz comparison for the primary market-open detection.

After-hours hold logic requires a separate in-memory list (not the main queue) to hold high-confidence signals until open. The consumer polls `get_clock().is_open` at the top of each loop iteration and drains the hold list when open is detected. Signals older than 24h in the hold list are expired as STALE.

**Primary recommendation:** Implement `risk_guard/guard.py` with a single async `risk_consumer()` function that loops forever: poll hold list at open, then `await queue.get()`, run checks (staleness → market hours → daily cap → position sizing), then call `executor.execute()`. Wire into `app.py` lifespan after `scheduler.start()`.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Signal queue (producer) | API/Backend (analysis_worker) | — | Signal insertion happens in async worker job; `put_nowait()` is in-process |
| Risk checks (staleness, market hours, daily cap, position sizing) | API/Backend (risk_guard/guard.py) | — | All checks require DB reads and Alpaca API calls; never in frontend |
| Trade execution | API/Backend (AlpacaExecutor) | — | Already implemented; risk guard calls it with computed qty |
| Settings read/write | API/Backend (risk_guard/router.py) | — | FastAPI router reads/writes app_settings table |
| After-hours hold list | API/Backend (in-memory) | — | Module-level list in guard.py; acceptable because D-04 already accepts signal loss on restart |

---

## Pattern 1: asyncio.Queue in FastAPI Lifespan

### Queue Instantiation — CRITICAL Pitfall

`asyncio.Queue` must NOT be instantiated at module import time when the module is imported before the event loop exists. The safe pattern used throughout this codebase: instantiate the queue at module level but keep it as a module-level object — this works in Python 3.10+ because `asyncio.Queue.__init__` no longer requires a running event loop.

```python
# trumptrade/risk_guard/__init__.py
# [VERIFIED: Python 3.10+ asyncio.Queue no longer binds to loop at creation]
import asyncio

signal_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
```

Python 3.10 removed the `loop` parameter from `asyncio.Queue` and the queue no longer captures the running loop at init time. Since this project requires Python 3.11 (`requires-python = ">=3.11"` in pyproject.toml), module-level instantiation is safe.

### Consumer Task in FastAPI Lifespan

The established pattern from `app.py` (read from codebase) is `asyncio.create_task()` in the lifespan startup block. The consumer task must be stored to allow cancellation on shutdown.

```python
# trumptrade/core/app.py — Phase 5 addition to lifespan
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # STARTUP
    scheduler.start()

    # Phase 5: start risk consumer
    from trumptrade.risk_guard.guard import risk_consumer  # local import — avoids circular
    _consumer_task = asyncio.create_task(risk_consumer(), name="risk_consumer")

    yield

    # SHUTDOWN
    _consumer_task.cancel()
    try:
        await _consumer_task
    except asyncio.CancelledError:
        pass
    scheduler.shutdown(wait=False)
```

**Why cancel + await:** Without `await _consumer_task` after `cancel()`, Python logs "Task was destroyed but it is pending!" on shutdown. The `CancelledError` swallow is intentional.

### Consumer Loop Structure

```python
# [ASSUMED] — pattern derived from asyncio producer-consumer best practices
async def risk_consumer() -> None:
    """Consumer loop — runs forever until cancelled."""
    while True:
        try:
            # 1. Drain hold list if market just opened
            await _drain_hold_list_if_open()

            # 2. Block until a signal arrives
            item: QueueItem = await signal_queue.get()

            # 3. Run risk checks (may discard or execute)
            await _process_signal(item)

            # 4. Mark task done (allows queue.join() if ever used)
            signal_queue.task_done()

        except asyncio.CancelledError:
            raise  # CRITICAL: let CancelledError propagate — never swallow it in consumer
        except Exception as exc:
            logger.exception("risk_consumer: unhandled error — continuing: %s", exc)
            # NEVER crash the loop; log + continue
```

**Critical rule:** `asyncio.CancelledError` MUST be re-raised. Swallowing it prevents graceful shutdown.

### Queue Item Schema

The queue carries a dataclass (not a SQLAlchemy model — avoid passing ORM objects across async boundaries):

```python
# [ASSUMED] — no existing pattern in codebase; dataclass is idiomatic
from dataclasses import dataclass
from datetime import datetime

@dataclass
class QueueItem:
    signal_id: int
    post_id: int
    tickers: list[str]       # already parsed from JSON by analysis_worker
    side: str                # "BUY" | "SELL"
    confidence: float
    posted_at: datetime      # post.posted_at — used for staleness check
```

### put_nowait() from analysis_worker

APScheduler's `AsyncIOScheduler` runs jobs in the event loop, so `analysis_worker` is an async coroutine running in the loop. `queue.put_nowait()` is safe here (no blocking). If the queue is full (maxsize=100), `put_nowait()` raises `asyncio.QueueFull` — log a warning and discard rather than blocking the analysis worker.

```python
# In analysis_worker after Signal DB insert (only for BUY/SELL final_action):
from trumptrade.risk_guard import signal_queue

if final_action in ("BUY", "SELL") and final_tickers:
    item = QueueItem(
        signal_id=signal.id,
        post_id=post.id,
        tickers=json.loads(signal.affected_tickers),
        side=final_action,
        confidence=signal_result.confidence,
        posted_at=post.posted_at,
    )
    try:
        signal_queue.put_nowait(item)
    except asyncio.QueueFull:
        logger.warning("risk_guard signal_queue full — discarding signal_id=%d", signal.id)
```

---

## Pattern 2: Alpaca Account API (get_account, get_clock)

### get_account() — Field Types

From alpaca-py source (`alpaca/trading/models.py`), confirmed via GitHub:

| Field | Type | Description |
|-------|------|-------------|
| `equity` | `Optional[str]` | cash + long_market_value + short_market_value; computed server-side |
| `last_equity` | `Optional[str]` | Equity as of previous trading day at 16:00:00 ET |
| `buying_power` | `Optional[str]` | Available buying power |
| `cash` | `Optional[str]` | Cash balance |

**CRITICAL:** All monetary fields are `str`, not `float`. Must convert explicitly:

```python
# [VERIFIED: alpaca-py GitHub alpaca/trading/models.py — TradeAccount model]
account = await loop.run_in_executor(None, trading_client.get_account)
equity = float(account.equity)          # "100000.00" → 100000.0
last_equity = float(account.last_equity)  # "101000.00" → 101000.0
daily_loss = last_equity - equity       # positive = loss
```

### get_clock() — Clock Response Fields

From alpaca-py source (`alpaca/trading/models.py`), confirmed via GitHub:

| Field | Type | Description |
|-------|------|-------------|
| `is_open` | `bool` | Whether market is currently open |
| `timestamp` | `datetime` | Current timestamp (timezone-aware) |
| `next_open` | `datetime` | When market will next open (timezone-aware) |
| `next_close` | `datetime` | When market will next close (timezone-aware) |

```python
# [VERIFIED: alpaca-py GitHub alpaca/trading/models.py — Clock model]
clock = await loop.run_in_executor(None, trading_client.get_clock)
if clock.is_open:
    # Market is open — proceed with execution
    pass
else:
    # Market is closed — check confidence gate for hold vs discard
    next_open: datetime = clock.next_open  # tz-aware datetime
```

### run_in_executor Pattern (established in executor.py)

```python
# [VERIFIED: codebase — trumptrade/trading/executor.py lines 56-65]
loop = asyncio.get_running_loop()
account = await loop.run_in_executor(
    None,
    trading_client.get_account,  # no args — pass callable directly, no partial()
)
clock = await loop.run_in_executor(
    None,
    trading_client.get_clock,
)
```

### Client Instantiation in risk_guard

`risk_guard/guard.py` needs a `TradingClient` instance for `get_account()` and `get_clock()`. Follow the same pattern as `executor.py`: read `trading_mode` from `app_settings` per cycle, instantiate client with `paper=is_paper`. Do NOT cache the client at module level — per the codebase's established D-06 rule (re-read settings per request).

```python
# [VERIFIED: codebase — trumptrade/trading/executor.py lines 41-47]
trading_mode = await _get_setting("trading_mode")
is_paper = (trading_mode == "paper")
settings = get_settings()
trading_client = TradingClient(
    api_key=settings.alpaca_api_key,
    secret_key=settings.alpaca_secret_key,
    paper=is_paper,
)
```

---

## Pattern 3: Market Hours Enforcement with pytz

### Established Project Pattern

`heartbeat.py` already established the authoritative pytz pattern for this codebase:

```python
# [VERIFIED: codebase — trumptrade/ingestion/heartbeat.py lines 8-26]
import pytz
from datetime import datetime, timezone

_EASTERN = pytz.timezone("America/New_York")  # note: risk_guard uses America/New_York, not US/Eastern

def _is_market_open_pytz() -> bool:
    """NYSE market hours: 9:30 AM – 4:00 PM ET, weekdays only."""
    now_et = datetime.now(timezone.utc).astimezone(_EASTERN)
    # Weekday check: Monday=0, Sunday=6
    if now_et.weekday() >= 5:  # Saturday or Sunday
        return False
    market_open = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_open <= now_et < market_close
```

**Note:** heartbeat.py uses `US/Eastern`; risk guard should use `America/New_York` (canonical IANA name, both are equivalent in pytz). The pattern is identical.

**CRITICAL pattern note:** Always use `datetime.now(timezone.utc).astimezone(_EASTERN)` — never `_EASTERN.localize(datetime.now())`. The `localize()` pattern is bug-prone on DST transition boundaries (per RESEARCH.md comment in heartbeat.py).

### get_clock() vs pytz — Preferred Approach

For the primary market-open check in the consumer loop, **prefer `get_clock().is_open`** over the hand-rolled pytz check:
- Handles US market holidays automatically (e.g., July 4th, Thanksgiving)
- Alpaca's authoritative source of truth for whether orders will be accepted
- `next_open` gives exact timestamp for logging

The pytz check is useful as a **fast pre-filter** when you want to avoid an API call (e.g., it's obviously Sunday), but the authoritative check before execution should be `get_clock().is_open`.

**Recommended approach in consumer:**
1. pytz weekday/time check → if obviously closed, no API call needed for the hold decision
2. `get_clock().is_open` before any order execution

---

## Pattern 4: Confidence-Gated After-Hours Hold

### The Problem

`asyncio.Queue` does not support time-delayed release. Held signals cannot simply stay in the queue because the consumer loop would immediately re-check them and loop.

### Solution: Module-Level Hold List

```python
# [ASSUMED] — no existing pattern in codebase; standard asyncio producer-consumer approach
import asyncio
from datetime import datetime, timedelta, timezone

# Module-level — persists for server lifetime; acceptable per D-04 (restart = lost signals)
_hold_list: list[tuple[datetime, QueueItem]] = []
# (enqueued_at, item) — enqueued_at used for 24h expiry
_HOLD_EXPIRY_HOURS = 24
_AFTER_HOURS_HOLD_THRESHOLD = 0.85  # D-17: hardcoded constant
```

### Consumer Flow for After-Hours Signals

```python
# [ASSUMED] — derived from D-16 decisions
async def _handle_after_hours(item: QueueItem) -> None:
    """Called when market is closed."""
    if item.confidence >= _AFTER_HOURS_HOLD_THRESHOLD:
        enqueued_at = datetime.now(timezone.utc)
        _hold_list.append((enqueued_at, item))
        logger.info(
            "risk_consumer: signal held for market open (confidence=%.2f signal_id=%d)",
            item.confidence, item.signal_id,
        )
    else:
        logger.info(
            "risk_consumer: MARKET_CLOSED discard (confidence=%.2f < 0.85) signal_id=%d",
            item.confidence, item.signal_id,
        )
        # Optional: update signal reason_code in DB to MARKET_CLOSED
```

### Draining Hold List at Market Open

```python
# [ASSUMED] — derived from D-16 decisions
async def _drain_hold_list_if_open(trading_client: TradingClient) -> None:
    """Called at top of consumer loop iteration. Drains held signals if market just opened."""
    if not _hold_list:
        return

    loop = asyncio.get_running_loop()
    try:
        clock = await loop.run_in_executor(None, trading_client.get_clock)
    except Exception as exc:
        logger.error("risk_consumer: get_clock failed in hold drain: %s", exc)
        return

    if not clock.is_open:
        return

    now = datetime.now(timezone.utc)
    expiry_cutoff = now - timedelta(hours=_HOLD_EXPIRY_HOURS)

    # Process held signals oldest-first
    to_process = sorted(_hold_list, key=lambda x: x[0])
    _hold_list.clear()

    for enqueued_at, item in to_process:
        if enqueued_at < expiry_cutoff:
            logger.info("risk_consumer: STALE held signal discarded signal_id=%d", item.signal_id)
            continue
        # Re-run full risk checks (position sizing, daily cap) at market open
        await _execute_signal(item, trading_client)
```

### Interaction with Consumer Loop

The consumer loop calls `_drain_hold_list_if_open()` **before** `await signal_queue.get()`. This ensures that when the market opens (likely between polling cycles), the held signals are processed before the next queued signal.

---

## Pattern 5: Position Sizing Math

### Equity Retrieval

```python
# [VERIFIED: alpaca-py source — equity and last_equity are Optional[str]]
account = await loop.run_in_executor(None, trading_client.get_account)
equity = float(account.equity)          # convert from str
last_equity = float(account.last_equity)  # for daily cap check
```

### Position Size Calculation (D-07)

```python
# [VERIFIED: D-07 decisions from CONTEXT.md]
max_position_size_pct = float(await _get_setting("max_position_size_pct"))  # e.g. "2.0"
trade_dollars = equity * (max_position_size_pct / 100) * item.confidence
```

### Share Price Lookup

Reuse the same `StockHistoricalDataClient.get_stock_latest_trade()` pattern from `executor.py`:

```python
# [VERIFIED: codebase — trumptrade/trading/executor.py lines 57-68]
from alpaca.data.requests import StockLatestTradeRequest
from alpaca.data.historical import StockHistoricalDataClient

trade_map = await loop.run_in_executor(
    None,
    partial(
        data_client.get_stock_latest_trade,
        StockLatestTradeRequest(symbol_or_symbols=symbol),
    ),
)
share_price: float = trade_map[symbol].price
```

### qty Calculation — floor() vs round()

Use `math.floor()` — never `round()`. Alpaca rejects fractional quantities for standard equity orders. `round()` can round up, potentially exceeding the intended position size.

```python
# [VERIFIED: D-07 decision; floor() is correct for "never exceed budget"]
import math

qty = math.floor(trade_dollars / share_price)
if qty < 1:
    logger.info(
        "risk_consumer: qty=0 after floor (trade_dollars=%.2f price=%.2f) — skipping %s",
        trade_dollars, share_price, symbol,
    )
    continue  # skip this ticker; not enough equity for even 1 share
```

### Full Position Sizing Block

```python
# [ASSUMED] — combining D-07, D-08, and executor.py patterns
async def _compute_qty(
    symbol: str,
    equity: float,
    confidence: float,
    max_position_size_pct: float,
    data_client: StockHistoricalDataClient,
    loop: asyncio.AbstractEventLoop,
) -> int | None:
    """Returns integer qty or None if qty would be < 1."""
    trade_dollars = equity * (max_position_size_pct / 100) * confidence
    try:
        trade_map = await loop.run_in_executor(
            None,
            partial(
                data_client.get_stock_latest_trade,
                StockLatestTradeRequest(symbol_or_symbols=symbol),
            ),
        )
        share_price = trade_map[symbol].price
    except Exception as exc:
        logger.error("risk_consumer: price lookup failed for %s: %s", symbol, exc)
        return None
    qty = math.floor(trade_dollars / share_price)
    return qty if qty >= 1 else None
```

---

## Pattern 6: Settings Endpoint Structure

### Existing Pattern Reference

`trumptrade/trading/router.py` establishes the Pydantic request/response model pattern:
- Module-level `router = APIRouter()`
- Pydantic `BaseModel` for request and response
- `_executor = AlpacaExecutor()` module-level instance for thin HTTP layer

### Settings Router Structure

```python
# trumptrade/risk_guard/router.py
# [VERIFIED: derived from codebase — trumptrade/trading/router.py pattern]
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional

router = APIRouter()


class RiskSettingsResponse(BaseModel):
    max_position_size_pct: float
    stop_loss_pct: float
    max_daily_loss_dollars: float
    signal_staleness_minutes: int


class RiskSettingsPatch(BaseModel):
    """All fields Optional — allows partial updates (PATCH semantics)."""
    max_position_size_pct: Optional[float] = Field(default=None, gt=0, le=100)
    stop_loss_pct: Optional[float] = Field(default=None, gt=0, le=100)
    max_daily_loss_dollars: Optional[float] = Field(default=None, gt=0)
    signal_staleness_minutes: Optional[int] = Field(default=None, gt=0)


@router.get("/risk", response_model=RiskSettingsResponse)
async def get_risk_settings() -> RiskSettingsResponse:
    """Return current risk settings from app_settings table."""
    ...


@router.patch("/risk", response_model=RiskSettingsResponse)
async def patch_risk_settings(body: RiskSettingsPatch) -> RiskSettingsResponse:
    """Update one or more risk settings. Returns all current values after update."""
    ...
```

### Settings Read/Write Pattern

Reuse `_get_setting()` pattern from `executor.py`. For PATCH, use `update().where(AppSettings.key == key).values(value=str(new_val))` inside `AsyncSessionLocal`. Only update keys where the request field is not None.

```python
# [VERIFIED: codebase — trumptrade/trading/executor.py _get_setting() and set_bot_enabled()]
# Read:
async with AsyncSessionLocal() as session:
    result = await session.execute(
        select(AppSettings.value).where(AppSettings.key == key)
    )
    return result.scalar_one()

# Write:
async with AsyncSessionLocal() as session:
    await session.execute(
        update(AppSettings)
        .where(AppSettings.key == key)
        .values(value=str(new_value))
    )
    await session.commit()
```

### Router Registration in app.py

```python
# [VERIFIED: pattern from trumptrade/core/app.py — Phase 2 trading router registration]
# In create_app():
from trumptrade.risk_guard import settings_router  # local import
app.include_router(settings_router, prefix="/settings", tags=["settings"])
```

---

## Pattern 7: Alembic Migration for New Settings Keys

### Existing Migration Pattern

From `004_analysis_app_settings.py` (verified from codebase):

```python
# [VERIFIED: codebase — alembic/versions/004_analysis_app_settings.py]
def upgrade() -> None:
    op.execute("INSERT OR IGNORE INTO app_settings (key, value) VALUES ('llm_provider', 'anthropic')")
```

`INSERT OR IGNORE` is the canonical pattern: it seeds defaults without overwriting user-changed values.

### Pre-Existing app_settings Keys

From the initial schema migration (`6e3709bc5279_initial_schema.py`), the following keys are **already seeded** with `INSERT` (not `INSERT OR IGNORE`):

| Key | Seeded Value | Notes |
|-----|-------------|-------|
| `position_size_pct` | `2.0` | **Old key** — Phase 5 uses `max_position_size_pct` instead |
| `stop_loss_pct` | `5.0` | Already exists — do NOT re-insert |
| `max_daily_loss_pct` | `10.0` | **Old key** — Phase 5 uses `max_daily_loss_dollars` instead |
| `confidence_threshold` | `0.7` | Already exists |
| `trading_mode` | `paper` | Already exists |
| `bot_enabled` | `false` | Already exists |

**IMPORTANT:** The initial schema has `position_size_pct` and `max_daily_loss_pct` (percentage-based). Phase 5 introduces `max_position_size_pct` (same concept, renamed) and `max_daily_loss_dollars` (dollar-based, different concept). The migration must use `INSERT OR IGNORE` for the new keys only — do NOT touch the old keys (existing code may still reference them).

### Phase 5 Migration (migration 005)

```python
# [VERIFIED: pattern from 004_analysis_app_settings.py]
# Revision: 005
# down_revision: "004"

def upgrade() -> None:
    # New risk guard settings — INSERT OR IGNORE preserves user-edited values
    op.execute("INSERT OR IGNORE INTO app_settings (key, value) VALUES ('max_position_size_pct', '2.0')")
    op.execute("INSERT OR IGNORE INTO app_settings (key, value) VALUES ('max_daily_loss_dollars', '500.0')")
    op.execute("INSERT OR IGNORE INTO app_settings (key, value) VALUES ('signal_staleness_minutes', '5')")
    # Note: stop_loss_pct already exists from initial schema — no INSERT needed

def downgrade() -> None:
    op.execute(
        "DELETE FROM app_settings WHERE key IN "
        "('max_position_size_pct', 'max_daily_loss_dollars', 'signal_staleness_minutes')"
    )
```

---

## Pattern 8: Integration Points and Import Strategy

### Module Structure

```
trumptrade/risk_guard/
├── __init__.py      # exports: signal_queue, settings_router, risk_consumer
├── guard.py         # risk_consumer(), _process_signal(), _drain_hold_list_if_open()
└── router.py        # FastAPI settings router (GET/PATCH /settings/risk)
```

### Import Chain (avoiding circular imports)

The established codebase pattern (confirmed in `app.py`): use local imports inside `create_app()` and inside function bodies. Module-level imports are safe when they don't form cycles.

**Safe import order:**

```
trumptrade/risk_guard/__init__.py
  └── imports: asyncio (stdlib only) → safe at module level

trumptrade/analysis/worker.py
  └── imports: from trumptrade.risk_guard import signal_queue
      (one-way dependency: worker → risk_guard — no cycle)

trumptrade/risk_guard/guard.py
  └── imports: from trumptrade.trading.executor import AlpacaExecutor
      (one-way: risk_guard → trading — no cycle)
  └── imports: from trumptrade.core.db import AsyncSessionLocal
      (one-way: risk_guard → core — no cycle)

trumptrade/core/app.py
  └── local import: from trumptrade.risk_guard.guard import risk_consumer
  └── local import: from trumptrade.risk_guard import settings_router
```

### __init__.py Exports

```python
# trumptrade/risk_guard/__init__.py
# [ASSUMED] — follows analysis/__init__.py pattern
import asyncio
from trumptrade.risk_guard.router import router as settings_router

signal_queue: asyncio.Queue = asyncio.Queue(maxsize=100)

__all__ = ["signal_queue", "settings_router"]
```

**Note:** `risk_consumer` is NOT exported from `__init__.py` — it's imported directly in `app.py` lifespan via local import from `guard.py` (matching how Phase 4 imports `analysis_worker` from `worker.py`).

### analysis_worker Integration Point

The exact location in `analysis_worker()` where enqueue is added:

```python
# [VERIFIED: codebase — trumptrade/analysis/worker.py lines 263-280]
# After:
#   async with AsyncSessionLocal() as session:
#       session.add(signal)
#       await session.commit()
# Add:
if final_action in ("BUY", "SELL") and final_tickers:
    from trumptrade.risk_guard import signal_queue, QueueItem  # local import
    item = QueueItem(
        signal_id=signal.id,
        post_id=post.id,
        tickers=json.loads(signal.affected_tickers),
        side=final_action,
        confidence=signal_result.confidence,
        posted_at=post.posted_at,
    )
    try:
        signal_queue.put_nowait(item)
    except asyncio.QueueFull:
        logger.warning("signal_queue full, discarding signal_id=%d", signal.id)
```

### app.py Lifespan Addition

```python
# [VERIFIED: pattern from trumptrade/core/app.py — scheduler.start() is already there]
# Phase 5 block in lifespan startup (after scheduler.start()):
from trumptrade.risk_guard.guard import risk_consumer  # local import
_consumer_task = asyncio.create_task(risk_consumer(), name="risk_consumer")

# Phase 5 block in lifespan shutdown (before scheduler.shutdown()):
_consumer_task.cancel()
try:
    await _consumer_task
except asyncio.CancelledError:
    pass
```

**Ordering constraint:** `asyncio.create_task()` MUST be called inside the async lifespan context (after the event loop is running). It is already inside the `async with` body, so this is satisfied. The task must be created AFTER `scheduler.start()` to maintain the existing startup order.

---

## Common Pitfalls

### Pitfall 1: Swallowing CancelledError in Consumer Loop
**What goes wrong:** `except Exception` catches `CancelledError` in Python 3.8+, preventing graceful shutdown. Server hangs on exit.
**Why it happens:** Developer adds broad `except Exception` to "never crash the loop."
**How to avoid:** Always have `except asyncio.CancelledError: raise` BEFORE `except Exception` in the consumer loop. Or use `except Exception` only (which does NOT catch `CancelledError` since Python 3.8 made it a `BaseException` subclass).
**Warning signs:** Server hangs for several seconds on Ctrl+C.

```python
# [VERIFIED: Python 3.8+ CancelledError is BaseException, not Exception]
# CORRECT:
except asyncio.CancelledError:
    raise
except Exception as exc:
    logger.exception("consumer error: %s", exc)
```

### Pitfall 2: equity/last_equity String → Float Conversion
**What goes wrong:** `equity - last_equity` raises `TypeError: unsupported operand type(s) for -: 'str' and 'str'`.
**Why it happens:** alpaca-py `TradeAccount` fields are typed `Optional[str]`, not `float`.
**How to avoid:** Always `float(account.equity)` before arithmetic. Also handle `None` case (paper account with zero activity may return `None` for `last_equity`).
**Warning signs:** `TypeError` in risk_consumer logs.

```python
equity_raw = account.equity
last_equity_raw = account.last_equity
if equity_raw is None or last_equity_raw is None:
    logger.warning("risk_consumer: account equity fields are None — skipping daily cap check")
    # proceed without cap check rather than blocking all trades
else:
    equity = float(equity_raw)
    last_equity = float(last_equity_raw)
    # ... cap check
```

### Pitfall 3: Module-Level TradingClient with Cached paper/live Mode
**What goes wrong:** Risk guard instantiates `TradingClient` once at module level. When user switches `trading_mode` from paper to live in settings, guard still uses the old paper client.
**Why it happens:** Convenient to cache expensive clients.
**How to avoid:** Follow executor.py's pattern — instantiate `TradingClient` per signal using `trading_mode` read fresh from `app_settings`. The cost is minimal (no network call at instantiation time).

### Pitfall 4: posted_at Timezone Mismatch in Staleness Check
**What goes wrong:** `(datetime.now(timezone.utc) - post.posted_at).total_seconds()` raises `TypeError: can't subtract offset-naive and offset-aware datetimes`.
**Why it happens:** SQLite stores datetimes as naive strings. SQLAlchemy returns them as naive `datetime` objects. `datetime.now(timezone.utc)` is timezone-aware.
**How to avoid:** Use naive UTC for comparison, matching the heartbeat.py pattern.

```python
# [VERIFIED: codebase — heartbeat.py line 58]
now_naive_utc = datetime.now(timezone.utc).replace(tzinfo=None)
age_seconds = (now_naive_utc - item.posted_at).total_seconds()
staleness_minutes = int(await _get_setting("signal_staleness_minutes"))
if age_seconds > staleness_minutes * 60:
    logger.info("risk_consumer: STALE signal discarded (age=%.0fs) signal_id=%d", age_seconds, item.signal_id)
    continue
```

### Pitfall 5: AlpacaExecutor HTTPException Leaking from Consumer
**What goes wrong:** `executor.execute()` raises `HTTPException` (from its router-layer design). If the consumer doesn't catch this, it propagates up and crashes the loop.
**Why it happens:** `executor.execute()` was designed for HTTP context (raises `HTTPException`). Risk guard calls it from a background task.
**How to avoid:** Wrap `executor.execute()` calls in the consumer with `except (HTTPException, BotDisabledError, Exception)` and log + continue.

```python
# [VERIFIED: codebase — executor.py raises HTTPException and BotDisabledError]
from fastapi import HTTPException
from trumptrade.trading.executor import BotDisabledError

try:
    result = await executor.execute(symbol, item.side.lower(), qty)
    logger.info("risk_consumer: order placed %s", result)
except BotDisabledError:
    logger.info("risk_consumer: bot disabled — signal_id=%d skipped", item.signal_id)
except HTTPException as exc:
    logger.error("risk_consumer: executor HTTPException %d: %s signal_id=%d", exc.status_code, exc.detail, item.signal_id)
except Exception as exc:
    logger.exception("risk_consumer: executor error signal_id=%d: %s", item.signal_id, exc)
```

### Pitfall 6: _hold_list Accumulating Duplicate Tickers
**What goes wrong:** Multiple high-confidence signals for the same ticker accumulate in the hold list. At market open, all of them execute — placing N orders for the same ticker.
**Why it happens:** D-08 says "one trade per ticker" but the hold list doesn't enforce this.
**How to avoid:** When draining the hold list at open, process one signal per ticker (first-seen wins, discard duplicates). Track which tickers have been processed.

```python
# [ASSUMED] — D-08 enforcement at drain time
processed_tickers: set[str] = set()
for enqueued_at, item in to_process:
    eligible_tickers = [t for t in item.tickers if t not in processed_tickers]
    if not eligible_tickers:
        continue
    # ... execute for eligible_tickers
    processed_tickers.update(eligible_tickers)
```

### Pitfall 7: asyncio.create_task() Called Before Event Loop
**What goes wrong:** `RuntimeError: no running event loop` if `create_task()` is called before the lifespan async context is entered.
**Why it happens:** Module-level code executing before `lifespan()` starts.
**How to avoid:** `asyncio.create_task(risk_consumer())` is called INSIDE the `lifespan` async context manager (confirmed placement in startup block, which runs after uvicorn starts the event loop). Never call it from `create_app()` directly.

---

## Code Examples

### Complete Consumer Skeleton

```python
# trumptrade/risk_guard/guard.py
# [ASSUMED] — assembled from all patterns above
import asyncio
import logging
import math
from datetime import datetime, timedelta, timezone
from functools import partial

import pytz
from alpaca.common.exceptions import APIError
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestTradeRequest
from alpaca.trading.client import TradingClient

from trumptrade.core.config import get_settings
from trumptrade.core.db import AsyncSessionLocal
from trumptrade.core.models import AppSettings
from trumptrade.risk_guard import signal_queue
from trumptrade.risk_guard.models import QueueItem

logger = logging.getLogger(__name__)

_EASTERN = pytz.timezone("America/New_York")
_AFTER_HOURS_HOLD_THRESHOLD = 0.85
_HOLD_EXPIRY_HOURS = 24
_hold_list: list[tuple[datetime, QueueItem]] = []


async def _get_setting(key: str, default: str = "") -> str:
    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AppSettings.value).where(AppSettings.key == key)
        )
        val = result.scalar_one_or_none()
        return val if val is not None else default


async def risk_consumer() -> None:
    """Consumer loop — runs until cancelled by lifespan shutdown."""
    from trumptrade.trading.executor import AlpacaExecutor, BotDisabledError
    from fastapi import HTTPException

    executor = AlpacaExecutor()

    while True:
        try:
            # Read settings fresh each cycle (D-19)
            trading_mode = await _get_setting("trading_mode", "paper")
            is_paper = (trading_mode == "paper")
            settings = get_settings()
            trading_client = TradingClient(
                api_key=settings.alpaca_api_key,
                secret_key=settings.alpaca_secret_key,
                paper=is_paper,
            )
            data_client = StockHistoricalDataClient(
                api_key=settings.alpaca_api_key,
                secret_key=settings.alpaca_secret_key,
            )
            loop = asyncio.get_running_loop()

            # Step 1: drain hold list if market is now open
            await _drain_hold_list_if_open(trading_client, data_client, executor, loop)

            # Step 2: wait for next signal
            item: QueueItem = await signal_queue.get()

            # Step 3: process signal through all risk checks
            await _process_signal(item, trading_client, data_client, executor, loop)

            signal_queue.task_done()

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("risk_consumer: unhandled error — continuing: %s", exc)
```

### Daily Cap Check

```python
# [VERIFIED: D-10, D-11, D-12 from CONTEXT.md + alpaca-py str types verified]
async def _check_daily_cap(trading_client: TradingClient, loop: asyncio.AbstractEventLoop) -> bool:
    """Return True if daily cap is NOT hit (trading allowed). False if cap hit."""
    max_daily_loss = float(await _get_setting("max_daily_loss_dollars", "500.0"))
    try:
        account = await loop.run_in_executor(None, trading_client.get_account)
        equity_raw = account.equity
        last_equity_raw = account.last_equity
        if equity_raw is None or last_equity_raw is None:
            logger.warning("risk_consumer: equity fields None — skipping daily cap check")
            return True  # allow trade rather than block on data error
        equity = float(equity_raw)
        last_equity = float(last_equity_raw)
        daily_loss = last_equity - equity
        if daily_loss >= max_daily_loss:
            logger.warning(
                "risk_consumer: DAILY_CAP_HIT (loss=%.2f >= cap=%.2f)", daily_loss, max_daily_loss
            )
            return False
        return True
    except APIError as exc:
        logger.error("risk_consumer: get_account failed: %s — allowing trade", exc)
        return True  # fail open: don't block trades on API errors
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `loop` parameter on `asyncio.Queue()` | No `loop` parameter (removed) | Python 3.10 | Safe to instantiate queue at module level |
| `asyncio.CancelledError` is `Exception` subclass | `CancelledError` is `BaseException` subclass | Python 3.8 | `except Exception` no longer catches it — explicit re-raise unnecessary but still idiomatic |
| `alpaca-trade-api` (deprecated) | `alpaca-py` | 2023 | Never use `alpaca-trade-api` — project CLAUDE.md CRITICAL rule |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `QueueItem` dataclass is the right schema for queue items | Pattern 1 | Minor — can use TypedDict or named tuple; dataclass is idiomatic Python 3.11 |
| A2 | `_hold_list` as module-level list is acceptable given D-04 restart-loss policy | Pattern 4 | Low — D-04 explicitly accepts signal loss on restart |
| A3 | Consumer should re-instantiate `TradingClient` every loop iteration | Pattern 2 | Low risk — adds small overhead; could optimize to once per minute if needed |
| A4 | `QueueFull` should log + discard (not block analysis_worker) | Pattern 1 | Low — blocking analysis_worker would cause APScheduler misfire |
| A5 | Hold list de-dup (one trade per ticker at drain) is correct per D-08 | Pattern 4 | Medium — if not deduped, N orders placed for same ticker on open |

---

## Open Questions

1. **Where does QueueItem live?**
   - What we know: dataclass with 6 fields needed by consumer; must be importable by both `analysis_worker` and `guard.py`
   - What's unclear: should it be in `risk_guard/models.py`, `risk_guard/__init__.py`, or `risk_guard/guard.py`?
   - Recommendation: `risk_guard/models.py` — keeps guard.py focused on logic; `analysis_worker` imports from `risk_guard.models`

2. **Should the consumer update Signal.reason_code in DB when discarding?**
   - What we know: CONTEXT.md says log reason codes; DB already has `reason_code` on Signal
   - What's unclear: is logging sufficient, or should the Signal row be updated?
   - Recommendation: Update `Signal.reason_code` in the DB for full audit trail (ANLYS-04 spirit); adds one async DB update per discard

3. **AlpacaExecutor.execute() passes signal_id for DB logging?**
   - What we know: `executor.execute(symbol, side, qty)` — no signal_id parameter; `_log_order()` has `signal_id` as optional
   - What's unclear: should risk_guard call a new method that accepts signal_id?
   - Recommendation: Add `signal_id: int | None = None` parameter to `AlpacaExecutor.execute()` and thread it through to `_log_order()` — enables full audit chain (SC-4)

---

## Environment Availability

Step 2.6: SKIPPED (no new external dependencies — all tools are already installed: alpaca-py >= 0.20.0, pytz >= 2024.1, asyncio is stdlib)

---

## Validation Architecture

`nyquist_validation` is explicitly `false` in `.planning/config.json` — section skipped per instructions.

---

## Project Constraints (from CLAUDE.md)

All constraints below are CRITICAL rules from `./CLAUDE.md`:

1. **Never use `alpaca-trade-api`** — use `alpaca-py` (`from alpaca.trading.client import TradingClient`)
2. **Never use `requests`** — use `httpx` (though risk guard has no HTTP outbound calls beyond Alpaca SDK)
3. **Paper mode is default** — read `trading_mode` from app_settings; `TRADING_MODE=paper` unless explicitly set to `live`
4. **Bracket orders only** — stop-loss must be atomic with entry; risk guard calls `executor.execute()` which already enforces this
5. **Risk checks inside the queue** — all position sizing and daily loss cap checks happen inside the executor **after dequeue**. This is exactly what Phase 5 implements.
6. **Dashboard reads Alpaca live API** — never trust bot's internal state for money-related display (not applicable to risk guard, but don't add any balance caching)
7. **LLM never suggests new tickers** — risk guard only processes tickers that already passed through analysis_worker's watchlist filter; no new ticker injection

---

## Sources

### Primary (HIGH confidence)
- [VERIFIED: alpaca-py GitHub alpaca/trading/models.py] — `TradeAccount.equity`, `TradeAccount.last_equity` are `Optional[str]`; `Clock.is_open` is `bool`, `Clock.next_open`/`next_close` are `datetime`
- [VERIFIED: codebase — trumptrade/trading/executor.py] — `run_in_executor` pattern, `TradingClient` instantiation, `_get_setting()`, `_log_order()`
- [VERIFIED: codebase — trumptrade/analysis/worker.py] — `analysis_worker()` integration point; `put_nowait()` location; `signal.affected_tickers` is JSON string
- [VERIFIED: codebase — trumptrade/core/app.py] — `asyncio.create_task()` placement in lifespan, local import pattern
- [VERIFIED: codebase — trumptrade/ingestion/heartbeat.py] — pytz `America/New_York` pattern; `datetime.now(timezone.utc).astimezone()` pattern; naive UTC comparison pattern
- [VERIFIED: codebase — alembic/versions/004_analysis_app_settings.py] — `INSERT OR IGNORE` migration pattern
- [VERIFIED: codebase — alembic/versions/6e3709bc5279_initial_schema.py] — existing app_settings keys (`stop_loss_pct` already exists; `position_size_pct` and `max_daily_loss_pct` are old keys)
- [VERIFIED: pyproject.toml] — `requires-python = ">=3.11"` — confirms safe module-level `asyncio.Queue()` instantiation

### Secondary (MEDIUM confidence)
- [CITED: WebSearch — alpaca-py community/docs] — `float(account.equity)` and `float(account.last_equity)` conversion pattern; consistent across multiple sources
- [CITED: Python 3.10 asyncio changelog] — `loop` parameter removed from `asyncio.Queue`; no longer binds to running loop at creation time

### Tertiary (LOW confidence)
- None — all critical claims verified against codebase or official sources

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already installed; patterns verified in codebase
- Architecture: HIGH — verified from existing executor.py, app.py, worker.py, heartbeat.py
- Alpaca API fields: HIGH — verified from alpaca-py GitHub source (TradeAccount, Clock models)
- Pitfalls: HIGH — most verified from codebase patterns and Python stdlib docs
- After-hours hold logic: MEDIUM — D-16 decisions are locked but implementation pattern is ASSUMED (no existing precedent in codebase)

**Research date:** 2026-04-21
**Valid until:** 2026-05-21 (stable stack — alpaca-py, asyncio, pytz change slowly)

---

## RESEARCH COMPLETE

**Phase:** 5 - Risk Guard + Integration
**Confidence:** HIGH

### Key Findings

1. **asyncio.Queue is safe at module level in Python 3.11** — `requires-python = ">=3.11"` confirmed; no event loop binding at creation time.

2. **Alpaca equity fields are `Optional[str]`, not float** — verified from alpaca-py GitHub source. ALWAYS `float(account.equity)` before arithmetic. Handle `None` defensively.

3. **Use `get_clock().is_open` for market hours check** — handles holidays automatically. pytz is backup for fast pre-filter only.

4. **After-hours hold requires a separate `_hold_list`** — `asyncio.Queue` can't hold-and-release. Module-level list is acceptable per D-04 (restart = signal loss is accepted).

5. **`executor.execute()` raises `HTTPException`** — consumer must catch this specifically or it will crash the loop. `BotDisabledError` must also be caught separately.

6. **`stop_loss_pct` already exists in app_settings** — initial schema seeded it. Migration 005 only needs 3 new keys: `max_position_size_pct`, `max_daily_loss_dollars`, `signal_staleness_minutes`.

7. **signal_id linkage gap** — `executor.execute()` takes no `signal_id`; adding it as an optional parameter enables full audit chain (SC-4).

### File Created
`.planning/phases/05-risk-guard-integration/05-RESEARCH.md`

### Confidence Assessment
| Area | Level | Reason |
|------|-------|--------|
| Standard Stack | HIGH | All libraries already in pyproject.toml; verified installed |
| asyncio.Queue patterns | HIGH | Python 3.11 stdlib; module-level instantiation safe |
| Alpaca API field types | HIGH | Verified from alpaca-py GitHub source models.py |
| Market hours via get_clock() | HIGH | Verified from alpaca-py Clock model |
| After-hours hold list | MEDIUM | Pattern is new to this codebase; D-16 decision is locked but impl is ASSUMED |
| Alembic migration keys | HIGH | Cross-checked initial schema + 004 migration; no conflicts |
| Settings router pattern | HIGH | Verified directly from trading/router.py |

### Open Questions (for planner)
- QueueItem dataclass location: `risk_guard/models.py` recommended
- Signal.reason_code DB update on discard: recommend yes for full audit trail
- executor.execute() signal_id parameter: recommend adding optional param to enable full audit chain

### Ready for Planning
Research complete. Planner can now create PLAN.md files.
