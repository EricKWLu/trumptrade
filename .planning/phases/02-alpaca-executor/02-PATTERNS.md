# Phase 2: Alpaca Executor - Pattern Map

**Mapped:** 2026-04-19
**Files analyzed:** 4 (new/modified)
**Analogs found:** 3 / 4 (1 partial — no existing routers yet; `create_app` is the anchor)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `trumptrade/trading/executor.py` | service | request-response + CRUD write | `trumptrade/core/db.py` (session pattern) + `trumptrade/core/models.py` (Order model) | role-match (no service classes exist yet) |
| `trumptrade/trading/router.py` | router | request-response | `trumptrade/core/app.py` (`create_app` + `/health` handler) | role-match (only existing route file) |
| `trumptrade/trading/__init__.py` | config/export | — | `trumptrade/dashboard/__init__.py` (stub comment style) | exact (same stub pattern) |
| `trumptrade/core/app.py` | config | — | itself (modification only — add `include_router` call) | exact |

---

## Pattern Assignments

### `trumptrade/trading/executor.py` (service, request-response + CRUD write)

**Analog:** `trumptrade/core/db.py` (session factory pattern) and `trumptrade/core/models.py` (model field names)

**Imports pattern** — copy from `trumptrade/core/db.py` lines 1-16 and `trumptrade/core/models.py` lines 1-18:

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

**`from __future__ import annotations` rule:** Every existing Python file in the project starts with this line (`app.py` line 8, `db.py` line 1, `models.py` line 1, `config.py` line 1). Apply to all new files.

**Logger declaration pattern** — from `trumptrade/core/app.py` line 19:

```python
logger = logging.getLogger(__name__)
```

**AsyncSessionLocal read pattern** — from `trumptrade/core/db.py` lines 43-49 (how `get_db` uses it; service layer uses same context manager directly):

```python
# Route handler uses Depends(get_db) — service layer opens its own:
async with AsyncSessionLocal() as session:
    result = await session.execute(
        select(AppSettings.value).where(AppSettings.key == key)
    )
    return result.scalar_one()
```

Key detail from `db.py` line 29: `expire_on_commit=False` is already set on the factory — safe to read attributes after commit without triggering lazy loads.

**AppSettings write pattern** — `update()` with explicit `commit()`:

```python
async with AsyncSessionLocal() as session:
    await session.execute(
        update(AppSettings)
        .where(AppSettings.key == "bot_enabled")
        .values(value="true" if enabled else "false")
    )
    await session.commit()
```

**Order model field names** — from `trumptrade/core/models.py` lines 114-141:

```python
# Exact column names required for Order(...) constructor:
Order(
    alpaca_order_id=str(alpaca_order.id),   # String(64), unique — UUID must be str()
    symbol=symbol,                           # String(10)
    side=side,                               # String(4): "buy" | "sell"
    qty=qty,                                 # Float
    order_type="bracket",                    # String(20), default="bracket"
    status="submitted",                      # String(20), default="submitted"
    trading_mode=trading_mode,               # String(5): "paper" | "live"
    # signal_id omitted — nullable=True, stub orders have no signal
)
```

**AppSettings seeded values** — from migration `alembic/versions/6e3709bc5279_initial_schema.py` lines 113-125:

```
key='trading_mode'   → value='paper'   (string)
key='bot_enabled'    → value='false'   (string — NOT Python False)
key='stop_loss_pct'  → value='5.0'     (string — cast to float)
```

Critical: `bot_enabled == "true"` check, not `bool(value)` — `"false"` is truthy in Python.

**run_in_executor pattern** for synchronous alpaca-py calls (no async methods exist in alpaca-py 0.43.2):

```python
loop = asyncio.get_running_loop()

# For calls with no kwargs:
alpaca_order = await loop.run_in_executor(
    None, trading_client.submit_order, order_request
)

# For calls requiring kwargs (use partial):
trade_map = await loop.run_in_executor(
    None,
    partial(data_client.get_stock_latest_trade,
            StockLatestTradeRequest(symbol_or_symbols=symbol))
)
last_price: float = trade_map[symbol].price
```

**Error handling pattern** — raise `HTTPException` from service, let FastAPI serialize it:

