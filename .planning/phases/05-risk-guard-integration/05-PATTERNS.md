# Phase 5: Risk Guard + Integration - Pattern Map

**Mapped:** 2026-04-21
**Files analyzed:** 7 new/modified files
**Analogs found:** 7 / 7

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `trumptrade/risk_guard/__init__.py` | package-init | event-driven | `trumptrade/analysis/__init__.py` | role-match |
| `trumptrade/risk_guard/guard.py` | service/consumer | event-driven | `trumptrade/analysis/worker.py` + `trumptrade/trading/executor.py` | role-match (composite) |
| `trumptrade/risk_guard/router.py` | controller | request-response | `trumptrade/trading/router.py` | exact |
| `trumptrade/analysis/worker.py` (patch) | service | event-driven | self (patch to existing file) | self |
| `trumptrade/trading/executor.py` (patch) | service | request-response | self (patch to existing file) | self |
| `trumptrade/core/app.py` (patch) | config/wiring | request-response | self (patch to existing file) | self |
| `alembic/versions/005_risk_settings.py` | migration | batch | `alembic/versions/004_analysis_app_settings.py` | exact |

---

## Pattern Assignments

### `trumptrade/risk_guard/__init__.py` (package-init, event-driven)

**Analog:** `trumptrade/analysis/__init__.py`

**Imports pattern** (`trumptrade/analysis/__init__.py` lines 1-7):
```python
from __future__ import annotations

"""Analysis package — LLM signal classification + APScheduler job registration (Phase 4)."""

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from trumptrade.analysis.worker import analysis_worker
```

**Core pattern** (`trumptrade/analysis/__init__.py` lines 10-32):
```python
def register_analysis_jobs(scheduler: AsyncIOScheduler) -> None:
    scheduler.add_job(
        analysis_worker,
        trigger="interval",
        seconds=30,
        id="analysis_worker",
        replace_existing=True,
        misfire_grace_time=15,
        coalesce=True,
        max_instances=1,
    )

__all__ = ["register_analysis_jobs"]
```

**Adaptation for `risk_guard/__init__.py`:**

The `risk_guard` package does NOT register APScheduler jobs — instead it exports:
1. `signal_queue` — module-level `asyncio.Queue(maxsize=100)` (safe in Python 3.11, per RESEARCH.md Pattern 1)
2. `settings_router` — re-exported from `risk_guard/router.py` (mirrors `trading/__init__.py` re-exporting `trading_router`)
3. `QueueItem` — dataclass (located in `risk_guard/guard.py` or a new `risk_guard/models.py`; import and re-export from `__init__.py`)

```python
# trumptrade/risk_guard/__init__.py — target structure
from __future__ import annotations

import asyncio
from trumptrade.risk_guard.router import router as settings_router
from trumptrade.risk_guard.guard import QueueItem

signal_queue: asyncio.Queue = asyncio.Queue(maxsize=100)

__all__ = ["signal_queue", "settings_router", "QueueItem"]
```

**Pattern note:** `trading/__init__.py` (lines 1-6) is the exact model for re-exporting a sub-module router:
```python
"""Trading package — AlpacaExecutor service and FastAPI router."""
from __future__ import annotations

from trumptrade.trading.router import router as trading_router

__all__ = ["trading_router"]
```

---

### `trumptrade/risk_guard/guard.py` (service/consumer, event-driven)

**Analog:** Composite of `trumptrade/analysis/worker.py` (async worker loop structure) + `trumptrade/trading/executor.py` (Alpaca client patterns + `_get_setting`)

**Imports pattern** (`trumptrade/trading/executor.py` lines 1-19):
```python
from __future__ import annotations

import asyncio
import logging
from functools import partial

from alpaca.common.exceptions import APIError
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestTradeRequest
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest, StopLossRequest
from fastapi import HTTPException
from sqlalchemy import select, update

from trumptrade.core.config import get_settings
from trumptrade.core.db import AsyncSessionLocal
from trumptrade.core.models import AppSettings, Order
```

**Additional imports needed in guard.py** (derived from RESEARCH.md + heartbeat.py):
```python
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytz
from sqlalchemy import select, update
from trumptrade.core.models import AppSettings, Signal
```

