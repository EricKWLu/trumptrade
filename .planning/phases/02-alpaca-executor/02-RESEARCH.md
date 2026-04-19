# Phase 2: Alpaca Executor - Research

**Researched:** 2026-04-19
**Domain:** alpaca-py TradingClient, FastAPI async service pattern, SQLAlchemy 2.x async write
**Confidence:** HIGH (all claims verified against installed package source)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Executor exposes `POST /trading/execute` accepting a signal payload (ticker, side, qty). This is the real executor entry point — Phase 5 (risk guard) will call this same endpoint from the asyncio.Queue consumer. Paper mode is active by default; stub signals go directly to Alpaca paper environment.
- **D-02:** Use market orders for the entry leg. Fetch the current last trade price from the Alpaca data API before submitting, then calculate: `stop_price = last_price * (1 - stop_loss_pct / 100)`. `stop_loss_pct` is read from `app_settings` DB table (seeded at 5.0). Market orders fill immediately in paper mode.
- **D-03:** Bracket orders use `alpaca-py` `MarketOrderRequest` with `order_class=OrderClass.BRACKET`. The `stop_loss` leg is a `StopLossRequest(stop_price=calculated_price)`. No `take_profit` leg in Phase 2. Stop-loss is ALWAYS part of the bracket submission — never a separate order (TRADE-03).
- **D-04:** Log the Alpaca order ID returned on submission to the `orders` table. "Confirmed" means Alpaca accepted and assigned an order ID — not waiting for fill status. No polling in Phase 2. `orders.status` is set to `"submitted"` at creation.
- **D-05:** `POST /trading/kill-switch` with body `{"enabled": bool}`. Updates `bot_enabled` in `app_settings`. Returns `{"bot_enabled": bool, "ok": true}`. The executor checks `bot_enabled` before every order placement — if false, returns 503 with `{"error": "bot_disabled"}`.
- **D-06:** `trading_mode` is read from `app_settings` at executor startup (not cached — re-read per request so DB changes take effect immediately). `"paper"` → Alpaca paper endpoint. `"live"` → live endpoint. Alpaca client is instantiated inside the executor service based on this value.

### Claude's Discretion
- Executor service architecture: `AlpacaExecutor` service class with `async def execute(signal)` method, called by the route handler. This keeps the HTTP layer thin and makes Phase 5 wiring cleaner.
- Pydantic request/response models for `POST /trading/execute` and `POST /trading/kill-switch`.
- Error handling: invalid ticker, Alpaca API error, and missing credentials each return appropriate 4xx/5xx with structured JSON.

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TRADE-01 | User can run the bot in paper trading mode (Alpaca paper environment — simulated money, real prices) as the default mode | `TradingClient(paper=True)` verified as constructor flag; `trading_mode` seeded as `"paper"` in migration |
| TRADE-03 | System places all entry orders as Alpaca bracket orders (atomic entry + stop-loss) — never two separate submissions | `MarketOrderRequest(order_class=OrderClass.BRACKET, stop_loss=StopLossRequest(stop_price=X))` verified against package source |
</phase_requirements>

---

## Summary

Phase 2 builds the Alpaca executor: a FastAPI router with two endpoints (`POST /trading/execute` and `POST /trading/kill-switch`) plus an `AlpacaExecutor` service class that handles bracket order placement, kill-switch enforcement, and DB logging. All decisions are locked via CONTEXT.md so research is focused on verifying exact API shapes, understanding the synchronous nature of alpaca-py clients, and confirming the async wrapper pattern needed for FastAPI integration.

The most significant technical finding is that **all alpaca-py clients (`TradingClient`, `StockHistoricalDataClient`) are synchronous** — no `async def` methods exist. They must be called via `asyncio.get_event_loop().run_in_executor()` to avoid blocking the uvicorn event loop. A secondary finding is that `StockHistoricalDataClient` requires `pytz`, which was missing from the environment — this must be added to project dependencies.

