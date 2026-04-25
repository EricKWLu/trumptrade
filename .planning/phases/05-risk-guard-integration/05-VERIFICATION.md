---
phase: 05-risk-guard-integration
verified: 2026-04-21T00:00:00Z
status: human_needed
score: 4/5
overrides_applied: 0
human_verification:
  - test: "Start server, exercise GET /settings/risk and PATCH /settings/risk, trigger a real end-to-end signal, and verify clean shutdown"
    expected: "Server logs 'Risk consumer task started'; GET /settings/risk returns all 4 keys with correct defaults; PATCH updates and persists value; end-to-end post → signal → risk_consumer → Order row with signal_id populated; server shuts down without 'Task destroyed but it is pending!' warning"
    why_human: "End-to-end pipeline requires live Alpaca paper credentials, live clock/equity calls, and actual post ingestion — cannot verify programmatically without running services. Roadmap SC-4 (post → signal → risk guard → paper trade with full audit chain) and SC-5 (settings endpoint live update and effect on next signal) both require a running server with external API access."
---

# Phase 5: Risk Guard + Integration Verification Report

**Phase Goal:** Signals flow through a single risk chokepoint before reaching the executor, with capital protected by position sizing, daily loss cap, and market hours enforcement
**Verified:** 2026-04-21
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A signal arriving outside market hours or older than the configured staleness threshold is discarded with reason code `STALE` or `MARKET_CLOSED` — no order is placed | VERIFIED | `_check_staleness()` in guard.py (lines 92–104) compares naive UTC datetimes and writes `STALE`; `_process_signal()` (lines 295–309) calls `get_clock().is_open` and writes `MARKET_CLOSED`; reason codes stored via `_update_signal_reason()` |
| 2 | Position size per trade respects the configured risk level as a percentage of live Alpaca portfolio value | VERIFIED | `_compute_qty()` (lines 147–176) implements `equity * (max_position_size_pct / 100) * confidence / share_price` with `math.floor()`; equity fetched live from Alpaca per cycle; `max_position_size_pct` read from `app_settings` per cycle |
| 3 | When cumulative daily losses reach the configured max daily loss cap (read from live Alpaca account), all subsequent signals are blocked | VERIFIED | `_check_daily_cap()` (lines 107–131) reads `last_equity` and `equity` as `Optional[str]` from Alpaca, converts to float, computes `daily_loss = last_equity - equity`, blocks and writes `DAILY_CAP_HIT` when `daily_loss >= max_daily_loss_dollars` |
| 4 | End-to-end: a real Trump post flows through ingestion → analysis → risk guard → paper trade execution with full audit chain | HUMAN_NEEDED | Code wiring is verified (see key links below): worker enqueues, consumer processes, executor called with `signal_id`; Order rows store `signal_id`. Actual end-to-end flow requires live services and Alpaca credentials |
| 5 | User can update position size %, stop-loss %, and daily loss cap from a settings endpoint and changes take effect on the next signal | HUMAN_NEEDED | `GET /risk` and `PATCH /risk` routes exist in router.py (lines 73–109) with correct Pydantic models and DB writes; `_consumer_task` reads settings per cycle from DB. Live confirmation requires running server |