**`_get_setting()` pattern** (`trumptrade/analysis/worker.py` lines 44-51):
```python
async def _get_app_setting(key: str, default: str) -> str:
    """Read a single app_settings value; return default if not found (Pitfall 6: per-cycle)."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AppSettings.value).where(AppSettings.key == key)
        )
        val = result.scalar_one_or_none()
        return val if val is not None else default
```

Use `scalar_one_or_none()` with a `default` fallback (analysis/worker.py pattern), NOT `scalar_one()` (executor.py pattern) — the latter raises `NoResultFound` if the key is missing.

**TradingClient instantiation pattern** (`trumptrade/trading/executor.py` lines 36-53):
```python
# STEP 2: Read runtime settings from DB (re-read per request per D-06 — no caching)
trading_mode = await self._get_setting("trading_mode")   # "paper" | "live"
stop_loss_pct = float(await self._get_setting("stop_loss_pct"))  # "5.0" → 5.0
is_paper = (trading_mode == "paper")

# STEP 3: Instantiate clients per-request (NOT cached — D-06 requires mode re-read)
settings = get_settings()
try:
    trading_client = TradingClient(
        api_key=settings.alpaca_api_key,
        secret_key=settings.alpaca_secret_key,
        paper=is_paper,
    )
    data_client = StockHistoricalDataClient(
        api_key=settings.alpaca_api_key,
        secret_key=settings.alpaca_secret_key,
    )
except ValueError as exc:
    raise HTTPException(status_code=502, detail=f"Alpaca credentials not configured: {exc}")
```

In guard.py the `ValueError` branch should log + continue (no HTTPException) since there is no HTTP context.

**run_in_executor pattern** (`trumptrade/trading/executor.py` lines 56-68):
```python
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
    logger.error("Alpaca data API error fetching price for %s: %s", symbol, exc)
    raise HTTPException(status_code=502, detail=f"Alpaca data error: {exc.message}")
last_price: float = trade_map[symbol].price
```

For `get_account()` and `get_clock()` (no args), pass the callable directly without `partial()`:
```python
account = await loop.run_in_executor(None, trading_client.get_account)
clock = await loop.run_in_executor(None, trading_client.get_clock)
```

**pytz market-hours pattern** (`trumptrade/ingestion/heartbeat.py` lines 16-26):
```python
_EASTERN = pytz.timezone("US/Eastern")

def _is_market_hours(start_hour: int = 9, end_hour: int = 17) -> bool:
    now_et = datetime.now(timezone.utc).astimezone(_EASTERN)
    return start_hour <= now_et.hour < end_hour
```

For risk_guard, use `America/New_York` (canonical IANA, equivalent to `US/Eastern`). The key idiom is `datetime.now(timezone.utc).astimezone(_EASTERN)` — never `_EASTERN.localize(datetime.now())`.

**Naive UTC comparison pattern** (`trumptrade/ingestion/heartbeat.py` lines 57-58):
```python
cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=30)
```

Use `datetime.now(timezone.utc).replace(tzinfo=None)` to get naive UTC, matching SQLite's stored datetimes. Apply same pattern for staleness check: `(now_naive_utc - item.posted_at).total_seconds()`.

**Consumer loop error handling pattern** (RESEARCH.md Pattern 1 — `asyncio.CancelledError` must be re-raised):
```python
while True:
    try:
        # ... consumer logic ...
    except asyncio.CancelledError:
        raise  # CRITICAL: let CancelledError propagate — never swallow it
    except Exception as exc:
        logger.exception("risk_consumer: unhandled error — continuing: %s", exc)
```

**`BotDisabledError` exception handling pattern** (`trumptrade/trading/executor.py` lines 23-33 + `trumptrade/trading/router.py` lines 43-47):
```python
# executor.py — declaration
class BotDisabledError(Exception):
    """Raised when bot_enabled=false in app_settings."""

# executor.py — kill-switch check
bot_enabled_raw = await self._get_setting("bot_enabled")
if bot_enabled_raw != "true":           # CRITICAL: compare to string "true", NOT bool()
    raise BotDisabledError()
```

In the consumer, import `BotDisabledError` from `trumptrade.trading.executor` and catch it separately (log + continue, not an error).

**DB write pattern for Signal update** (`trumptrade/trading/executor.py` lines 108-116):
```python
async def set_bot_enabled(self, enabled: bool) -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(AppSettings)
            .where(AppSettings.key == "bot_enabled")
            .values(value="true" if enabled else "false")
        )
        await session.commit()
```