The `AppSettings` table is seeded with `trading_mode="paper"`, `bot_enabled="false"`, and `stop_loss_pct="5.0"`, all as plain string values. Reading them requires a `SELECT WHERE key = ?` and explicit string-to-Python-type casting. The `Order.alpaca_order_id` DB column is `String(64)` and the Alpaca `Order.id` return type is `UUID` — must call `str(order.id)` before persisting.

**Primary recommendation:** Wrap all alpaca-py sync calls in `loop.run_in_executor(None, fn)`. Instantiate both `TradingClient` and `StockHistoricalDataClient` fresh per-request inside `execute()` using the mode read from DB — do not cache clients at class level.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Kill-switch enforcement | API / Backend | — | Must be server-side; cannot trust client to skip trades |
| Paper vs live mode selection | API / Backend | — | Mode read from DB per-request; client selection is pure backend concern |
| Bracket order submission | API / Backend | — | Alpaca API call; happens server-side |
| Last trade price fetch | API / Backend | — | Alpaca Data API call; server-side only |
| Order ID persistence | Database / Storage | — | Written to SQLite `orders` table via async SQLAlchemy session |
| Kill-switch state storage | Database / Storage | — | `bot_enabled` in `app_settings` table |
| HTTP entry point | API / Backend | — | `POST /trading/execute` and `POST /trading/kill-switch` are FastAPI routes |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| alpaca-py | 0.43.2 | TradingClient + StockHistoricalDataClient | Already installed; project mandates `alpaca-py` not `alpaca-trade-api` |
| fastapi | 0.136.0 | Router + endpoint definitions | Already installed; project stack |
| sqlalchemy | 2.0.49 | Async session writes to `orders` and `app_settings` | Already installed; project stack |
| pytz | 2026.1.post1 | Required transitive dependency of `alpaca.data.historical` | Must be in requirements; was missing from environment |

[VERIFIED: pip show / installed package inspection]

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic | (via fastapi) | Request/response model validation | Signal payload, kill-switch body, structured error responses |
| aiosqlite | 0.22.1 | SQLite async driver | Used via SQLAlchemy, no direct import needed |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `run_in_executor` for sync alpaca-py | `httpx` direct REST calls to Alpaca | alpaca-py is the project-mandated library; raw httpx would duplicate SDK logic |
| Per-request client instantiation | Module-level cached client | Cached client cannot respond to `trading_mode` DB changes; per-request is required per D-06 |

**Installation — add pytz to project dependencies:**
```bash
pip install pytz
```
Also add `pytz` to `pyproject.toml` or `requirements.txt` — it is a required transitive dependency of `alpaca.data.historical` that is not auto-installed.

---

## Architecture Patterns

### System Architecture Diagram

```
POST /trading/execute
  {"symbol": "AAPL", "side": "buy", "qty": 1}
         │
         ▼
  [route handler: trading_router]
         │
         ├─► read bot_enabled from app_settings ──► if false: return 503
         │
         ├─► read trading_mode from app_settings
         │
         ├─► instantiate TradingClient(paper=True|False)
         │   instantiate StockHistoricalDataClient()
         │
         ├─► run_in_executor: get_stock_latest_trade(symbol)
         │         └─► trade.price → last_price
         │
         ├─► compute stop_price = last_price * (1 - stop_loss_pct/100)
         │
         ├─► run_in_executor: trading_client.submit_order(
         │       MarketOrderRequest(
         │           symbol, qty, side,
         │           order_class=BRACKET,
         │           stop_loss=StopLossRequest(stop_price),
         │           time_in_force=DAY
         │       )
         │   )
         │         └─► alpaca_order.id (UUID)
         │
         ├─► async with AsyncSessionLocal() as session:
         │       session.add(Order(alpaca_order_id=str(alpaca_order.id), ...))
         │       await session.commit()
         │
         └─► return 200 {"order_id": str(alpaca_order.id), "status": "submitted"}


POST /trading/kill-switch
  {"enabled": bool}
         │
         ▼
  [route handler]
         │
         ├─► async with AsyncSessionLocal() as session:
         │       UPDATE app_settings SET value=? WHERE key='bot_enabled'
         │       await session.commit()
         │
         └─► return {"bot_enabled": bool, "ok": true}
```

