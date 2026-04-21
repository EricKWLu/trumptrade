---
phase: 06-web-dashboard
plan: "04"
subsystem: frontend-feed
tags: [react, tanstack-query, websocket, shadcn, lucide-react, typescript]
dependency_graph:
  requires:
    - frontend/src/lib/api.ts (PostItem, PostFeedMessage types, api.posts())
    - frontend/src/hooks/usePostFeed.ts (usePostFeed, ConnectionStatus)
    - frontend/src/components/ui/badge.tsx (Badge variant="outline")
    - frontend/src/components/ui/card.tsx (Card, CardContent)
    - frontend/src/components/ui/skeleton.tsx (Skeleton)
    - frontend/src/components/ui/scroll-area.tsx (ScrollArea)
    - frontend/src/lib/utils.ts (cn())
    - trumptrade/dashboard/ws.py (/ws/feed WebSocket endpoint)
    - trumptrade/dashboard/router.py (GET /posts endpoint)
  provides:
    - frontend/src/components/PostCard.tsx (PostCardData interface + PostCard component)
    - frontend/src/pages/FeedPage.tsx (full implementation replacing Plan 03 stub)
  affects:
    - Plan 06-05 (TradesPage, PortfolioPage, SettingsPage content)
tech_stack:
  added: []
  patterns:
    - TanStack Query v5 useQuery with isPending (not isLoading) for initial REST fetch
    - useMemo merge of WebSocket live posts + REST initial load, dedup by id
    - relativeTime() using Date arithmetic (no date-fns dependency added)
    - lucide-react X (aliased as XIcon) for Twitter/X platform icon
    - PostCardData union type accepting both REST PostItem and WS PostFeedMessage shapes
key_files:
  created:
    - frontend/src/components/PostCard.tsx
  modified:
    - frontend/src/pages/FeedPage.tsx
decisions:
  - "lucide-react dropped Twitter export in current version — replaced with 'X as XIcon' (auto-fixed Rule 1)"
  - "SentimentBadge keeps confidence in type signature for callers but does not display it separately — confidence % is rendered at call-site in FeedPage"
  - "relativeTime() implemented inline without date-fns — avoids adding a dependency for simple relative formatting"
  - "PostCardData uses optional signal field (not union discriminated) — simplest approach covering both REST (no signal) and WS (has signal) shapes"
metrics:
  duration: "~4 minutes"
  completed: "2026-04-21"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 1
---

# Phase 06 Plan 04: Feed Page + PostCard Summary

**One-liner:** FeedPage merges REST initial load (50 posts via TanStack Query) with live WebSocket prepend (usePostFeed), deduped by id; PostCard renders platform icon, relative timestamp, sentiment badge, confidence %, ticker chips, filtered state (opacity-40), and slide-in animation for new WS posts.

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 | Create PostCard component with full UI-SPEC styling | fd22ee3 | frontend/src/components/PostCard.tsx |
| 1 (fix) | Replace removed Twitter icon with X alias; drop unused confidence param | 4e45744 | frontend/src/components/PostCard.tsx |
| 2 | Implement FeedPage with WebSocket push + REST initial load merge | 4a4d9ac | frontend/src/pages/FeedPage.tsx |

## What Was Built

### frontend/src/components/PostCard.tsx

- `PostCardData` union interface — covers both REST `PostItem` (no signal) and WS `PostFeedMessage` (has signal) without needing separate components
- `relativeTime()` — inline relative timestamp using `Date` arithmetic; no additional dependencies
- `SentimentBadge` — renders BULLISH (`bg-green-500/10 text-green-400`), BEARISH (`bg-red-500/10 text-red-400`), NEUTRAL (`bg-muted text-muted-foreground`) per UI-SPEC
- `PlatformIcon` — `Globe` for Truth Social, `X` (aliased as `XIcon`) for Twitter/X
- Filtered state: `opacity-40` on entire Card + gray "Filtered" label + italic filter reason
- New WS card: `animate-in slide-in-from-top-2 fade-in duration-200` via `isNew` prop
- Analyzing state: italic "Analyzing…" text when signal is null/undefined
- Ticker chips: `Badge variant="outline"` per ticker in affected_tickers array

### frontend/src/pages/FeedPage.tsx

- `useQuery(["posts"])` — initial REST load of 50 posts, `staleTime: 30_000`, uses `isPending` (TQ v5 API)
- `usePostFeed()` — live WebSocket posts, `status` for reconnect chip
- `useMemo` merge — live posts at top, REST posts filtered with `liveIds.has(p.id)` to avoid duplicates
- `LoadingSkeletons` — 4 x `h-24` Skeleton cards during `isPending`
- `EmptyState` — `Zap` icon (48px) + "No posts yet" heading + body copy per UI-SPEC copywriting contract
- Reconnect chip — amber `bg-yellow-500/10 text-yellow-400` when `status === "reconnecting"`, muted when "disconnected"
- `ScrollArea` — wraps post list for scroll overflow handling
- Error boundary — `text-destructive` message if REST fetch fails

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Replaced removed `Twitter` lucide-react export with `X as XIcon`**
- **Found during:** Task 1 TypeScript compilation (`npm run build`)
- **Issue:** The plan and UI-SPEC referenced `Twitter` icon from `lucide-react`, but the installed version has removed this export. Build error: `Module '"lucide-react"' has no exported member 'Twitter'`
- **Fix:** Changed import to `import { Globe, X as XIcon } from "lucide-react"` and updated `PlatformIcon` to use `<XIcon>` for twitter platform
- **Files modified:** `frontend/src/components/PostCard.tsx`
- **Commit:** 4e45744

**2. [Rule 1 - Bug] Removed unused `confidence` destructure in `SentimentBadge`**
- **Found during:** Task 1 TypeScript compilation (`npm run build`)
- **Issue:** `SentimentBadge` destructured `confidence` from props but never used it — TypeScript TS6133 error
- **Fix:** Kept `confidence` in the type signature (callers pass it) but removed from destructure — `{ sentiment }` only
- **Files modified:** `frontend/src/components/PostCard.tsx`
- **Commit:** 4e45744

## Known Stubs

None — both PostCard and FeedPage are fully implemented. No placeholder data, no hardcoded empty values flowing to UI.

## Threat Flags

No new threat surface beyond the plan's threat model. Post content is rendered as React text nodes (JSX `{post.content}`), never via `dangerouslySetInnerHTML` — React escapes all text automatically. WebSocket JSON parsing is wrapped in try/catch in `usePostFeed.ts` (implemented in Plan 03).

## Self-Check: PASSED

**Files exist:**
- frontend/src/components/PostCard.tsx: FOUND (opacity-40, bg-green-500/10, bg-red-500/10, animate-in slide-in-from-top-2)
- frontend/src/pages/FeedPage.tsx: FOUND (usePostFeed, queryKey ["posts"], isPending, liveIds.has, ScrollArea)

**Commits exist:**
- fd22ee3: FOUND (Task 1 — PostCard initial)
- 4e45744: FOUND (Task 1 fix — icon alias + unused param)
- 4a4d9ac: FOUND (Task 2 — FeedPage)

**Build:** `npm run build` — PASSED (zero TypeScript errors, 1872 modules transformed)