Adapt this pattern to update `Signal.reason_code` when discarding a signal in the consumer.

**QueueItem dataclass** (RESEARCH.md Pattern 1 — no existing codebase precedent):
```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class QueueItem:
    signal_id: int
    post_id: int
    tickers: list[str]       # already parsed from JSON by analysis_worker
    side: str                # "BUY" | "SELL"
    confidence: float
    posted_at: datetime      # post.posted_at — naive UTC from SQLite
```

Place `QueueItem` in `guard.py` (or a `risk_guard/models.py`). Import and re-export from `__init__.py`.

---

### `trumptrade/risk_guard/router.py` (controller, request-response)

**Analog:** `trumptrade/trading/router.py` — exact role and data flow match

**Full imports pattern** (`trumptrade/trading/router.py` lines 1-10):
```python
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from trumptrade.trading.executor import AlpacaExecutor, BotDisabledError

logger = logging.getLogger(__name__)

router = APIRouter()
_executor = AlpacaExecutor()   # module-level instance — keeps HTTP layer thin
```

For `risk_guard/router.py`, the module-level instance is not needed (no executor dependency). Replace with DB session calls directly or a helper:
```python
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select, update

from trumptrade.core.db import AsyncSessionLocal
from trumptrade.core.models import AppSettings

logger = logging.getLogger(__name__)

router = APIRouter()
```

**Pydantic request/response model pattern** (`trumptrade/trading/router.py` lines 16-33):
```python
class ExecuteSignalRequest(BaseModel):
    symbol: str
    side: str        # "buy" | "sell"
    qty: float = Field(gt=0)   # Security: reject zero or negative quantity at validation layer

class ExecuteSignalResponse(BaseModel):
    order_id: str
    status: str
```

For `risk_guard/router.py`:
```python
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
```

**Route handler pattern** (`trumptrade/trading/router.py` lines 36-48):
```python
@router.post("/execute", response_model=ExecuteSignalResponse)
async def execute_signal(body: ExecuteSignalRequest) -> ExecuteSignalResponse:
    """Place a bracket order on Alpaca. Returns order_id on success."""
    try:
        result = await _executor.execute(body.symbol, body.side, body.qty)
        return ExecuteSignalResponse(**result)
    except BotDisabledError:
        raise HTTPException(status_code=503, detail={"error": "bot_disabled"})
```

For `risk_guard/router.py`, GET reads all 4 setting keys; PATCH updates only non-None fields:
```python
@router.get("/risk", response_model=RiskSettingsResponse)
async def get_risk_settings() -> RiskSettingsResponse:
    async with AsyncSessionLocal() as session:
        # read all 4 keys via individual scalar queries (matching executor._get_setting pattern)
        ...

@router.patch("/risk", response_model=RiskSettingsResponse)
async def patch_risk_settings(body: RiskSettingsPatch) -> RiskSettingsResponse:
    async with AsyncSessionLocal() as session:
        for key, value in body.model_dump(exclude_none=True).items():
            await session.execute(
                update(AppSettings)
                .where(AppSettings.key == key)
                .values(value=str(value))
            )
        await session.commit()
    return await get_risk_settings()  # return updated values
```

---

### `trumptrade/analysis/worker.py` (patch — enqueue BUY/SELL signals)

**Analog:** Self — insert enqueue block immediately after `await session.commit()` in the Signal insert block.

**Insertion point** (`trumptrade/analysis/worker.py` lines 275-289):
```python
        async with AsyncSessionLocal() as session:
            session.add(signal)
            await session.commit()

        inserted += 1
        logger.info(
            "analysis_worker: post_id=%d → action=%s sentiment=%s confidence=%.2f "
            "tickers=%s reason=%s",
            post.id,
            final_action,
            signal_result.sentiment,
            signal_result.confidence,
            final_tickers,
            reason_code,
        )
```

Insert after `await session.commit()` and before `inserted += 1`:
```python
        # Phase 5: enqueue BUY/SELL signals onto risk_guard queue (D-01)
        if final_action in ("BUY", "SELL") and final_tickers:
            from trumptrade.risk_guard import signal_queue, QueueItem  # local import — avoids circular
            item = QueueItem(
                signal_id=signal.id,
                post_id=post.id,
                tickers=final_tickers,           # already list[str]; no json.loads() needed
                side=final_action,
                confidence=signal_result.confidence,
                posted_at=post.posted_at,        # naive UTC datetime from SQLite
            )
            try:
                signal_queue.put_nowait(item)
            except asyncio.QueueFull:
                logger.warning(
                    "analysis_worker: signal_queue full — discarding signal_id=%d", signal.id
                )
```