```python
try:
    alpaca_order = await loop.run_in_executor(
        None, trading_client.submit_order, order_request
    )
except APIError as e:
    if e.status_code == 403:
        raise HTTPException(status_code=502, detail="Alpaca auth failed")
    elif e.status_code == 422:
        raise HTTPException(status_code=400, detail=f"Invalid order: {e.message}")
    elif e.status_code == 429:
        raise HTTPException(status_code=429, detail="Alpaca rate limit exceeded")
    else:
        raise HTTPException(status_code=502, detail=f"Alpaca error: {e.message}")
```

**Custom exception for kill-switch** (bot disabled before any network call):

```python
class BotDisabledError(Exception):
    """Raised when bot_enabled=false in app_settings."""
```

Map to HTTP 503 in the router, not inside the service — keeps service logic clean and reusable by Phase 5 queue consumer.

**TradingClient instantiation — per-request, never cached** (D-06):

```python
settings = get_settings()
is_paper = (trading_mode == "paper")
trading_client = TradingClient(
    api_key=settings.alpaca_api_key,
    secret_key=settings.alpaca_secret_key,
    paper=is_paper,
)
data_client = StockHistoricalDataClient(
    api_key=settings.alpaca_api_key,
    secret_key=settings.alpaca_secret_key,
)
```

`get_settings()` is `@lru_cache` (config.py line 34) — safe to call repeatedly; returns same singleton. Client objects are NOT cached.

**Stop price calculation** (D-02 + pitfall 5):

```python
stop_price = round(last_price * (1 - stop_loss_pct / 100), 2)
```

**Bracket order construction** (D-03 + TRADE-03):

```python
order_request = MarketOrderRequest(
    symbol=symbol,
    qty=qty,
    side=OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL,
    time_in_force=TimeInForce.DAY,        # DAY safer than GTC in paper mode
    order_class=OrderClass.BRACKET,
    stop_loss=StopLossRequest(stop_price=stop_price),
    # take_profit omitted — Phase 2 scope
)
```

---

### `trumptrade/trading/router.py` (router, request-response)

**Analog:** `trumptrade/core/app.py` (the only existing FastAPI file with route definitions — `/health` handler at lines 70-76)

**Imports pattern** — based on `app.py` import style (lines 8-17):

```python
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from trumptrade.trading.executor import AlpacaExecutor, BotDisabledError

logger = logging.getLogger(__name__)
```

**Router declaration pattern** — from `app.py` line 63 (`FastAPI(...)`) adapted to `APIRouter`:

```python
router = APIRouter()
```

**Module-level service instance** (thin HTTP layer pattern per CONTEXT.md discretion):

```python
_executor = AlpacaExecutor()
```

**Pydantic request/response models** — project uses Pydantic v2 (pyproject.toml line 13: `pydantic>=2.7.0`); use `BaseModel` with `Field` for constraints:

```python
class ExecuteSignalRequest(BaseModel):
    symbol: str
    side: str        # "buy" | "sell"
    qty: float = Field(gt=0)   # security: reject zero/negative qty

class ExecuteSignalResponse(BaseModel):
    order_id: str
    status: str

class KillSwitchRequest(BaseModel):
    enabled: bool

class KillSwitchResponse(BaseModel):
    bot_enabled: bool
    ok: bool
```

**Route handler pattern** — from `app.py` lines 70-76 (`/health` handler as model):

```python
@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "scheduler_running": scheduler.running,
    }
```

Adapted for trading routes:

```python
@router.post("/execute")
async def execute_signal(body: ExecuteSignalRequest) -> ExecuteSignalResponse:
    try:
        result = await _executor.execute(body.symbol, body.side, body.qty)
        return ExecuteSignalResponse(**result)
    except BotDisabledError:
        raise HTTPException(status_code=503, detail={"error": "bot_disabled"})

@router.post("/kill-switch")
async def kill_switch(body: KillSwitchRequest) -> KillSwitchResponse:
    await _executor.set_bot_enabled(body.enabled)
    return KillSwitchResponse(bot_enabled=body.enabled, ok=True)
```

---

### `trumptrade/trading/__init__.py` (config/export)

