---
phase: 02-alpaca-executor
verified: 2026-04-20T00:00:00Z
status: human_needed
score: 7/9 must-haves verified
overrides_applied: 0
human_verification:
  - test: "POST /trading/execute with valid Alpaca paper credentials places a real bracket order"
    expected: "Response 200 with {order_id: '<uuid>', status: 'submitted'} and order appears in Alpaca paper dashboard"
    why_human: "Requires running server with real Alpaca API credentials — cannot verify programmatically without network and secrets"
  - test: "Kill-switch end-to-end: enable bot, execute, disable, execute again — confirm 503 on second attempt"
    expected: "First /execute returns 200 or 502 (auth-dependent); second /execute after kill-switch returns 503 with {detail: {error: 'bot_disabled'}}"
    why_human: "Requires running server and confirmed DB state transitions — end-to-end flow can't be verified without live app"
---

# Phase 2: Alpaca Executor Verification Report

**Phase Goal:** The system can place, fill, and confirm paper trades with atomic bracket stop-loss orders using stub signals
**Verified:** 2026-04-20T00:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Injecting a stub BUY signal causes the executor to place a bracket order on Alpaca paper and log a confirmed order ID | ? HUMAN | Code fully implemented and wired; all 7 unit tests pass; requires live Alpaca credentials to confirm end-to-end |
| 2 | The placed bracket order contains an attached stop-loss at the correct calculated percentage — never submitted as a separate order | ✓ VERIFIED | `OrderClass.BRACKET` + `StopLossRequest(stop_price=stop_price)` in executor.py line 80-81; stop price math verified by test_stop_price_calculation_basic and test_stop_price_precision |
| 3 | The system runs in paper mode by default | ✓ VERIFIED | DB migration seeds `trading_mode='paper'` (6e3709bc5279_initial_schema.py line 122); executor reads this per-request from DB |
| 4 | Switching to live mode requires an explicit change | ✓ VERIFIED (with note) | Implementation uses DB-stored `trading_mode` key rather than `TRADING_MODE=live` env var; design decision D-09 documented in config.py; manual DB update required (no endpoint in this phase) |
| 5 | A kill-switch endpoint halts trade execution immediately when called | ✓ VERIFIED | `/trading/kill-switch` endpoint exists; `set_bot_enabled()` updates DB; executor checks `bot_enabled != "true"` before every order; test_bot_disabled_raises_before_network confirms BotDisabledError fires before any network call |
| 6 | POST /trading/execute when bot is disabled returns 503 with {error: bot_disabled} | ✓ VERIFIED | router.py line 46-47: `except BotDisabledError: raise HTTPException(status_code=503, detail={"error": "bot_disabled"})` |
| 7 | Negative or zero qty is rejected at the Pydantic layer before reaching the executor | ✓ VERIFIED | `qty: float = Field(gt=0)` in ExecuteSignalRequest (router.py line 19) |
| 8 | A confirmed order is logged to the orders table with status=submitted | ✓ VERIFIED | `_log_order()` writes `Order(status="submitted", order_type="bracket", ...)` after order submission (executor.py lines 127-142) |
| 9 | POST /trading/execute with a valid signal body — end-to-end with Alpaca paper | ? HUMAN | Cannot verify without live Alpaca paper credentials |

