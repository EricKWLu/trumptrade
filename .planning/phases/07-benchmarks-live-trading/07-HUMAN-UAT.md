---
status: partial
phase: 07-benchmarks-live-trading
source: [07-VERIFICATION.md]
started: 2026-04-23T00:00:00Z
updated: 2026-04-23T00:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Live Mode Activation
expected: Type "ENABLE LIVE TRADING" in the modal (Settings → Trading Mode → Switch to LIVE Trading). Confirm button stays disabled until the full exact phrase is typed (case-sensitive). After clicking Confirm, a red "LIVE TRADING ACTIVE — real money at risk" banner appears at the top of every page.

result: [pending]

### 2. Paper Mode Return
expected: From live mode, click "Switch to PAPER Trading". Type "ENABLE PAPER TRADING". Dismiss button reads "Keep LIVE mode". After confirming, the red banner disappears and the badge reverts to PAPER.

result: [pending]

### 3. Benchmarks Nav
expected: Sidebar shows order: Feed → Trades → Portfolio → Benchmarks → Settings. Benchmarks has the LineChart icon. Clicking navigates to /benchmarks which shows the empty-state ("No benchmark data yet. Check back after today's market close (4:01 PM ET)...").

result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