### Recommended Project Structure
```
trumptrade/trading/
├── __init__.py          # existing stub
├── executor.py          # AlpacaExecutor service class
└── router.py            # FastAPI router: /execute and /kill-switch
```

### Pattern 1: Synchronous alpaca-py in Async FastAPI — run_in_executor

**What:** alpaca-py's `TradingClient.submit_order()` and `StockHistoricalDataClient.get_stock_latest_trade()` are synchronous blocking calls. Calling them directly in an async route handler blocks uvicorn's event loop.

**When to use:** Every alpaca-py call inside an `async def` route handler or service method.

```python
# Source: verified against alpaca-py 0.43.2 source — no async def methods found
import asyncio
from functools import partial

async def _run_sync(fn, *args, **kwargs):
    """Run a synchronous blocking call in a thread pool."""
    loop = asyncio.get_running_loop()
    if kwargs:
        fn = partial(fn, **kwargs)
    return await loop.run_in_executor(None, fn, *args)

# Usage:
alpaca_order = await _run_sync(trading_client.submit_order, order_request)
trade_map = await _run_sync(
    data_client.get_stock_latest_trade,
    StockLatestTradeRequest(symbol_or_symbols=symbol)
)
last_price: float = trade_map[symbol].price
```

[VERIFIED: alpaca-py 0.43.2 — zero `async def` methods in `TradingClient` or `StockHistoricalDataClient`]

### Pattern 2: TradingClient Instantiation — Paper vs Live

**What:** `TradingClient.__init__` takes `paper: bool = True`. Paper mode is the default. No URL override needed.

```python
# Source: verified against TradingClient.__init__ signature
from alpaca.trading.client import TradingClient
from trumptrade.core.config import get_settings

settings = get_settings()

# Paper mode (default):
client = TradingClient(
    api_key=settings.alpaca_api_key,
    secret_key=settings.alpaca_secret_key,
    paper=True,   # routes to paper-api.alpaca.markets
)

# Live mode:
client = TradingClient(
    api_key=settings.alpaca_api_key,
    secret_key=settings.alpaca_secret_key,
    paper=False,  # routes to api.alpaca.markets
)
```

[VERIFIED: `TradingClient.__init__(self, api_key, secret_key, oauth_token=None, paper=True, raw_data=False, url_override=None)`]

### Pattern 3: StockHistoricalDataClient — Last Trade Price

**What:** `StockHistoricalDataClient.get_stock_latest_trade()` returns `Dict[str, Trade]` where `Trade.price: float`.

```python
# Source: verified against alpaca-py 0.43.2 source
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestTradeRequest

data_client = StockHistoricalDataClient(
    api_key=settings.alpaca_api_key,
    secret_key=settings.alpaca_secret_key,
    # sandbox=False by default — paper trading uses real market data
)

trade_map = data_client.get_stock_latest_trade(
    StockLatestTradeRequest(symbol_or_symbols="AAPL")
)
last_price: float = trade_map["AAPL"].price
```

`StockLatestTradeRequest` fields: `symbol_or_symbols` (str or List[str]), `feed` (Optional), `currency` (Optional).
`Trade` fields verified: `symbol: str`, `timestamp: datetime`, `price: float`, `size: float`.

[VERIFIED: alpaca-py 0.43.2 source inspection]

### Pattern 4: Bracket Order Construction

**What:** `MarketOrderRequest` fields that apply for bracket order.

