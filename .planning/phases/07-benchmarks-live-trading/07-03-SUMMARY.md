---
phase: 07-benchmarks-live-trading
plan: "03"
subsystem: frontend
tags: [react, recharts, benchmarks, tanstack-query, shadcn, typescript]

# Dependency graph
requires:
  - phase: 07-02
    provides: GET /benchmarks returning {snapshots:[BenchmarkPoint,...]}; POST /trading/set-mode

provides:
  - BenchmarkPoint and SetModeResponse TypeScript types in frontend/src/lib/api.ts
  - api.benchmarks() calling GET /benchmarks, unwrapping r.snapshots
  - api.setMode() calling POST /trading/set-mode with {mode, confirmed: true}
  - /benchmarks route in router.tsx mapping to BenchmarksPage
  - BenchmarksPage with inline BenchmarkChart (4-series Recharts LineChart)
  - Loading skeleton, empty state, error state for BenchmarksPage
  - shadcn Dialog component at frontend/src/components/ui/dialog.tsx

affects:
  - 07-04 (AppShell augmentations, LiveModeModal, SettingsPage TradingModeSection — use api.setMode() and dialog.tsx)

# Tech tracking
tech-stack:
  added:
    - recharts@^3.8.1 (LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine)
    - react-is@^19.2.5 (recharts 3.x peer dependency)
    - shadcn dialog component (frontend/src/components/ui/dialog.tsx)
  patterns:
    - Recharts LineChart with 4 series and nullable data (connectNulls=false)
    - useQuery with staleTime=refetchInterval=300_000 for low-frequency data
    - Inline sub-component pattern (BenchmarkChart inside BenchmarksPage)
    - SVG styling via inline style props (Tailwind does not apply to SVG)

key-files:
  created:
    - frontend/src/pages/BenchmarksPage.tsx
    - frontend/src/components/ui/dialog.tsx
  modified:
    - frontend/package.json (recharts + react-is added)
    - frontend/package-lock.json
    - frontend/src/lib/api.ts (BenchmarkPoint, SetModeResponse, benchmarks(), setMode())
    - frontend/src/router.tsx (/benchmarks route + BenchmarksPage import)

key-decisions:
  - "BenchmarkChart is inline in BenchmarksPage (no separate file) — single-use component, UI-SPEC Section 2d"
  - "connectNulls=false on all 4 Line components — backend returns null for portfolios not yet started; gaps render correctly"
  - "staleTime=refetchInterval=300_000 — benchmark data only updates at market close (4:01pm ET), polling more often wastes bandwidth"
  - "XAxis tickFormatter slices MM-DD from YYYY-MM-DD — keeps axis labels compact with many data points"

# Metrics
duration: ~2min
completed: 2026-04-23
---

# Phase 7 Plan 03: Frontend Benchmarks Page Summary

**Recharts LineChart BenchmarksPage with 4 series (bot/SPY/QQQ/random), loading skeleton, empty state, error state; BenchmarkPoint/SetModeResponse types and api.benchmarks()/api.setMode() wired to backend; /benchmarks route added to router**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-04-23T02:12:54Z
- **Completed:** 2026-04-23T02:15:09Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- `npm install recharts react-is` — recharts@^3.8.1 and react-is@^19.2.5 added to frontend/package.json
- `npx shadcn add dialog` — `frontend/src/components/ui/dialog.tsx` created (needed by plan 07-04 LiveModeModal)
- `frontend/src/lib/api.ts` — `BenchmarkPoint` interface (date + nullable bot/spy/qqq/random) and `SetModeResponse` interface added; `api.benchmarks()` unwraps `r.snapshots` from GET /benchmarks; `api.setMode()` posts `{mode, confirmed: true}` to POST /trading/set-mode
- `frontend/src/router.tsx` — import BenchmarksPage + `{ path: "benchmarks", element: <BenchmarksPage /> }` route between portfolio and settings
- `frontend/src/pages/BenchmarksPage.tsx` — full page created with inline `BenchmarkChart` component, `LoadingSkeletons`, `EmptyState` sub-components; all 4 Recharts `Line` series with correct colors per UI-SPEC; Y-axis label "Return since start (%)"; dashed `ReferenceLine` at y=0; Legend below; copywriting contract text exact match; TypeScript 0 errors

## Task Commits

Each task was committed atomically:

1. **Task 1: deps + api.ts + router.tsx** — `93fa56f` (feat)
2. **Task 2: BenchmarksPage.tsx** — `f84d8bb` (feat)

## Files Created/Modified

- `frontend/package.json` — recharts + react-is dependencies added
- `frontend/package-lock.json` — lockfile updated
- `frontend/src/components/ui/dialog.tsx` — shadcn Dialog component (created by npx shadcn add dialog)
- `frontend/src/lib/api.ts` — BenchmarkPoint, SetModeResponse types; benchmarks(), setMode() methods
- `frontend/src/router.tsx` — /benchmarks route + BenchmarksPage import
- `frontend/src/pages/BenchmarksPage.tsx` — new page with BenchmarkChart inline component

## Decisions Made

- `connectNulls={false}` on all 4 Line components — backend may return `null` for portfolios not yet started; chart renders gaps correctly rather than connecting across nulls
- `staleTime` and `refetchInterval` both set to 300_000ms (5 min) — benchmark data only updates daily at market close; aggressive polling is wasteful
- BenchmarkChart is an inline sub-component of BenchmarksPage (not a separate file) — single-use component per UI-SPEC Section 2d note
- XAxis `tickFormatter` slices characters 5+ (`v.slice(5)`) to show MM-DD from YYYY-MM-DD — keeps axis readable at any data density with `minTickGap={40}`

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — `api.benchmarks()` calls real GET /benchmarks endpoint (implemented in 07-02); `api.setMode()` calls real POST /trading/set-mode endpoint (implemented in 07-02).

## Threat Model Coverage

- T-07-07 (Tampering — setMode always sends confirmed: true): frontend enforces typed phrase before calling setMode(); server double-validates confirmed=True — frontend implementation aligns with plan design
- T-07-08 (Information Disclosure — recharts/react-is from npm): official npm packages, no auth tokens in chart data; accepted per plan threat register

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| frontend/src/pages/BenchmarksPage.tsx exists | FOUND |
| frontend/src/components/ui/dialog.tsx exists | FOUND |
| recharts in package.json | FOUND (^3.8.1) |
| react-is in package.json | FOUND (^19.2.5) |
| BenchmarkPoint in api.ts | FOUND |
| SetModeResponse in api.ts | FOUND |
| benchmarks() in api.ts | FOUND |
| setMode() in api.ts | FOUND |
| /benchmarks route in router.tsx | FOUND |
| BenchmarksPage import in router.tsx | FOUND |
| 4 Line series with correct colors | FOUND (bot #3b82f6, SPY #22c55e, QQQ #a855f7, random #f59e0b) |
| ReferenceLine at y=0 dashed | FOUND |
| Legend verticalAlign="bottom" | FOUND |
| Y-axis "Return since start (%)" label | FOUND |
| Empty state "No benchmark data yet" | FOUND |
| Loading skeleton + error state | FOUND |
| TypeScript 0 errors (tsc --noEmit --skipLibCheck) | PASSED |
| Commit 93fa56f exists | FOUND |
| Commit f84d8bb exists | FOUND |
