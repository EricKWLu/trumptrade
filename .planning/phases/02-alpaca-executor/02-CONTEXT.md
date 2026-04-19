# Phase 2: Alpaca Executor - Context

**Gathered:** 2026-04-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the Alpaca executor: given a signal (ticker + side), place an atomic bracket order on the Alpaca paper environment, log the confirmed Alpaca order ID, and expose a kill-switch endpoint. No LLM, no ingestion, no risk guard — stub signals only. Phase 5 wires the real pipeline.

</domain>

<decisions>
## Implementation Decisions

### Stub Signal Interface
- **D-01:** Executor exposes `POST /trading/execute` accepting a signal payload (ticker, side, qty). This is the real executor entry point — Phase 5 (risk guard) will call this same endpoint from the asyncio.Queue consumer. Paper mode is active by default; stub signals go directly to Alpaca paper environment.

### Entry Order Type
- **D-02:** Use **market orders** for the entry leg. Fetch the current last trade price from the Alpaca data API before submitting, then calculate:
  ```
  stop_price = last_price * (1 - stop_loss_pct / 100)
  ```
  `stop_loss_pct` is read from `app_settings` DB table (seeded at 5.0). Market orders fill immediately in paper mode, making demo and verification straightforward.

### Bracket Order Construction
- **D-03:** Bracket orders use `alpaca-py` `MarketOrderRequest` with `order_class=OrderClass.BRACKET`. The `stop_loss` leg is a `StopLossRequest(stop_price=calculated_price)`. No `take_profit` leg in Phase 2 (can be added in Phase 5). Stop-loss is ALWAYS part of the bracket submission — never a separate order (TRADE-03).

### Fill Confirmation
- **D-04:** Log the Alpaca **order ID returned on submission** to the `orders` table. "Confirmed" in SC1 means Alpaca accepted and assigned an order ID — not waiting for fill status. No polling in Phase 2. `orders.status` is set to `"submitted"` at creation; `fills` table is populated in Phase 5 when the pipeline is complete.

### Kill Switch
- **D-05:** `POST /trading/kill-switch` with body `{"enabled": bool}`. Updates `bot_enabled` in `app_settings`. Returns `{"bot_enabled": bool, "ok": true}`. The executor checks `bot_enabled` before every order placement — if false, returns 503 with `{"error": "bot_disabled"}`. Phase 6 dashboard toggle calls this endpoint.

### Trading Mode Selection
- **D-06:** `trading_mode` is read from `app_settings` at executor startup (not cached — re-read per request so DB changes take effect immediately). `"paper"` → Alpaca paper endpoint (`paper-api.alpaca.markets`). `"live"` → live endpoint. Alpaca client is instantiated inside the executor service based on this value. Switching to live requires updating `app_settings` — the architecture supports it, Phase 2 only tests paper.

### Claude's Discretion
- Executor service architecture: `AlpacaExecutor` service class with `async def execute(signal)` method, called by the route handler. This keeps the HTTP layer thin and makes Phase 5 wiring cleaner.
- Pydantic request/response models for `POST /trading/execute` and `POST /trading/kill-switch`.
- Error handling: invalid ticker, Alpaca API error, and missing credentials each return appropriate 4xx/5xx with structured JSON.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Requirements
- `.planning/REQUIREMENTS.md` — TRADE-01 (paper mode default), TRADE-03 (bracket orders only, never separate)
- `.planning/ROADMAP.md` §Phase 2 — success criteria SC1–SC4

### Existing Phase 1 Code (read before implementing)
- `trumptrade/core/models.py` — `Order` model (fields: alpaca_order_id, symbol, side, qty, order_type, status, trading_mode, fill_price), `AppSettings` key-value model
- `trumptrade/core/db.py` — `AsyncSessionLocal` for service-layer sessions, `get_db` FastAPI dependency
- `trumptrade/core/config.py` — `get_settings()` for Alpaca API key/secret
- `trumptrade/core/app.py` — `create_app()` where new routers are registered

### Stack Docs
- alpaca-py: use `from alpaca.trading.client import TradingClient`, `from alpaca.trading.requests import MarketOrderRequest`, `from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce`
- alpaca-py bracket orders: `MarketOrderRequest(..., order_class=OrderClass.BRACKET, stop_loss=StopLossRequest(stop_price=X))`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `trumptrade/core/db.py` — `AsyncSessionLocal` context manager for DB writes inside the executor service (not a FastAPI route dependency)
- `trumptrade/core/config.py` — `get_settings()` provides `alpaca_api_key` and `alpaca_secret_key`
- `trumptrade/core/models.py` — `Order` and `AppSettings` models ready to use (no schema changes needed for Phase 2)

### Established Patterns
- Route handlers use `Depends(get_db)` for DB sessions; background service methods use `async with AsyncSessionLocal() as session`
- New domain routes go in `trumptrade/trading/` and are registered via `app.include_router()` in `create_app()`
- Settings reads: `SELECT value FROM app_settings WHERE key = 'trading_mode'` (then cast to Python type)
- No `relationship()` calls — all joins done manually in queries

### Integration Points
- `trumptrade/trading/__init__.py` — currently empty stub; Phase 2 adds `executor.py` and `router.py` here
- `trumptrade/core/app.py` `create_app()` — add `app.include_router(trading_router, prefix="/trading")`
- `AppSettings` table — read `trading_mode`, `stop_loss_pct`, `bot_enabled` at runtime

</code_context>

<specifics>
## Specific Ideas

- The executor endpoint `POST /trading/execute` should work with a simple JSON body: `{"symbol": "AAPL", "side": "buy", "qty": 1}`. This makes it curl-testable for SC1 verification.
- Kill switch check should be the FIRST thing the executor does before fetching price data or calling Alpaca.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 02-alpaca-executor*
*Context gathered: 2026-04-19*