Note: `asyncio` is not yet imported in `worker.py` — add `import asyncio` to the imports block at the top.

**Local import pattern for circular-import avoidance** (`trumptrade/core/app.py` lines 71-80):
```python
from trumptrade.trading import trading_router          # local import avoids circular import
app.include_router(trading_router, prefix="/trading", tags=["trading"])

from trumptrade.ingestion import register_ingestion_jobs  # local import avoids circular import
register_ingestion_jobs(scheduler)

from trumptrade.analysis import register_analysis_jobs  # local import avoids circular import
register_analysis_jobs(scheduler)
```

The same local-import pattern is used inside function bodies throughout the codebase. The `from trumptrade.risk_guard import ...` import in `analysis_worker` must be a local import (inside the loop body) to avoid circular imports.

---

### `trumptrade/trading/executor.py` (patch — add `signal_id` parameter)

**Analog:** Self — minimal signature change to `execute()` and `_log_order()`.

**Current `execute()` signature** (`trumptrade/trading/executor.py` line 29):
```python
async def execute(self, symbol: str, side: str, qty: float) -> dict:
```

**Patched signature** (add optional `signal_id`):
```python
async def execute(self, symbol: str, side: str, qty: float, signal_id: int | None = None) -> dict:
```

**Current `_log_order()` call** (`trumptrade/trading/executor.py` line 103):
```python
await self._log_order(alpaca_order_id, symbol, side, qty, trading_mode)
```

**Patched call:**
```python
await self._log_order(alpaca_order_id, symbol, side, qty, trading_mode, signal_id=signal_id)
```

**Current `_log_order()` signature** (`trumptrade/trading/executor.py` lines 127-129):
```python
async def _log_order(
    self, alpaca_order_id: str, symbol: str, side: str, qty: float, trading_mode: str
) -> None:
```

**Patched signature:**
```python
async def _log_order(
    self, alpaca_order_id: str, symbol: str, side: str, qty: float, trading_mode: str,
    signal_id: int | None = None,
) -> None:
```

**Current `_log_order()` body** (`trumptrade/trading/executor.py` lines 130-142):
```python
        async with AsyncSessionLocal() as session:
            session.add(Order(
                alpaca_order_id=alpaca_order_id,
                symbol=symbol,
                side=side,
                qty=qty,
                order_type="bracket",
                status="submitted",
                trading_mode=trading_mode,
                # signal_id omitted — nullable=True; stub/test orders have no signal
            ))
            await session.commit()
```

**Patched body** (pass `signal_id` through to `Order`):
```python
        async with AsyncSessionLocal() as session:
            session.add(Order(
                alpaca_order_id=alpaca_order_id,
                symbol=symbol,
                side=side,
                qty=qty,
                order_type="bracket",
                status="submitted",
                trading_mode=trading_mode,
                signal_id=signal_id,  # Phase 5: links order to signal for full audit chain (SC-4)
            ))
            await session.commit()
```

---

### `trumptrade/core/app.py` (patch — wire Phase 5 lifespan block)

**Analog:** Self — insert risk consumer task into existing `lifespan()` and settings router into `create_app()`.

**Current lifespan pattern** (`trumptrade/core/app.py` lines 27-53):
```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    logger.info("TrumpTrade starting", extra={"db_url": settings.db_url, "debug": settings.debug})

    # STARTUP
    scheduler.start()
    logger.info("APScheduler started — ready to receive jobs")

    yield  # Application runs here

    # SHUTDOWN
    scheduler.shutdown(wait=False)
    logger.info("APScheduler stopped")
```