**Score:** 3/5 truths fully verified programmatically (SC-1, SC-2, SC-3 — the core risk logic); 2 require human confirmation (SC-4 end-to-end, SC-5 live settings effect). Note: 05-03-SUMMARY.md records human checkpoint approval on 2026-04-21, which covers SC-4 and SC-5.

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `trumptrade/risk_guard/__init__.py` | signal_queue, QueueItem, settings_router exports | VERIFIED | Direct imports of QueueItem from guard.py and settings_router from router.py; `signal_queue = asyncio.Queue(maxsize=100)`; no stub/None guard |
| `trumptrade/risk_guard/guard.py` | QueueItem dataclass, risk_consumer coroutine, all risk check helpers | VERIFIED | All helpers present: `_get_setting`, `_make_clients`, `_check_staleness`, `_check_daily_cap`, `_get_equity`, `_compute_qty`, `_execute_for_tickers`, `_drain_hold_list_if_open`, `_process_signal`, `risk_consumer`; 362 lines, substantive |
| `trumptrade/risk_guard/router.py` | GET /risk and PATCH /risk FastAPI routes | VERIFIED | `RiskSettingsResponse`, `RiskSettingsPatch`, `get_risk_settings()`, `patch_risk_settings()` all present; `model_dump(exclude_none=True)` PATCH semantics confirmed |
| `alembic/versions/005_risk_settings.py` | 3 new app_settings keys seeded with INSERT OR IGNORE | VERIFIED | 3 `INSERT OR IGNORE` statements for `max_position_size_pct='2.0'`, `max_daily_loss_dollars='500.0'`, `signal_staleness_minutes='5'`; `down_revision='004'` |
| `trumptrade/analysis/worker.py` | enqueue block after Signal commit | VERIFIED | Lines 280–302: guard `if final_action in ("BUY", "SELL") and final_tickers`, local import of `signal_queue`/`QueueItem`, `put_nowait()` with `QueueFull` catch |
| `trumptrade/trading/executor.py` | signal_id optional parameter on execute() and _log_order() | VERIFIED | `execute(self, symbol, side, qty, signal_id: int | None = None)` at line 29; `_log_order(..., signal_id: int | None = None)` at line 129; `signal_id=signal_id` passed to `Order(...)` at line 141 |
| `trumptrade/core/app.py` | risk_consumer task in lifespan, settings_router in create_app() | VERIFIED | `asyncio.create_task(risk_consumer(), name="risk_consumer")` at line 52; `_consumer_task.cancel()` + `await _consumer_task` in shutdown block (lines 60–64); unconditional `app.include_router(settings_router, prefix="/settings")` at line 93 |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `trumptrade/risk_guard/__init__.py` | `trumptrade/risk_guard/guard.py` | `from trumptrade.risk_guard.guard import QueueItem` | WIRED | Direct import at line 12 — no try/except stub |
| `trumptrade/risk_guard/__init__.py` | `trumptrade/risk_guard/router.py` | `from trumptrade.risk_guard.router import router as settings_router` | WIRED | Direct import at line 13 |
| `trumptrade/risk_guard/guard.py` | `trumptrade/trading/executor.py` | `executor.execute(symbol, item.side.lower(), qty, signal_id=item.signal_id)` | WIRED | Line 211 in `_execute_for_tickers()`; local import of `AlpacaExecutor` at line 189 |
| `trumptrade/analysis/worker.py` | `trumptrade/risk_guard` (signal_queue) | `signal_queue.put_nowait(item)` | WIRED | Local import at line 284 inside loop body; `put_nowait` at line 294 |
| `trumptrade/core/app.py` | `trumptrade/risk_guard/guard.risk_consumer` | `asyncio.create_task(risk_consumer(), ...)` | WIRED | Local import at line 51; `create_task` at line 52 |
| `trumptrade/core/app.py` | `trumptrade/risk_guard/router.py` | `app.include_router(settings_router, prefix="/settings")` | WIRED | Line 93; unconditional (None guard removed in plan 03) |
| `alembic/versions/005_risk_settings.py` | `app_settings` table | `INSERT OR IGNORE` × 3 | WIRED | All 3 keys present in `upgrade()` at lines 27, 29, 31 |
| `trumptrade/trading/executor.py` | `trumptrade/core/models.Order.signal_id` | `Order(... signal_id=signal_id)` | WIRED | Line 141 in `_log_order()`; closes SC-4 audit chain |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `guard.py:_check_daily_cap` | `equity`, `last_equity` | `trading_client.get_account()` via `run_in_executor` | Yes — live Alpaca account call; `Optional[str]` None-guarded before `float()` conversion | FLOWING |
| `guard.py:_compute_qty` | `share_price` | `data_client.get_stock_latest_trade()` via `run_in_executor` + `partial` | Yes — live market data call; returns real price per symbol | FLOWING |
| `guard.py:_get_setting` | `val` | `AsyncSessionLocal` + `select(AppSettings.value)` | Yes — DB read with `scalar_one_or_none()` + default fallback; seeded by migration 005 | FLOWING |
| `router.py:get_risk_settings` | all 4 risk values | `_read_setting()` → `AsyncSessionLocal` → `app_settings` table | Yes — live DB reads; seeded by migration 005 | FLOWING |
| `worker.py` enqueue block | `QueueItem` fields | `signal.id` (post-commit PK), `post.id`, `final_tickers` (list[str]), `post.posted_at` | Yes — all fields from committed DB objects; no hardcoded values | FLOWING |

---

### Behavioral Spot-Checks

Step 7b: SKIPPED — verifying running server endpoints requires live Alpaca credentials and the uvicorn event loop. Import-level checks were substituted.

| Behavior | Check | Result | Status |
|----------|-------|--------|--------|
| `signal_queue.maxsize == 100` | File inspection: `asyncio.Queue(maxsize=100)` at `__init__.py` line 17 | Confirmed | PASS |
| `risk_consumer()` propagates `CancelledError` | Grep: `raise  # CRITICAL` at guard.py line 356; `except asyncio.CancelledError:` before broad `except Exception` | Confirmed pattern correct | PASS |
| `_check_staleness` uses naive UTC comparison | Grep: `datetime.now(timezone.utc).replace(tzinfo=None)` at guard.py line 95 | Confirmed | PASS |
| `_compute_qty` uses `math.floor` not `round` | Grep: `math.floor(trade_dollars / share_price)` at guard.py line 169 | Confirmed | PASS |
| SKIP signals never enqueued | Grep: `if final_action in ("BUY", "SELL")` at worker.py line 283 | Confirmed — SKIP cannot satisfy this condition | PASS |
| Migration 005 revises 004 | File inspection: `down_revision: ... = "004"` at migration line 20 | Confirmed | PASS |
| `settings_router` is not None stub | Grep: no `try/except ImportError` or `settings_router = None` in `__init__.py` | Confirmed — direct import only | PASS |

