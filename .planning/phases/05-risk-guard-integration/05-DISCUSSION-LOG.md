# Phase 5: Risk Guard + Integration - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-21
**Phase:** 05-risk-guard-integration
**Areas discussed:** Signal dispatch pipeline, Position sizing formula, Daily loss cap baseline, Staleness + market hours behavior

---

## Signal Dispatch Pipeline

| Option | Description | Selected |
|--------|-------------|----------|
| Direct enqueue | analysis_worker puts BUY/SELL signals onto asyncio.Queue after DB write | ✓ |
| DB poller | Separate scheduler job picks up unprocessed Signal rows | |
| asyncio background task (consumer) | create_task() in lifespan | ✓ |
| APScheduler job (consumer) | 1-second interval drains queue | |

**User's choice:** Direct enqueue + asyncio background task consumer
**Notes:** User asked for explanation of what a Signal is and how old posts are filtered before deciding. After explanation of the LEFT JOIN anti-join pattern and Phase 3 pre-filtering, chose the simpler direct enqueue approach.

---

## Position Sizing Formula

| Option | Description | Selected |
|--------|-------------|----------|
| Direct % of portfolio equity | max_position_size_pct in app_settings | ✓ |
| Low/Medium/High labels | Maps labels to fixed percentages | |
| LLM-determined with user cap | Confidence as multiplier on max_pct | ✓ |
| LLM explicit output | Add position_size field to SignalResult | |
| One trade per ticker | Position sizing per ticker independently | ✓ |
| Split pct across tickers | Divide max_pct by ticker count | |

**User's choice:** max_position_size_pct × confidence = actual trade size; one trade per affected ticker
**Notes:** User specifically requested the LLM (via confidence score) determine position size with a user-set cap. Chose confidence-as-multiplier approach over explicit LLM output field to avoid schema changes.

---

## Daily Loss Cap Baseline

| Option | Description | Selected |
|--------|-------------|----------|
| Use Alpaca last_equity field | No stored state, auto-resets at close | ✓ |
| Snapshot at server start / market open | Explicit baseline, stored in DB | |
| Dollar amount cap | max_daily_loss_dollars setting | ✓ |
| Percentage cap | max_daily_loss_pct × last_equity | |

**User's choice:** last_equity field as baseline; dollar-amount cap
**Notes:** User asked for clarification on how last_equity works (vs equity). After explanation that Alpaca updates last_equity at each market close and it's directly accessible from get_account(), chose this approach as it requires no stored state or snapshot jobs.

---

## Staleness + Market Hours Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Discard all after-hours signals | MARKET_CLOSED for all non-market signals | |
| Hold high-confidence signals until open | ≥0.85 confidence held in queue | ✓ |
| 5 minutes staleness (fixed) | Hard-coded threshold | |
| 15 minutes staleness (fixed) | More lenient threshold | |
| Configurable staleness (5-min default) | signal_staleness_minutes in app_settings | ✓ |
| Execute at open oldest-first | Held signals execute in arrival order | ✓ |
| Discard held signals at open | Very conservative, re-evaluate manually | |

**User's choice:** Hold ≥0.85 confidence after-hours, discard <0.85; execute at open oldest-first; staleness configurable with 5-min default
**Notes:** User initially asked if high-confidence signals could be held. After discussing the staleness/hold interaction (held signals would be STALE if the 5-min threshold applied), decided on separate staleness rule for held signals (24h expiry at market open). Hold threshold 0.85 is hardcoded (not configurable) to minimize settings surface.

---

## Claude's Discretion

- Default seed values: max_position_size_pct, max_daily_loss_dollars
- Pydantic schema for PATCH /settings/risk
- Error handling in consumer loop (log + continue on executor failures)

## Deferred Ideas

None.