**Patched lifespan** (add `_consumer_task` around the `yield`):
```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    logger.info("TrumpTrade starting", extra={"db_url": settings.db_url, "debug": settings.debug})

    # STARTUP
    scheduler.start()
    logger.info("APScheduler started — ready to receive jobs")

    # Phase 5: start risk consumer task (D-03 — asyncio.create_task, not APScheduler)
    from trumptrade.risk_guard.guard import risk_consumer  # local import — avoids circular
    _consumer_task = asyncio.create_task(risk_consumer(), name="risk_consumer")
    logger.info("Risk consumer task started")

    yield  # Application runs here

    # SHUTDOWN
    _consumer_task.cancel()
    try:
        await _consumer_task
    except asyncio.CancelledError:
        pass
    logger.info("Risk consumer task stopped")

    scheduler.shutdown(wait=False)
    logger.info("APScheduler stopped")
```

Add `import asyncio` to the top-level imports in `app.py`.

**Current `create_app()` router registration pattern** (`trumptrade/core/app.py` lines 71-80):
```python
    from trumptrade.trading import trading_router          # local import avoids circular import
    app.include_router(trading_router, prefix="/trading", tags=["trading"])
```

**Phase 5 addition to `create_app()`** (insert after trading router registration):
```python
    # ── Phase 5: risk settings router ───────────────────────────────────────
    from trumptrade.risk_guard import settings_router      # local import avoids circular import
    app.include_router(settings_router, prefix="/settings", tags=["settings"])
```

---

### `alembic/versions/005_risk_settings.py` (migration, batch)

**Analog:** `alembic/versions/004_analysis_app_settings.py` — exact match

**Full analog file** (`alembic/versions/004_analysis_app_settings.py` lines 1-31):
```python
"""analysis_app_settings

Revision ID: 004
Revises: 6e3709bc5279
Create Date: 2026-04-21

Seeds llm_provider, llm_model, confidence_threshold defaults into app_settings.
Uses INSERT OR IGNORE so existing values are never overwritten.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "004"
down_revision: Union[str, Sequence[str], None] = "6e3709bc5279"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("INSERT OR IGNORE INTO app_settings (key, value) VALUES ('llm_provider', 'anthropic')")
    op.execute("INSERT OR IGNORE INTO app_settings (key, value) VALUES ('llm_model', 'claude-haiku-4-5-20251001')")
    op.execute("INSERT OR IGNORE INTO app_settings (key, value) VALUES ('confidence_threshold', '0.7')")


def downgrade() -> None:
    op.execute(
        "DELETE FROM app_settings WHERE key IN ('llm_provider', 'llm_model', 'confidence_threshold')"
    )
```

**Phase 5 migration target structure:**
```python
"""risk_settings

Revision ID: 005
Revises: 004
Create Date: 2026-04-21

Seeds max_position_size_pct, max_daily_loss_dollars, signal_staleness_minutes into app_settings.
Uses INSERT OR IGNORE so existing values are never overwritten.
Note: stop_loss_pct already exists from initial schema — NOT re-inserted here.
Note: position_size_pct and max_daily_loss_pct (old keys from initial schema) are preserved
      untouched; Phase 5 uses new keys with different names/semantics.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "005"
down_revision: Union[str, Sequence[str], None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("INSERT OR IGNORE INTO app_settings (key, value) VALUES ('max_position_size_pct', '2.0')")
    op.execute("INSERT OR IGNORE INTO app_settings (key, value) VALUES ('max_daily_loss_dollars', '500.0')")
    op.execute("INSERT OR IGNORE INTO app_settings (key, value) VALUES ('signal_staleness_minutes', '5')")


def downgrade() -> None:
    op.execute(
        "DELETE FROM app_settings WHERE key IN "
        "('max_position_size_pct', 'max_daily_loss_dollars', 'signal_staleness_minutes')"
    )
```

---

## Shared Patterns

### `_get_setting()` Helper — Per-Cycle DB Read
**Source:** `trumptrade/analysis/worker.py` lines 44-51
**Apply to:** `risk_guard/guard.py`, `risk_guard/router.py`

```python
async def _get_app_setting(key: str, default: str = "") -> str:
    """Read a single app_settings value; return default if not found."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AppSettings.value).where(AppSettings.key == key)
        )
        val = result.scalar_one_or_none()
        return val if val is not None else default
```

Use `scalar_one_or_none()` with default (not `scalar_one()` which raises on missing key).

### Alpaca SDK `run_in_executor` Wrapper
**Source:** `trumptrade/trading/executor.py` lines 56-68
**Apply to:** `risk_guard/guard.py` (for `get_account()`, `get_clock()`, price lookups)

