# Phase 2: Alpaca Executor - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-19
**Phase:** 02-alpaca-executor
**Areas discussed:** Stub signal injection, Entry order type, Fill confirmation depth, Kill-switch endpoint

---

## Stub Signal Injection

| Option | Description | Selected |
|--------|-------------|----------|
| POST /trading/execute | Real FastAPI endpoint accepting signal payload; Phase 5 calls the same route from the risk guard queue | ✓ |
| Internal Python call only | Service class with async execute() method, tested via Python script, not HTTP | |
| POST /trading/stub-signal | Dev-only named endpoint explicitly signaling it's a test entry point | |

**User's choice:** POST /trading/execute (Recommended)
**Notes:** Same endpoint used by Phase 5 risk guard — no special stub endpoint needed.

---

## Entry Order Type + Stop Price

| Option | Description | Selected |
|--------|-------------|----------|
| Market order + last price for stop | MARKET entry, fetch last trade price from Alpaca data API, compute stop as last_price * (1 - stop_loss_pct/100) | ✓ |
| Limit order at current ask | LIMIT entry at ask price, stop calculated exactly from limit price | |

**User's choice:** Market order + last price for stop (Recommended)
**Notes:** Simpler, fills immediately in paper mode. Stop is approximate but sufficient for Phase 2.

---

## Fill Confirmation Depth

| Option | Description | Selected |
|--------|-------------|----------|
| Log order ID on submission | Alpaca returns order ID on submission; write to orders table immediately | ✓ |
| Poll once after 5 seconds | GET /orders/{id} after delay; write fill record if filled | |
| Background poll until filled | Async task polls until status == filled; fills table populated in Phase 2 | |

**User's choice:** Log order ID on submission (Recommended)
**Notes:** "Confirmed" = Alpaca accepted the order. Fill tracking deferred to Phase 5.

---

## Kill-Switch Endpoint

| Option | Description | Selected |
|--------|-------------|----------|
| POST /trading/kill-switch with {"enabled": bool} | Single endpoint for halt and resume; updates bot_enabled in app_settings | ✓ |
| POST /trading/kill (halt only) | Dedicated halt endpoint; separate /trading/resume for resume | |
| PUT /settings/bot-enabled | Generic settings API endpoint; implies full settings API built in Phase 2 | |

**User's choice:** POST /trading/kill-switch with {"enabled": bool} (Recommended)
**Notes:** Phase 6 dashboard toggle calls this same endpoint.

---

## Claude's Discretion

- AlpacaExecutor service class architecture (thin HTTP layer, service handles logic)
- Pydantic request/response models
- Error handling structure (4xx/5xx with JSON)

## Deferred Ideas

None
