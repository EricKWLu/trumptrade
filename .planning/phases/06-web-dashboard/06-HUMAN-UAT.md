---
status: partial
phase: 06-web-dashboard
source: [06-VERIFICATION.md]
started: 2026-04-21T00:00:00Z
updated: 2026-04-21T00:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Sidebar layout visual rendering
expected: Dark sidebar renders with all 4 nav links (Feed, Trades, Portfolio, Settings), prominent red Stop Bot button at top, PAPER/LIVE badge at bottom, alert panel below nav — matches UI-SPEC dark mode layout
result: [pending]

### 2. WebSocket live push in FeedPage
expected: New Trump posts auto-insert at top of feed without page refresh; reconnect chip appears on disconnect; posts show platform icon, relative timestamp, sentiment badge, and filtered-gray treatment for filtered posts
result: [pending]

### 3. Kill switch toggle
expected: Button shows correct initial state (Stop Bot / Start Bot) based on backend; clicking toggles immediately (optimistic); trade execution halts when stopped; button reverts on API error
result: [pending]

### 4. TradesPage expandable audit chain
expected: Trade table rows expand on click to show full audit chain: post content, signal details (sentiment, confidence, tickers, reason), fill price, and raw LLM prompt+response in collapsible code block
result: [pending]

### 5. PortfolioPage live data + refresh
expected: 3 summary cards show equity, P&L today, buying power from live Alpaca API; positions table shows current holdings; data refreshes on interval
result: [pending]

### 6. SettingsPage watchlist + risk controls
expected: Watchlist chips show current tickers with X to remove; text input adds new ticker; risk controls form shows current values; Save Changes submits all 4 fields; "Settings saved." feedback appears
result: [pending]

## Summary

total: 6
passed: 0
issues: 0
pending: 6
skipped: 0
blocked: 0

## Gaps