```python
# Source: verified against MarketOrderRequest.model_fields in alpaca-py 0.43.2
from alpaca.trading.requests import MarketOrderRequest, StopLossRequest
from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce

order_request = MarketOrderRequest(
    symbol="AAPL",
    qty=1,
    side=OrderSide.BUY,           # or OrderSide.SELL
    time_in_force=TimeInForce.DAY,
    order_class=OrderClass.BRACKET,
    stop_loss=StopLossRequest(stop_price=round(stop_price, 2)),
    # take_profit omitted — Phase 2 does not set profit target
)
```

`StopLossRequest` fields verified: `stop_price` (required), `limit_price` (optional). Only `stop_price` is needed.

`submit_order()` returns `alpaca.trading.models.Order` with `id: UUID`. Extract with `str(alpaca_order.id)` before storing in `orders.alpaca_order_id` (DB column is `String(64)`).

[VERIFIED: alpaca-py 0.43.2 source inspection]

### Pattern 5: AppSettings Read via Async SQLAlchemy

**What:** Read a single setting value from `app_settings` table inside a service method (not a route handler, so no `Depends(get_db)`).

```python
# Source: established project pattern per CONTEXT.md + db.py inspection
from sqlalchemy import select, update
from trumptrade.core.db import AsyncSessionLocal
from trumptrade.core.models import AppSettings

async def _get_setting(key: str) -> str:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AppSettings.value).where(AppSettings.key == key)
        )
        return result.scalar_one()  # raises NoResultFound if missing — acceptable

# Example reads:
trading_mode = await _get_setting("trading_mode")   # "paper" | "live"
bot_enabled = (await _get_setting("bot_enabled")) == "true"  # string "false" seeded
stop_loss_pct = float(await _get_setting("stop_loss_pct"))   # "5.0" seeded
```

[VERIFIED: models.py — AppSettings.value is `Text`, seeded values are plain strings]

### Pattern 6: AppSettings Write — Kill Switch

```python
# Source: established project pattern + db.py
async def _set_setting(key: str, value: str) -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(AppSettings)
            .where(AppSettings.key == key)
            .values(value=value)
        )
        await session.commit()

# Usage:
await _set_setting("bot_enabled", "true")   # or "false"
```

Note: `AsyncSessionLocal` uses `expire_on_commit=False` — safe to read attributes after commit.

[VERIFIED: db.py line 29 — `expire_on_commit=False` explicitly set]

### Pattern 7: Order DB Write from Service Layer

```python
# Source: established project pattern per CONTEXT.md
from trumptrade.core.db import AsyncSessionLocal
from trumptrade.core.models import Order

async def _log_order(alpaca_order_id: str, symbol: str, side: str,
                      qty: float, trading_mode: str) -> None:
    async with AsyncSessionLocal() as session:
        order = Order(
            alpaca_order_id=alpaca_order_id,  # str(uuid)
            symbol=symbol,
            side=side,
            qty=qty,
            order_type="bracket",
            status="submitted",
            trading_mode=trading_mode,
            # signal_id=None (nullable — test/stub orders have no signal)
        )
        session.add(order)
        await session.commit()
```

[VERIFIED: models.py Order fields; signal_id is `nullable=True`]

### Pattern 8: FastAPI Router Registration

```python
# trumptrade/trading/router.py
from fastapi import APIRouter
router = APIRouter()

# trumptrade/core/app.py create_app() — add:
from trumptrade.trading.router import router as trading_router
app.include_router(trading_router, prefix="/trading", tags=["trading"])
```

[VERIFIED: app.py create_app() pattern — no routers registered yet; this is the first]

### Anti-Patterns to Avoid

