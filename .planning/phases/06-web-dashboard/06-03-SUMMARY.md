---
phase: 06-web-dashboard
plan: "03"
subsystem: frontend-shell
tags: [react, react-router-dom, shadcn, websocket, tanstack-query, typescript]
dependency_graph:
  requires:
    - frontend/src/main.tsx (QueryClientProvider wrapping)
    - frontend/src/lib/utils.ts (cn() utility)
    - frontend/src/components/ui/button.tsx (KillSwitchBtn)
    - trumptrade/dashboard/router.py (GET /alerts, GET /trading/status)
    - trumptrade/dashboard/ws.py (/ws/feed WebSocket endpoint)
    - trumptrade/dashboard/watchlist.py (GET/POST/DELETE /watchlist)
  provides:
    - frontend/src/router.tsx (createBrowserRouter with 4 child routes)
    - frontend/src/components/AppShell.tsx (sidebar layout with Outlet)
    - frontend/src/components/KillSwitchBtn.tsx (optimistic kill switch)
    - frontend/src/components/AlertPanel.tsx (10s-polling alert panel)
    - frontend/src/lib/api.ts (typed fetch wrappers for all backend endpoints)
    - frontend/src/hooks/usePostFeed.ts (WebSocket hook with exponential backoff)
    - frontend/src/pages/FeedPage.tsx (stub — Plan 04 fills)
    - frontend/src/pages/TradesPage.tsx (stub — Plan 05 fills)
    - frontend/src/pages/PortfolioPage.tsx (stub — Plan 05 fills)
    - frontend/src/pages/SettingsPage.tsx (stub — Plan 05 fills)
  affects:
    - Plan 06-04 (FeedPage content)
    - Plan 06-05 (TradesPage, PortfolioPage, SettingsPage content)
tech_stack:
  added:
    - react-router-dom@6.30.3 (pinned v6, not v7)
    - shadcn components: badge, card, table, collapsible, input, separator, skeleton, alert, tooltip, scroll-area
  patterns:
    - createBrowserRouter with index route (not path="/") for FeedPage
    - Optimistic mutation with onMutate/onError rollback for KillSwitchBtn
    - WebSocket hook with exponential backoff (1s initial, 2x per retry, 30s cap)
    - type-only imports for verbatimModuleSyntax compliance
key_files:
  created:
    - frontend/src/router.tsx
    - frontend/src/components/AppShell.tsx
    - frontend/src/components/KillSwitchBtn.tsx
    - frontend/src/components/AlertPanel.tsx
    - frontend/src/lib/api.ts
    - frontend/src/hooks/usePostFeed.ts
    - frontend/src/pages/FeedPage.tsx
    - frontend/src/pages/TradesPage.tsx
    - frontend/src/pages/PortfolioPage.tsx
    - frontend/src/pages/SettingsPage.tsx
  modified:
    - frontend/src/App.tsx (rewritten to use RouterProvider)
    - frontend/package.json (react-router-dom@6 added)
    - frontend/src/components/ui/scroll-area.tsx (removed unused React import)
decisions:
  - "react-router-dom pinned to v6 (^6.30.3) not v7 — CONTEXT.md decision D-router-v6"
  - "KillSwitchBtn uses local optimistic state (useState) not queryClient.setQueryData — simpler for boolean toggle with server reconcile on success"
  - "usePostFeed exponential backoff capped at 30s — balances reconnect speed vs server load"
  - "AlertPanel hides entirely when alerts=[] — clean sidebar with no empty panel"
  - "type-only imports (import type) required by verbatimModuleSyntax in tsconfig"
metrics:
  duration: "~8 minutes"
  completed: "2026-04-21"
  tasks_completed: 2
  tasks_total: 2
  files_created: 10
  files_modified: 3
---

# Phase 06 Plan 03: React Shell Summary

**One-liner:** React router shell with sidebar layout, optimistic kill switch, 10s-polling alert panel, typed API client, WebSocket hook with exponential backoff, and 10 shadcn components installed.

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 | Install react-router-dom@6 + 10 shadcn UI components | c195c38 | package.json, package-lock.json, ui/badge.tsx, ui/card.tsx, ui/table.tsx, ui/collapsible.tsx, ui/input.tsx, ui/separator.tsx, ui/skeleton.tsx, ui/alert.tsx, ui/tooltip.tsx, ui/scroll-area.tsx |
| 2 | Build router shell: App.tsx, router.tsx, AppShell, KillSwitchBtn, AlertPanel, api.ts, usePostFeed, page stubs | 7dc69f0 | App.tsx, router.tsx, AppShell.tsx, KillSwitchBtn.tsx, AlertPanel.tsx, api.ts, usePostFeed.ts, FeedPage.tsx, TradesPage.tsx, PortfolioPage.tsx, SettingsPage.tsx, scroll-area.tsx |

## What Was Built

### frontend/src/router.tsx
- `createBrowserRouter` with AppShell as root layout
- 4 child routes: `index: true` (FeedPage), trades, portfolio, settings
- Uses `index: true` for FeedPage — not `path: "/"` (avoids double-match with parent)

### frontend/src/components/AppShell.tsx
- Fixed 240px sidebar (w-60, flex-shrink-0) — never collapses per D-01
- KillSwitchBtn at sidebar top (D-09), AlertPanel below nav (D-10), PAPER/LIVE badge at bottom (D-02)
- `TradingModeBadge` fetches from `api.portfolio()` every 60s; defaults to "paper" on error
- NavLink with active state styling (border-l-2 border-primary highlight)
- `<Outlet />` renders child page content in main area