All Alpaca SDK calls are synchronous. Every call must be wrapped:
```python
loop = asyncio.get_running_loop()
result = await loop.run_in_executor(None, trading_client.get_account)   # no-arg: direct callable
result = await loop.run_in_executor(
    None,
    partial(data_client.get_stock_latest_trade, StockLatestTradeRequest(symbol_or_symbols=symbol))
)  # with-arg: use partial()
```

### Local Import Pattern (Circular Import Avoidance)
**Source:** `trumptrade/core/app.py` lines 71-80
**Apply to:** All new imports in `app.py` lifespan and `create_app()`; `analysis_worker.py` enqueue block

```python
from trumptrade.risk_guard.guard import risk_consumer  # local import — avoids circular
```

### String-to-Float Conversion for Alpaca Fields
**Source:** RESEARCH.md Pattern 2 (verified from alpaca-py source)
**Apply to:** `risk_guard/guard.py` — all account equity field reads

```python
equity_raw = account.equity
last_equity_raw = account.last_equity
if equity_raw is None or last_equity_raw is None:
    logger.warning("risk_consumer: equity fields are None — skipping daily cap check")
    # proceed without cap check rather than blocking all trades
else:
    equity = float(equity_raw)
    last_equity = float(last_equity_raw)
```

### Naive UTC Datetime for SQLite Comparison
**Source:** `trumptrade/ingestion/heartbeat.py` lines 57-58
**Apply to:** `risk_guard/guard.py` staleness check

```python
# SQLite stores datetimes as naive strings; compare with naive UTC
now_naive_utc = datetime.now(timezone.utc).replace(tzinfo=None)
age_seconds = (now_naive_utc - item.posted_at).total_seconds()
```

### `asyncio.CancelledError` in Consumer Loops
**Source:** RESEARCH.md Pattern 1 (verified Python 3.8+ behavior)
**Apply to:** `risk_guard/guard.py` consumer loop

```python
try:
    ...
except asyncio.CancelledError:
    raise  # CRITICAL: re-raise; never swallow in consumer — prevents graceful shutdown
except Exception as exc:
    logger.exception("risk_consumer: unhandled error — continuing: %s", exc)
```

### `INSERT OR IGNORE` Migration Pattern
**Source:** `alembic/versions/004_analysis_app_settings.py` line 22
**Apply to:** `alembic/versions/005_risk_settings.py`

```python
op.execute("INSERT OR IGNORE INTO app_settings (key, value) VALUES ('key_name', 'default_value')")
```

---

## No Analog Found

All files have analogs. No gaps.

| File | Role | Data Flow | Notes |
|------|------|-----------|-------|
| After-hours hold list (`_hold_list`) | sub-pattern within `guard.py` | event-driven | No existing in-memory hold list in codebase — RESEARCH.md Pattern 4 provides the design; treat as new |

---

## Critical Implementation Notes for Planner

1. **`asyncio.Queue(maxsize=100)` at module level is safe** — Python 3.11 confirmed in `pyproject.toml`. No event loop binding at creation time.

2. **`final_tickers` in `analysis_worker` is already `list[str]`** (line 248: `final_action, reason_code, final_tickers, keyword_matches = _apply_keyword_overlay(...)`). No `json.loads()` needed when building `QueueItem.tickers`.

3. **`signal.id` is available after `await session.commit()`** — SQLAlchemy 2.x async: after `commit()`, the `signal.id` is populated (autoincrement primary key assigned by SQLite). No refresh needed for integer PKs in this ORM configuration.

4. **`trading/router.py` catches `BotDisabledError` from `executor.execute()`** — the consumer must also catch it (log INFO + continue, not ERROR — it's expected behavior when kill switch is off).

5. **`stop_loss_pct` already in app_settings from initial schema** — do NOT insert it in migration 005. The settings router's `GET /settings/risk` should read the existing key.

6. **`Order.signal_id` column** — verify it exists as a nullable FK in `core/models.py` before patching `executor.py`. The existing comment on line 141 (`# signal_id omitted — nullable=True`) confirms it exists.

---

## Metadata

**Analog search scope:** `trumptrade/analysis/`, `trumptrade/trading/`, `trumptrade/ingestion/`, `trumptrade/core/`, `alembic/versions/`
**Files scanned:** 9 files read in full
**Pattern extraction date:** 2026-04-21