- **Calling alpaca-py sync methods directly in async handlers:** Blocks uvicorn event loop. Always use `run_in_executor`.
- **Caching TradingClient at module or class level:** Violates D-06 — mode is re-read per request. Instantiate fresh inside `execute()`.
- **Submitting stop-loss as a separate order after the entry:** Violates TRADE-03 and project rule #4. Use `order_class=OrderClass.BRACKET` with `stop_loss=StopLossRequest(...)` in the same `submit_order()` call.
- **Reading `trading_mode` from `config.py`/environment:** Per CONTEXT.md, `trading_mode` lives in `app_settings` DB table, not in `.env`. `config.py` only holds secrets.
- **Trusting `bot_enabled` from app state:** Always re-read from DB per request.
- **Placing kill-switch check after price fetch or order setup:** Kill-switch must be the FIRST check in `execute()` before any network calls.
- **Storing Alpaca UUID directly without `str()` conversion:** `Order.id` is `UUID` type; DB column is `String(64)`. Must call `str(alpaca_order.id)`.
- **Using `stop_price` with more than 2 decimal places without rounding:** Alpaca paper API may reject prices with excessive precision. Use `round(stop_price, 2)`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Bracket order atomicity | Separate stop-loss submission logic | `MarketOrderRequest(order_class=OrderClass.BRACKET, stop_loss=StopLossRequest(...))` | Alpaca enforces atomicity server-side; two-step submission can leave unprotected positions |
| Thread pool for sync calls | Custom ThreadPoolExecutor management | `asyncio.get_running_loop().run_in_executor(None, fn)` | Default executor is pre-sized and managed by asyncio event loop |
| HTTP status code mapping for Alpaca errors | Custom error code table | `APIError.status_code` property from `alpaca.common.exceptions` | SDK already exposes `status_code` from the underlying `requests.HTTPError` |
| Settings cache | Custom TTL or invalidation logic | Re-read from DB per request via `AsyncSessionLocal` | DB reads on SQLite are fast enough; caching would break D-06 live mode switching |

**Key insight:** The alpaca-py SDK handles all bracket order semantics server-side. The client only needs to assemble the right request object — no custom state machine for stop-loss attachment.

---

## Common Pitfalls

### Pitfall 1: alpaca-py is Synchronous
**What goes wrong:** Developer calls `trading_client.submit_order(...)` directly inside an `async def` route handler. This blocks the uvicorn event loop for the duration of the HTTP call (~100-500ms), starving other requests and WebSocket connections.
**Why it happens:** `TradingClient` inherits from `RESTClient` which uses `requests` (blocking HTTP). No `async` version exists in alpaca-py 0.43.2.
**How to avoid:** Always wrap with `await loop.run_in_executor(None, fn, *args)`.
**Warning signs:** Requests queuing up; dashboard unresponsive during order placement.

[VERIFIED: zero `async def` in TradingClient source]

### Pitfall 2: pytz Missing for Data Client
**What goes wrong:** `from alpaca.data.historical import StockHistoricalDataClient` raises `ModuleNotFoundError: No module named 'pytz'` at import time — even though alpaca-py is installed.
**Why it happens:** `pytz` is a dependency of `alpaca.data` but is not listed in alpaca-py's own package metadata in a way that auto-installs it in all environments.
**How to avoid:** Add `pytz` explicitly to `requirements.txt` / `pyproject.toml`. Already resolved in this environment (2026.1.post1 installed).
**Warning signs:** Import error at startup when `trading/executor.py` is first imported.

[VERIFIED: tested in environment — `alpaca.data.historical` failed without pytz, succeeded after install]

### Pitfall 3: UUID to String for DB Insert
**What goes wrong:** `Order(alpaca_order_id=alpaca_order.id, ...)` fails or stores garbage because `alpaca_order.id` is a `UUID` object and the DB column is `String(64)`.
**Why it happens:** alpaca-py `Order.id` is typed as `UUID` (from `uuid.UUID`), not `str`.
**How to avoid:** Always use `str(alpaca_order.id)` before storing.
**Warning signs:** SQLAlchemy type coercion warning or `alpaca_order_id` stored as UUID repr with dashes in wrong format.