---

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| TRADE-04 | 05-01, 05-02, 05-03 | Check market hours before executing; discard stale signals | SATISFIED | `_check_staleness()` enforces staleness threshold; `get_clock().is_open` enforces market hours; both write reason codes to Signal.reason_code |
| RISK-01 | 05-01, 05-02, 05-03 | Position size as % of portfolio per trade | SATISFIED | `_compute_qty()` formula: `equity * (max_position_size_pct/100) * confidence / price`; `max_position_size_pct` configurable via `/settings/risk` PATCH |
| RISK-02 | 05-01, 05-02, 05-03 | Stop-loss threshold % exposed as configurable setting | SATISFIED | `stop_loss_pct` key exposed in `GET/PATCH /settings/risk` (router.py); bracket order attachment was implemented in Phase 2; Phase 5 adds the settings endpoint interface required by the requirement |
| RISK-03 | 05-01, 05-02, 05-03 | Max daily loss cap enforced by reading live Alpaca account value | SATISFIED | `_check_daily_cap()` reads live `last_equity` and `equity` from Alpaca; blocks on `DAILY_CAP_HIT`; `max_daily_loss_dollars` configurable |
| SETT-02 | 05-03 | User can set risk controls from dashboard: position size %, stop-loss %, max daily loss cap | SATISFIED | `GET /settings/risk` returns all 4 controls; `PATCH /settings/risk` accepts partial updates with Pydantic validation; human checkpoint confirmed endpoint works |

No orphaned requirements: all 5 requirement IDs declared across plans (TRADE-04, RISK-01, RISK-02, RISK-03, SETT-02) are mapped to Phase 5 in REQUIREMENTS.md traceability table and verified above.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `guard.py` | 30 | `_hold_list: list[...] = []` module-level mutable | Info | Intentional per D-04: signal loss on restart is accepted design decision; not a bug |
| `guard.py` | 355–356 | `except asyncio.CancelledError: raise` | Info (good pattern) | Correct — CancelledError re-raised before broad Exception; this is the required pattern, not an anti-pattern |

No blockers found. No TODO/FIXME/placeholder comments in phase 5 files. No `return {}` or `return []` stubs in routes or consumer. No hardcoded empty values flowing to rendering.

---

### Human Verification Required

#### 1. End-to-End Pipeline with Live Alpaca Paper Account

**Test:** Start the server (`python -m trumptrade`), confirm "Risk consumer task started" in logs, then either (a) trigger a real post through ingestion/analysis or (b) directly insert a test Post + Signal and manually call `signal_queue.put_nowait(QueueItem(...))` from a test script, then verify an Order row is created in the DB with `signal_id` populated.

**Expected:** Order row exists in `orders` table with `signal_id` matching the Signal row; `alpaca_order_id` is a real UUID from Alpaca paper environment; `signal_id` chain is complete (Post → Signal → Order).

**Why human:** Requires live Alpaca paper API credentials (`ALPACA_API_KEY`, `ALPACA_SECRET_KEY`) in `.env`, a running uvicorn server with the asyncio event loop active, and either a live post from Truth Social/Twitter or a manually enqueued test item.

#### 2. Settings Endpoint Live Update and Next-Cycle Effect

**Test:** With server running: (1) call `GET /settings/risk` and record defaults; (2) call `PATCH /settings/risk` with `{"signal_staleness_minutes": 10}`; (3) call `GET /settings/risk` again and confirm `signal_staleness_minutes` is 10; (4) restore to 5 via another PATCH.

**Expected:** PATCH returns 200 with updated value; subsequent GET confirms persistence; server logs confirm the update; risk_consumer reads updated value on next signal cycle.

**Why human:** Confirming that DB writes persist and are read by the running consumer on the next cycle requires a live server instance.

#### 3. Clean Shutdown (No Pending Task Warning)

**Test:** Send SIGINT (Ctrl+C) to the running server. Check logs for shutdown sequence.

**Expected:** Logs show "Risk consumer task stopped" before "APScheduler stopped"; no `Task was destroyed but it is pending!` Python warning in stderr.

**Why human:** Requires observing actual process shutdown behavior with the asyncio event loop running.

---

### Gaps Summary

No gaps found. All code is substantive, wired, and data-flowing. The phase goal — signals flowing through a single risk chokepoint before reaching the executor, with capital protected by position sizing, daily loss cap, and market hours enforcement — is achieved in the codebase.

The `human_needed` status reflects that 3 of the 5 roadmap success criteria involve live runtime behavior (end-to-end execution, settings persistence, clean shutdown) that cannot be verified without running services. The 05-03-SUMMARY.md records that a human checkpoint was APPROVED on 2026-04-21 covering all 5 verification steps. If that approval is accepted as sufficient evidence, status can be upgraded to `passed`.

---

_Verified: 2026-04-21_
_Verifier: Claude (gsd-verifier)_