### frontend/src/components/KillSwitchBtn.tsx
- Fetches initial state from GET /trading/status with `staleTime: Infinity`
- Optimistic toggle: `onMutate` sets local state, `onError` reverts, `onSuccess` reconciles
- Shows "Stop Bot" (variant="destructive") when enabled, "Start Bot" (bg-green-600) when disabled
- Loader2 spinner during pending mutation

### frontend/src/components/AlertPanel.tsx
- Polls GET /alerts every 10s (`refetchInterval: 10_000`, `staleTime: 0`)
- Returns null (no render) when alerts array is empty
- AlertIcon distinguishes alpaca/llm errors (XCircle) from scraper silence (AlertTriangle)
- ScrollArea with max-h-60 for overflow

### frontend/src/lib/api.ts
- `apiFetch<T>()` generic fetch wrapper — throws on non-ok responses
- `api` object with 10 typed methods: posts, trades, portfolio, watchlist, riskSettings, alerts, addWatchlist, removeWatchlist, patchRiskSettings, toggleKillSwitch
- Full TypeScript interfaces: PostItem, SignalDetail, FillDetail, TradeItem, PositionItem, PortfolioData, WatchlistItem, RiskSettings, AlertItem, PostFeedMessage

### frontend/src/hooks/usePostFeed.ts
- Connects to `ws://localhost:8000/ws/feed`
- Prepends incoming messages to posts array (newest at top, D-06)
- Exponential backoff: starts at 1s, doubles per failure, caps at 30s
- Cleans up WebSocket on unmount via `unmountedRef` guard

### Page Stubs
- FeedPage, TradesPage, PortfolioPage, SettingsPage — minimal placeholders for Plans 04/05

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed verbatimModuleSyntax type-only import errors**
- **Found during:** Task 2 build verification (`npm run build`)
- **Issue:** `AlertItem` in AlertPanel.tsx and `PostFeedMessage` in usePostFeed.ts were value-imported but are type-only — TypeScript strict mode (`verbatimModuleSyntax`) requires `import type`
- **Fix:** Changed to `import type { AlertItem }` and `import type { PostFeedMessage }`
- **Files modified:** frontend/src/components/AlertPanel.tsx, frontend/src/hooks/usePostFeed.ts
- **Commit:** 7dc69f0 (included in Task 2 commit)

**2. [Rule 1 - Bug] Removed unused React import from shadcn-generated scroll-area.tsx**
- **Found during:** Task 2 build verification (`npm run build`)
- **Issue:** shadcn scaffold generated `import * as React from "react"` but none of the component code uses it — TypeScript TS6133 error
- **Fix:** Removed the unused import line
- **Files modified:** frontend/src/components/ui/scroll-area.tsx
- **Commit:** 7dc69f0 (included in Task 2 commit)

## Known Stubs

The following page stubs are intentional — they will be filled by later plans:

| File | Stub Content | Filled By |
|------|-------------|-----------|
| frontend/src/pages/FeedPage.tsx | "Loading feed..." placeholder | Plan 06-04 |
| frontend/src/pages/TradesPage.tsx | "Loading trades..." placeholder | Plan 06-05 |
| frontend/src/pages/PortfolioPage.tsx | "Loading portfolio..." placeholder | Plan 06-05 |
| frontend/src/pages/SettingsPage.tsx | "Loading settings..." placeholder | Plan 06-05 |

These stubs do not prevent this plan's goal (router shell with navigation) from being achieved. The sidebar layout, kill switch, alert panel, API client, and WebSocket hook are all fully wired.

## Threat Flags

No new threat surface beyond what is documented in the plan's threat model (T-06-03-01 through T-06-03-05).

| T-ID | Mitigation Status |
|------|-------------------|
| T-06-03-01 | Accepted — KillSwitchBtn sends typed boolean only |
| T-06-03-02 | Mitigated — JSON.parse in try/catch in usePostFeed.ts |
| T-06-03-03 | Accepted — in-memory on backend, personal tool |
| T-06-03-04 | Accepted — cosmetic default, no security boundary |
| T-06-03-05 | Accepted — WebSocket only accessible locally |

## Self-Check: PASSED

**Files exist:**
- frontend/src/router.tsx: FOUND (contains createBrowserRouter, index: true)
- frontend/src/components/AppShell.tsx: FOUND (contains Outlet, KillSwitchBtn, AlertPanel)
- frontend/src/components/KillSwitchBtn.tsx: FOUND (variant="destructive", bg-green-600)
- frontend/src/components/AlertPanel.tsx: FOUND (refetchInterval: 10_000)
- frontend/src/lib/api.ts: FOUND (exports api, apiFetch)
- frontend/src/hooks/usePostFeed.ts: FOUND (ws://localhost:8000/ws/feed, retryDelayRef.current = delay * 2)
- frontend/src/pages/FeedPage.tsx: FOUND
- frontend/src/pages/TradesPage.tsx: FOUND
- frontend/src/pages/PortfolioPage.tsx: FOUND
- frontend/src/pages/SettingsPage.tsx: FOUND

**Commits exist:**
- c195c38: FOUND (Task 1 — shadcn install)
- 7dc69f0: FOUND (Task 2 — router shell)

**Build:** npm run build — PASSED (zero TypeScript errors, 1868 modules transformed)