[VERIFIED: alpaca trading models.py — `class ModelWithID` with `id: UUID`; orders table `alpaca_order_id String(64)`]

### Pitfall 4: bot_enabled Seeded as String "false"
**What goes wrong:** Code reads `bot_enabled` value from DB and checks `if bot_enabled_value:` — `"false"` is a truthy string in Python, so the check passes even when bot is disabled.
**Why it happens:** `AppSettings.value` is `Text` — all values are strings. Seeded value is `"false"` (not Python `False`).
**How to avoid:** Compare explicitly: `bot_enabled = (raw_value == "true")`.
**Warning signs:** Kill switch appears to have no effect; trades fire even after `POST /trading/kill-switch {"enabled": false}`.

[VERIFIED: alembic migration seeds `bot_enabled = 'false'` as string]

### Pitfall 5: stop_price Precision
**What goes wrong:** Alpaca paper API returns 422 or silently adjusts `stop_price` if it has too many decimal places (e.g., `stop_price = 189.23456789`).
**Why it happens:** Alpaca enforces tick size constraints even in paper mode for price fields.
**How to avoid:** Always `round(stop_price, 2)` before passing to `StopLossRequest`.
**Warning signs:** 422 API error with message about price precision; or stop fires at unexpected price.

[ASSUMED — standard Alpaca paper mode behavior; not confirmed against live paper API in this session]

### Pitfall 6: TimeInForce for Bracket Orders
**What goes wrong:** Bracket orders with `TimeInForce.GTC` may not be accepted in paper mode for certain order classes; paper mode has quirks around GTC bracket behavior.
**Why it happens:** Alpaca paper environment mimics live but has simplified order lifecycle simulation.
**How to avoid:** Use `TimeInForce.DAY` for all Phase 2 bracket orders. Phase 5 can revisit if GTC is needed.
**Warning signs:** Order submitted but immediately transitions to `rejected` or `expired` status.

[ASSUMED — common Alpaca paper mode quirk; not confirmed against live API in this session]

---

## Code Examples

### Complete execute() Flow (Skeleton)

```python
# Source: all patterns verified above; skeleton shows composition
import asyncio
from functools import partial
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, StopLossRequest
from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestTradeRequest
from alpaca.common.exceptions import APIError
from sqlalchemy import select, update
from trumptrade.core.db import AsyncSessionLocal
from trumptrade.core.models import AppSettings, Order
from trumptrade.core.config import get_settings


class AlpacaExecutor:

    async def execute(self, symbol: str, side: str, qty: float) -> dict:
        settings = get_settings()

        # 1. Kill-switch check FIRST
        bot_enabled_raw = await self._get_setting("bot_enabled")
        if bot_enabled_raw != "true":
            raise BotDisabledError()

        # 2. Read runtime settings
        trading_mode = await self._get_setting("trading_mode")
        stop_loss_pct = float(await self._get_setting("stop_loss_pct"))
        is_paper = (trading_mode == "paper")

        # 3. Instantiate clients (per-request, not cached)
        trading_client = TradingClient(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_secret_key,
            paper=is_paper,
        )
        data_client = StockHistoricalDataClient(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_secret_key,
        )

        # 4. Fetch last trade price (sync → thread pool)
        loop = asyncio.get_running_loop()
        trade_map = await loop.run_in_executor(
            None,
            partial(data_client.get_stock_latest_trade,
                    StockLatestTradeRequest(symbol_or_symbols=symbol))
        )
        last_price: float = trade_map[symbol].price

        # 5. Calculate stop price
        stop_price = round(last_price * (1 - stop_loss_pct / 100), 2)

        # 6. Build and submit bracket order (sync → thread pool)
        order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
        order_request = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=order_side,
            time_in_force=TimeInForce.DAY,
            order_class=OrderClass.BRACKET,
            stop_loss=StopLossRequest(stop_price=stop_price),
        )
        alpaca_order = await loop.run_in_executor(
            None, trading_client.submit_order, order_request
        )
        alpaca_order_id = str(alpaca_order.id)  # UUID → str

        # 7. Log to DB
        await self._log_order(alpaca_order_id, symbol, side, qty, trading_mode)

        return {"order_id": alpaca_order_id, "status": "submitted"}

    async def _get_setting(self, key: str) -> str:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(AppSettings.value).where(AppSettings.key == key)
            )
            return result.scalar_one()

    async def _log_order(self, alpaca_order_id: str, symbol: str,
                          side: str, qty: float, trading_mode: str) -> None:
        async with AsyncSessionLocal() as session:
            session.add(Order(
                alpaca_order_id=alpaca_order_id,
                symbol=symbol,
                side=side,
                qty=qty,
                order_type="bracket",
                status="submitted",
                trading_mode=trading_mode,
            ))
            await session.commit()
```