**Analog:** `trumptrade/dashboard/__init__.py` (line 1) — exact stub-to-export evolution

**Before (stub):**
```python
# Stub — implementation added in Phase 3/4/5/6 respectively
```

**After (Phase 2 export):**
```python
"""Trading package — AlpacaExecutor and FastAPI router."""
from trumptrade.trading.router import router as trading_router

__all__ = ["trading_router"]
```

---

### `trumptrade/core/app.py` (modification — add router registration)

**Analog:** itself (lines 56-78 `create_app()`)

**Current `create_app()` body** (lines 63-78) — add `include_router` after `FastAPI(...)` construction, before return:

```python
# ADD after FastAPI(...) construction:
from trumptrade.trading import trading_router
app.include_router(trading_router, prefix="/trading", tags=["trading"])
```

Full insertion point — after line 68 (closing paren of `FastAPI(...)`), before line 70 (`@app.get("/health")`):

```python
def create_app() -> FastAPI:
    app = FastAPI(
        title="TrumpTrade",
        version="0.1.0",
        description="Automated Trump social media trading bot",
        lifespan=lifespan,
    )

    # ── Phase 2: trading router ──────────────────────────────────────────
    from trumptrade.trading import trading_router          # local import avoids
    app.include_router(trading_router, prefix="/trading", tags=["trading"])  # circular

    @app.get("/health")
    async def health() -> dict:
        ...

    return app
```

Use a local import inside `create_app()` (not top-level) to avoid circular import risk — `trading/executor.py` imports from `trumptrade.core.*`, so a top-level import in `app.py` could create a cycle at module load time.

---

## Shared Patterns

### `from __future__ import annotations`
**Source:** All existing Python files (`app.py` line 8, `db.py` line 1, `models.py` line 1, `config.py` line 1)
**Apply to:** `executor.py`, `router.py`
First line of every `.py` file in `trumptrade/`.

### Logger Declaration
**Source:** `trumptrade/core/app.py` line 19
**Apply to:** `executor.py`, `router.py`
```python
logger = logging.getLogger(__name__)
```

### AsyncSessionLocal Context Manager
**Source:** `trumptrade/core/db.py` lines 29-33 (factory declaration) and lines 43-49 (usage in `get_db`)
**Apply to:** `executor.py` — all DB reads and writes use `async with AsyncSessionLocal() as session:`
Never use `Depends(get_db)` inside service classes — that dependency injection only works in FastAPI route function signatures.

### Pydantic v2 Models
**Source:** `trumptrade/core/config.py` lines 9-28 (`Settings(BaseSettings)`)
**Apply to:** `router.py` request/response models
Project uses pydantic v2 (`pydantic>=2.7.0`). Use `model_config`, `Field`, `BaseModel` from `pydantic`. No `class Config:` inner class (v1 style).

### `get_settings()` Access
**Source:** `trumptrade/core/config.py` lines 34-41
**Apply to:** `executor.py`
```python
from trumptrade.core.config import get_settings
settings = get_settings()   # @lru_cache — safe to call per-request
```
`settings.alpaca_api_key` and `settings.alpaca_secret_key` are the only Alpaca credentials. Never log them.

---

## No Analog Found

No files fall into this category — all four files have sufficient analogs from the existing codebase. The RESEARCH.md patterns fill any gaps for the alpaca-py specifics (which are new to Phase 2).

---

## Metadata

**Analog search scope:** `trumptrade/core/`, `trumptrade/dashboard/`, `trumptrade/trading/`, `trumptrade/ingestion/`, `trumptrade/analysis/`, `trumptrade/risk/`, `alembic/versions/`
**Files scanned:** 9 source files + 1 migration file
**Pattern extraction date:** 2026-04-19

**Key finding:** No routers or service classes exist in the codebase yet — `trumptrade/core/app.py` is the only FastAPI file, containing a single inline `GET /health` handler. All router and service patterns are therefore inferred from `app.py`'s conventions (import style, `from __future__ import annotations`, `logging.getLogger(__name__)`, Pydantic v2, `lifespan` over `@app.on_event`) plus the DB session patterns in `db.py` and model field names from `models.py`.