**Score:** 7/9 truths verified (2 require human verification)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `trumptrade/trading/executor.py` | AlpacaExecutor service class with execute() and set_bot_enabled() | ✓ VERIFIED | 143 lines, all required methods implemented; `from __future__ import annotations` line 1; exports AlpacaExecutor and BotDisabledError; imports cleanly |
| `pyproject.toml` | pytz>=2024.1 dependency | ✓ VERIFIED | Line 22: `"pytz>=2024.1",` present |
| `trumptrade/trading/router.py` | FastAPI router with /execute and /kill-switch endpoints | ✓ VERIFIED | 59 lines; both endpoints implemented; Pydantic models with Field(gt=0); BotDisabledError mapped to 503 |
| `trumptrade/trading/__init__.py` | trading_router export | ✓ VERIFIED | Exports `trading_router` from router.py; `__all__ = ["trading_router"]` |
| `trumptrade/core/app.py` | router registered under /trading prefix | ✓ VERIFIED | Local import inside `create_app()` body (line 71-72); `include_router(trading_router, prefix="/trading", tags=["trading"])` |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `AlpacaExecutor.execute()` | `app_settings.bot_enabled` | `_get_setting('bot_enabled') != "true"` | ✓ WIRED | executor.py line 32-33: string comparison confirmed |
| `AlpacaExecutor.execute()` | `alpaca TradingClient.submit_order` | `loop.run_in_executor(None, trading_client.submit_order, order_request)` | ✓ WIRED | executor.py lines 86-88; sync call wrapped in run_in_executor as required |
| `MarketOrderRequest` | `StopLossRequest` | `order_class=OrderClass.BRACKET, stop_loss=StopLossRequest(stop_price=...)` | ✓ WIRED | executor.py lines 75-82; atomic bracket construction confirmed |
| `alpaca_order.id` | `orders.alpaca_order_id` | `str(alpaca_order.id)` | ✓ WIRED | executor.py line 100: UUID → str conversion before DB write |
| `trumptrade/trading/__init__.py` | `trumptrade/trading/router.py` | `from trumptrade.trading.router import router as trading_router` | ✓ WIRED | __init__.py line 4 |
| `trumptrade/core/app.py create_app()` | `trumptrade/trading/__init__.py` | local import inside create_app() | ✓ WIRED | app.py line 71: local import pattern avoids circular dependency |
| `router.py /execute handler` | `AlpacaExecutor.execute()` | `await _executor.execute(body.symbol, body.side, body.qty)` | ✓ WIRED | router.py line 44 |
| `BotDisabledError` | HTTP 503 | `except BotDisabledError: raise HTTPException(status_code=503` | ✓ WIRED | router.py lines 46-47 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `executor.py execute()` | `bot_enabled_raw` | `_get_setting("bot_enabled")` → `AsyncSessionLocal` → `AppSettings` table | Yes — DB query via SQLAlchemy select | ✓ FLOWING |
| `executor.py execute()` | `trading_mode`, `stop_loss_pct` | `_get_setting()` → DB on every call (no caching) | Yes — per-request DB reads | ✓ FLOWING |
| `executor.py execute()` | `last_price` | `StockHistoricalDataClient.get_stock_latest_trade()` via run_in_executor | Yes — live Alpaca data API | ✓ FLOWING (requires live credentials) |
| `executor._log_order()` | `Order` record | `session.add(Order(...))` → SQLite `orders` table | Yes — real DB write | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| executor imports cleanly | `python -c "from trumptrade.trading.executor import AlpacaExecutor, BotDisabledError; print('ok')"` | `executor import ok` | ✓ PASS |
| router imports cleanly | `python -c "from trumptrade.trading import trading_router; print('ok')"` | `router import ok` | ✓ PASS |
| FastAPI routes registered | `python -c "from trumptrade.core.app import create_app; app = create_app(); routes = [r.path for r in app.routes]; assert '/trading/execute' in routes and '/trading/kill-switch' in routes and '/health' in routes"` | Routes: `['/openapi.json', '/docs', '/docs/oauth2-redirect', '/redoc', '/trading/execute', '/trading/kill-switch', '/health']` | ✓ PASS |
| All 7 unit tests pass | `python -m pytest tests/trading/ -v` | `7 passed, 1 warning` | ✓ PASS |
| bot_disabled raises before network | test_bot_disabled_raises_before_network | TradingClient and StockHistoricalDataClient never called when bot disabled | ✓ PASS |
| stop price math correct | test_stop_price_calculation_basic, test_stop_price_precision | 100.0 → 95.0; 189.2345 → 179.77 | ✓ PASS |
| BotDisabledError is plain Exception | test_bot_disabled_error_is_plain_exception | `issubclass(BotDisabledError, Exception)` and not HTTPException | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| TRADE-01 | 02-01-PLAN, 02-02-PLAN | User can run the bot in paper trading mode (Alpaca paper environment — simulated money, real prices) as the default mode | ✓ SATISFIED | DB seed sets `trading_mode='paper'`; executor reads this per-request; TradingClient instantiated with `paper=is_paper` |
| TRADE-03 | 02-01-PLAN, 02-02-PLAN | System places all entry orders as Alpaca bracket orders (atomic entry + stop-loss) — never two separate submissions | ✓ SATISFIED | `order_class=OrderClass.BRACKET, stop_loss=StopLossRequest(stop_price=...)` in MarketOrderRequest; design decision documented in executor.py comment |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | No anti-patterns detected | — | — |

Scanned for: TODO/FIXME/PLACEHOLDER comments, empty return values, hardcoded empty data, props with empty values, console.log-only implementations. None found in executor.py, router.py, __init__.py, or app.py.

### Human Verification Required

#### 1. End-to-End Bracket Order Placement

**Test:** Start the server (`python -m trumptrade`), enable the bot via `POST /trading/kill-switch {"enabled": true}`, then call `POST /trading/execute {"symbol": "AAPL", "side": "buy", "qty": 1}` with valid Alpaca paper credentials in `.env`.

**Expected:** Response `{"order_id": "<uuid>", "status": "submitted"}` and order visible in Alpaca paper dashboard. If credentials are missing, response should be 502 (Alpaca auth failed), NOT a Python crash or 500.

**Why human:** Requires real Alpaca paper API credentials and live network call. Cannot be verified programmatically without secrets.

#### 2. Kill-Switch End-to-End Toggle

**Test:** Start server, call `POST /trading/kill-switch {"enabled": false}` then immediately call `POST /trading/execute {"symbol": "AAPL", "side": "buy", "qty": 1}`.

**Expected:** Kill-switch returns `{"bot_enabled": false, "ok": true}`. Execute returns HTTP 503 with body `{"detail": {"error": "bot_disabled"}}`.

**Why human:** Requires running server with live DB state transitions. The unit test covers the executor logic but not the full HTTP round-trip with a real SQLite DB session.

### Gaps Summary

No blocking gaps identified. All code is fully implemented, substantive, wired, and data flows through real DB queries. The two human verification items cover end-to-end behaviors that require a running server with live Alpaca credentials.

**Design note on SC3 (live mode switching):** The roadmap success criterion mentions `TRADING_MODE=live` as the switching mechanism, but the Phase 1 architecture decision D-09 explicitly placed `trading_mode` in the DB (app_settings table) rather than in environment config. The config.py comment confirms this: "trading_mode... lives in the app_settings DB table, NOT here." This is an intentional, documented design choice — paper is the default via DB seed, and live requires a manual DB update (a future settings endpoint is planned in Phase 5). This is NOT a gap.

---

_Verified: 2026-04-20T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
