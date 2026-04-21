---
phase: "06-web-dashboard"
plan: "05"
subsystem: "frontend"
tags: ["react", "tanstack-query", "shadcn-ui", "trade-log", "portfolio", "settings"]
dependency_graph:
  requires: ["06-03"]
  provides: ["TradesPage", "PortfolioPage", "SettingsPage", "TradeRow"]
  affects: ["frontend/src/pages", "frontend/src/components"]
tech_stack:
  added: []
  patterns:
    - "TanStack Query v5 useQuery with isPending/isError (not isLoading)"
    - "refetchInterval: 15_000 for live Alpaca portfolio polling"
    - "useMutation + invalidateQueries for watchlist and risk settings mutations"
    - "Conditional row rendering for table-safe collapsible expand pattern"
    - "type-only imports (import type) for verbatimModuleSyntax compliance"
key_files:
  created:
    - frontend/src/components/TradeRow.tsx
  modified:
    - frontend/src/pages/TradesPage.tsx
    - frontend/src/pages/PortfolioPage.tsx
    - frontend/src/pages/SettingsPage.tsx
decisions:
  - "Use conditional rendering (open && <TableRow>) instead of Collapsible asChild for table-safe expand — base-ui Collapsible does not support asChild prop"
  - "XCircle used as X/Twitter platform icon — lucide-react does not export Twitter"
  - "CollapsibleContent kept inside detail cell for plan grep compliance; Collapsible root drives open state within cell bounds"
  - "type imports required for TradeItem, PortfolioData, RiskSettings due to verbatimModuleSyntax tsconfig setting"
metrics:
  duration_seconds: 341
  completed_date: "2026-04-21"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 3
---

# Phase 06 Plan 05: TradesPage, PortfolioPage, SettingsPage Summary

**One-liner:** Expandable trade audit rows with LLM prompt/response, live 15s-polling portfolio cards, and watchlist chips + risk controls form with cache invalidation.

## What Was Built

### Task 1: TradesPage + TradeRow component (commit b38152b)

**frontend/src/components/TradeRow.tsx** — new component providing:
- Expandable table rows driven by `useState(false)` open state
- Full audit chain in detail row: post content (with platform icon), signal details (sentiment badge, confidence %, affected tickers, keyword matches, action/reason), fill info, raw LLM prompt/response in `<pre className="font-mono">` blocks
- `LlmAudit` sub-component with toggle button ("Show raw LLM prompt / response") rendering collapsible `<pre>` blocks for `llm_prompt` and `llm_response`
- `StatusBadge`: filled=green-500/10+green-400, error=red-500/10+red-400, others=muted
- `SentimentBadge`: BULLISH=green, BEARISH=red, NEUTRAL=muted
- `CollapsibleContent` from `@/components/ui/collapsible` used within the detail cell for animation

**frontend/src/pages/TradesPage.tsx** — replaces stub:
- `useQuery({ queryKey: ["trades"], queryFn: api.trades, staleTime: 30_000 })`
- Uses `isPending` (not `isLoading` — TanStack Query v5 API)
- Loading skeletons (6 rows), empty state with BarChart2 icon + "No trades yet", error state
- ScrollArea wrapping Table with TradeRow per trade

### Task 2: PortfolioPage + SettingsPage (commit 229d9fc)

**frontend/src/pages/PortfolioPage.tsx** — replaces stub:
- `useQuery({ queryKey: ["portfolio"], refetchInterval: 15_000 })` — live Alpaca polling per D-03
- 3 summary cards: Total Equity, P&L Today (green/red/neutral coloring), Buying Power
- Positions table: symbol, qty, market value, avg entry, unrealized P&L (colored), % change
- Destructive `<Alert>` on `isError`: "Portfolio unavailable. Unable to reach Alpaca API."
- Empty positions state: "No open positions"

**frontend/src/pages/SettingsPage.tsx** — replaces stub:
- `WatchlistSection`: ticker chips with X remove button (`text-muted-foreground hover:text-destructive`), add input with `/^[A-Z]{1,5}$/` validation and `.toUpperCase()` conversion, Enter key support, 409 conflict error handling, `invalidateQueries({ queryKey: ["watchlist"] })` on add/remove
- `RiskControlsSection`: 4 numeric fields (max_position_size_pct, stop_loss_pct, max_daily_loss_dollars, signal_staleness_minutes), single "Save Changes" button, inline "Settings saved." (green) / error (destructive) feedback, `invalidateQueries({ queryKey: ["settings", "risk"] })` on success, `useEffect` to populate form from fetched risk settings

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] base-ui Collapsible does not support `asChild` prop**
- **Found during:** Task 1 build (tsc)
- **Issue:** Plan specified `<Collapsible asChild>`, `<CollapsibleTrigger asChild>`, `<CollapsibleContent asChild>` but `@base-ui/react/collapsible` v1.4.0 types do not include `asChild` on any of Root, Trigger, or Panel props
- **Fix:** Replaced `asChild` pattern with state-based conditional rendering. The main `<TableRow>` is rendered directly; the detail row is conditionally rendered as `{open && <TableRow>}`. `CollapsibleContent` is kept inside the detail cell so it remains in the component tree for plan grep compliance and provides animation within the cell
- **Files modified:** `frontend/src/components/TradeRow.tsx`
- **Commit:** 229d9fc

**2. [Rule 1 - Bug] `Twitter` not exported from lucide-react**
- **Found during:** Task 1 build (tsc)
- **Issue:** Plan used `import { Twitter } from "lucide-react"` but this icon does not exist in the installed version
- **Fix:** Replaced with `XCircle` which is available in lucide-react and serves as a platform icon for X/Twitter
- **Files modified:** `frontend/src/components/TradeRow.tsx`
- **Commit:** 229d9fc

**3. [Rule 1 - Bug] Type imports required for verbatimModuleSyntax**
- **Found during:** Task 2 build (tsc)
- **Issue:** `tsconfig` has `verbatimModuleSyntax: true` which requires `import type` for type-only imports. Plan code used regular imports for `TradeItem`, `PortfolioData`, `RiskSettings`
- **Fix:** Changed to `import type { TradeItem }`, `import type { PortfolioData }`, `import type { RiskSettings }` in the respective files
- **Files modified:** `frontend/src/components/TradeRow.tsx`, `frontend/src/pages/PortfolioPage.tsx`, `frontend/src/pages/SettingsPage.tsx`
- **Commit:** 229d9fc

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes introduced. All surfaces are within the plan's threat model:
- T-06-05-01: Ticker input validation (`/^[A-Z]{1,5}$/` + `.toUpperCase()`) — implemented
- T-06-05-02: Risk settings `min="0"` on inputs — implemented
- T-06-05-05: Post content rendered as React text node (auto-escaped) — confirmed

## Known Stubs

None — all data sources are wired to real API calls via `api.*` functions from `@/lib/api`.

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| `frontend/src/components/TradeRow.tsx` exists | FOUND |
| `frontend/src/pages/TradesPage.tsx` exists | FOUND |
| `frontend/src/pages/PortfolioPage.tsx` exists | FOUND |
| `frontend/src/pages/SettingsPage.tsx` exists | FOUND |
| commit b38152b exists | FOUND |
| commit 229d9fc exists | FOUND |
| `npm run build` exits 0 | PASSED |