### Kill-Switch Route Handler

```python
# Source: FastAPI patterns + established project conventions
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import update
from trumptrade.core.db import AsyncSessionLocal
from trumptrade.core.models import AppSettings

router = APIRouter()

class KillSwitchRequest(BaseModel):
    enabled: bool

@router.post("/kill-switch")
async def kill_switch(body: KillSwitchRequest):
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(AppSettings)
            .where(AppSettings.key == "bot_enabled")
            .values(value="true" if body.enabled else "false")
        )
        await session.commit()
    return {"bot_enabled": body.enabled, "ok": True}
```

### Execute Route Handler

```python
# Source: FastAPI patterns + established project conventions
from fastapi import APIRouter
from pydantic import BaseModel
from trumptrade.trading.executor import AlpacaExecutor

router = APIRouter()
_executor = AlpacaExecutor()

class ExecuteSignalRequest(BaseModel):
    symbol: str
    side: str   # "buy" | "sell"
    qty: float

@router.post("/execute")
async def execute_signal(body: ExecuteSignalRequest):
    # BotDisabledError mapped to 503 in exception handler
    result = await _executor.execute(body.symbol, body.side, body.qty)
    return result
```

### Error Handling — Alpaca APIError

```python
# Source: verified against alpaca.common.exceptions.APIError
from alpaca.common.exceptions import APIError

try:
    alpaca_order = await loop.run_in_executor(None, trading_client.submit_order, req)
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

`APIError` properties verified: `.status_code` (from `requests.HTTPError.response`), `.message` (from JSON response body), `.code` (Alpaca internal error code).

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `alpaca-trade-api` Python SDK | `alpaca-py` | 2022 | `alpaca-trade-api` is deprecated; `alpaca-py` is the official SDK |
| `@app.on_event("startup")` | `lifespan` context manager | FastAPI 0.93+ | `on_event` deprecated; project already uses `lifespan` in app.py |

**Deprecated/outdated:**
- `alpaca-trade-api`: Forbidden by CLAUDE.md rule #1. `alpaca-py` is the replacement.
- `requests` for HTTP calls: Forbidden by CLAUDE.md rule #2 (alpaca-py itself uses requests internally, but application code must not add `requests` calls).

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `stop_price` should be rounded to 2 decimal places to avoid Alpaca 422 errors on price precision | Common Pitfalls #5 | If wrong: stop_price with more decimals may still work in paper mode (low severity) |
| A2 | `TimeInForce.DAY` is the safest choice for bracket orders in paper mode (GTC may cause issues) | Common Pitfalls #6 | If wrong: GTC bracket orders would work fine in paper mode too (low severity) |

---

## Open Questions

1. **Alpaca paper environment credential separation**
   - What we know: `TradingClient(paper=True)` routes to `paper-api.alpaca.markets`; uses the same API keys as live.
   - What's unclear: Whether there is a separate paper key pair vs. a toggle on the same key — Alpaca may have changed this.
   - Recommendation: Test with existing keys; if auth fails, user needs to generate paper-specific credentials in Alpaca dashboard. [ASSUMED]

2. **`StockHistoricalDataClient` — no sandbox flag needed for paper trading**
   - What we know: Constructor has `sandbox=False` default; `TradingClient` has `paper=True`.
   - What's unclear: Whether the data client should use `sandbox=True` when using paper trading credentials.
   - Recommendation: Use `sandbox=False` (default) — market data is real regardless of trading mode; only the order routing changes. [ASSUMED]

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| alpaca-py | TradingClient, StockHistoricalDataClient | ✓ | 0.43.2 | — |
| pytz | alpaca.data.historical | ✓ | 2026.1.post1 | — (was missing, now installed) |
| fastapi | Router + endpoints | ✓ | 0.136.0 | — |
| sqlalchemy | Async DB writes | ✓ | 2.0.49 | — |
| aiosqlite | SQLite async driver | ✓ | 0.22.1 | — |

**Missing dependencies with no fallback:** None — all dependencies now installed.

**Missing dependencies with fallback:** None.

**Action required:** Add `pytz` to `pyproject.toml` or `requirements.txt` — it was absent and caused a runtime import failure until manually installed.

---

## Security Domain

`security_enforcement` not set in config.json (treated as enabled).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | No user auth in Phase 2; single-user tool |
| V3 Session Management | No | No sessions in Phase 2 |
| V4 Access Control | No | No multi-user access control |
| V5 Input Validation | Yes | Pydantic models on request bodies (symbol, side, qty) |
| V6 Cryptography | No | No crypto operations in Phase 2 |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Unvalidated ticker symbol injected as Alpaca API parameter | Tampering | Pydantic validates `symbol` field type; Alpaca returns 422 on invalid tickers — catch `APIError` with status 422 |
| Negative or zero `qty` in execute payload | Tampering | Pydantic `Field(gt=0)` constraint on qty |
| Kill-switch race (concurrent requests toggle state) | Tampering | SQLite serializes writes; each request re-reads from DB — no shared in-memory state |
| Alpaca credentials exposed in logs | Information Disclosure | Never log `settings.alpaca_api_key` or `settings.alpaca_secret_key`; log order IDs only |

---

## Sources

### Primary (HIGH confidence)
- Installed alpaca-py 0.43.2 package source — `TradingClient.__init__` signature, `submit_order` signature, `MarketOrderRequest.model_fields`, `StopLossRequest.model_fields`, `OrderClass`/`OrderSide`/`TimeInForce` enum values, `Order` model fields, `APIError` exception structure, `StockHistoricalDataClient.__init__` signature, `get_stock_latest_trade` signature, `Trade.price` field
- `trumptrade/core/models.py` — `Order` field names, `AppSettings` key-value structure
- `trumptrade/core/db.py` — `AsyncSessionLocal`, `expire_on_commit=False` pattern
- `trumptrade/core/config.py` — `get_settings()`, `alpaca_api_key`, `alpaca_secret_key`
- `trumptrade/core/app.py` — `create_app()` router registration point
- `alembic/versions/6e3709bc5279_initial_schema.py` — `app_settings` seeded values (`trading_mode="paper"`, `bot_enabled="false"`, `stop_loss_pct="5.0"`)
- `pip show` / runtime import tests — confirmed all dependency versions

### Secondary (MEDIUM confidence)
- [ASSUMED] Alpaca paper mode `TimeInForce.DAY` safer than `GTC` for bracket orders
- [ASSUMED] `stop_price` rounded to 2 decimal places avoids Alpaca precision errors

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified against installed packages
- Architecture: HIGH — verified against package source + existing code patterns
- Pitfalls: HIGH for items 1-4 (verified), MEDIUM for items 5-6 (assumed)

**Research date:** 2026-04-19
**Valid until:** 2026-05-19 (alpaca-py API is stable; FastAPI/SQLAlchemy patterns are stable)
