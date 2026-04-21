# Phase 6: Web Dashboard - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-21
**Phase:** 06-web-dashboard
**Areas discussed:** Overall layout, Post feed display, Trade log, Kill switch + settings

---

## Overall Layout

| Option | Description | Selected |
|--------|-------------|----------|
| Sidebar nav | Persistent left sidebar, separate routes per section | ✓ |
| Top tab bar | Horizontal tabs across the top | |
| Single page, scroll | All sections stacked vertically | |

**User's choice:** Sidebar nav
**Notes:** Four sections: Feed, Trades, Portfolio, Settings.

---

## Portfolio Display

| Option | Description | Selected |
|--------|-------------|----------|
| Summary cards + positions table | Equity/P&L cards at top, table below | ✓ |
| Positions table only | Just the table | |
| You decide | Claude picks layout | |

**User's choice:** Summary cards + positions table

---

## Trading Mode Indicator

| Option | Description | Selected |
|--------|-------------|----------|
| Sidebar badge | PAPER/LIVE badge at bottom of sidebar | ✓ |
| Top bar | Small indicator in top right | |
| Settings page only | Only visible in Settings | |

**User's choice:** Sidebar badge

---

## Post Feed Display

| Option | Description | Selected |
|--------|-------------|----------|
| Full content + sentiment badge | Full text, platform icon, timestamp, colored badge | ✓ |
| Content preview + sentiment | Truncated 2-line preview with expand | |
| Minimal — sentiment + ticker only | No post text | |

**User's choice:** Full content + sentiment badge
**Notes:** Filtered posts shown grayed out with filter reason.

---

## WebSocket Feed Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-insert at top | New posts slide in without user action | ✓ |
| "New posts" banner | Sticky banner, user clicks to load | |
| Manual refresh only | User clicks refresh | |

**User's choice:** Auto-insert at top

---

## Trade Log Layout

| Option | Description | Selected |
|--------|-------------|----------|
| Expandable rows | Table row expands to show full audit chain | ✓ |
| Flat table, all fields | Wide table with all columns visible | |
| Separate detail page | Link to dedicated page per order | |

**User's choice:** Expandable rows

---

## LLM Prompt/Response in Audit Trail

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — show in expanded view | Raw LLM text in collapsible code block | ✓ |
| No — just structured fields | Only sentiment, confidence, final action | |

**User's choice:** Yes — show raw LLM prompt and response
**Notes:** Intentional for debugging signal quality.

---

## Kill Switch Prominence

| Option | Description | Selected |
|--------|-------------|----------|
| Prominent red button in sidebar | Always visible, single click | ✓ |
| Toggle in Settings only | Less visible, requires navigation | |
| Prominent + confirmation modal | Always visible, confirmation before stop | |

**User's choice:** Prominent red button in sidebar (single click, no modal)

---

## Alert Panel

| Option | Description | Selected |
|--------|-------------|----------|
| Persistent alert panel in sidebar | Errors persist below nav, count badge | ✓ |
| Toast notifications only | Auto-dismiss toasts in corner | |
| Dedicated Alerts section | Separate nav tab | |

**User's choice:** Persistent alert panel in sidebar

---

## Settings UI

| Option | Description | Selected |
|--------|-------------|----------|
| Settings page with two sections | Dedicated page: Watchlist + Risk Controls | ✓ |
| Inline editing everywhere | Settings editable in-context across pages | |
| Modal dialogs | Settings gear opens modal | |

**User's choice:** Settings page with two sections (Watchlist chips + Risk form)

---

## Claude's Discretion

- shadcn/ui component selection
- Exact badge color palette (BULLISH/BEARISH/NEUTRAL)
- Loading skeleton designs
- Empty state designs
- WebSocket reconnect behavior
- Alert clearing behavior

## Deferred Ideas

None.
