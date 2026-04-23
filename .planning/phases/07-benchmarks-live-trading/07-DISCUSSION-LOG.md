# Phase 7: Benchmarks + Live Trading - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-23
**Phase:** 07-benchmarks-live-trading
**Areas discussed:** Comparison chart, Live trading unlock UX, Shadow portfolio start date

---

## Comparison Chart

| Option | Description | Selected |
|--------|-------------|----------|
| Since bot start | Full history always visible, no configuration needed | ✓ |
| Last 30 days | Rolling window, hides early history | |
| User-selectable range | 1W/1M/All buttons, more UI work | |

**Time range chosen:** Since bot start

| Option | Description | Selected |
|--------|-------------|----------|
| Bot + SPY + QQQ + Random | All 4 lines, complete picture | ✓ |
| Bot vs SPY only | Simpler, less visual noise | |
| Toggleable lines | Checkboxes, more flexible | |

**Lines chosen:** All 4 on one chart

| Option | Description | Selected |
|--------|-------------|----------|
| % return from start | Fair comparison, all start at 0% | ✓ |
| Absolute NAV in dollars | Real dollar value, requires configured starting amount | |

**Y-axis metric:** % return from start

---

## Live Trading Unlock UX

| Option | Description | Selected |
|--------|-------------|----------|
| Type phrase + click confirm | Type 'ENABLE LIVE TRADING', hard to do by accident | ✓ |
| Two separate modal clicks | Two modals with delay, no typing | |
| Settings toggle with delay | 10-second countdown, cancellable | |

**Unlock flow:** Type phrase + confirm

| Option | Description | Selected |
|--------|-------------|----------|
| Sidebar badge + page header | Red LIVE badge in sidebar + banner on every page | ✓ |
| Sidebar only | Subtle but always visible | |
| Header only | High visibility, takes screen space | |

**LIVE indicator:** Sidebar badge + page header banner

| Option | Description | Selected |
|--------|-------------|----------|
| Same confirmation to revert | Typing required both directions | ✓ |
| One click to revert to paper | Paper mode is lower risk | |

**Switching back to paper:** Same typed confirmation required

---

## Shadow Portfolio Start Date

| Option | Description | Selected |
|--------|-------------|----------|
| From first app run | No backfill, grows over time | ✓ |
| Backfill from user-set date | Longer history immediately, more work | |
| Backfill from first bot trade | Aligns with actual trading activity | |

**Start date:** First app run (no backfill)

| Option | Description | Selected |
|--------|-------------|----------|
| Daily at market close | One snapshot/day at 4pm ET, simple | ✓ |
| Real-time (intraday) | Accurate but complex and not meaningful for daily chart | |

**Update frequency:** Daily at market close (4pm ET)

---

## Claude's Discretion

- Recharts chart styling (colors, tooltip, grid lines)
- Random baseline tie-breaking when watchlist has 1 ticker
- Chart loading skeleton and empty state (no data yet on day 1)
- Whether Benchmarks is a separate sidebar nav item or a tab in PortfolioPage

## Deferred Ideas

- User-selectable chart date range — not needed for v1
- Historical backfill — deferred, start-from-first-run is sufficient
- Random baseline configuration in Settings UI — Claude decides defaults
