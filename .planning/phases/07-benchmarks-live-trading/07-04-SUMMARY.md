---
phase: 07-benchmarks-live-trading
plan: "04"
subsystem: frontend
tags: [react, shadcn, dialog, live-trading, tanstack-query, typescript]

# Dependency graph
requires:
  - phase: 07-03
    provides: api.setMode(), dialog.tsx, /benchmarks route

provides:
  - LiveModeModal.tsx: two-direction typed confirmation modal (ENABLE LIVE TRADING / ENABLE PAPER TRADING)
  - AppShell.tsx: Benchmarks nav item (LineChart icon, /benchmarks) + conditional LIVE banner
  - SettingsPage.tsx: TradingModeSection card with badge + switch button + LiveModeModal wired

affects:
  - All pages (LIVE banner rendered in AppShell main area when mode=live)
  - Settings page (Trading Mode section added as third card)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Typed phrase confirmation pattern (disabled confirm until exact case-sensitive match)
    - TanStack Query deduplication (same queryKey ["portfolio-mode"] used in AppShell + TradingModeBadge + TradingModeSection — single network call)
    - base-ui Dialog with controlled open/onOpenChange

key-files:
  created:
    - frontend/src/components/LiveModeModal.tsx
  modified:
    - frontend/src/components/AppShell.tsx (LineChart import, Benchmarks nav item, LIVE banner, mode query)
    - frontend/src/pages/SettingsPage.tsx (LiveModeModal import, TradingModeSection component)

key-decisions:
  - "TanStack Query deduplicates portfolio-mode fetch — AppShell, TradingModeBadge, and TradingModeSection all use queryKey=['portfolio-mode']; only one network call is made"
  - "base-ui Dialog onOpenChange receives (open, eventDetails) — modal reset (clear input, clear error) happens in handleOpenChange(false)"
  - "LiveModeModal resets input and error on close regardless of trigger (backdrop click, X button, or dismiss button)"

# Metrics
duration: ~2min
completed: 2026-04-23
---

# Phase 7 Plan 04: LiveModeModal + AppShell LIVE Banner + SettingsPage Trading Mode Summary

**Two-direction typed confirmation modal (ENABLE LIVE TRADING / ENABLE PAPER TRADING), AppShell Benchmarks nav and LIVE banner, SettingsPage Trading Mode section — completing TRADE-02 live trading unlock UI**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-04-23T02:17:13Z
- **Completed:** 2026-04-23T02:18:50Z
- **Tasks:** 1 auto + 1 checkpoint (auto-approved)
- **Files modified:** 3

## Accomplishments

- `frontend/src/components/LiveModeModal.tsx` — created: two-direction shadcn Dialog modal; `LIVE_PHRASE="ENABLE LIVE TRADING"` and `PAPER_PHRASE="ENABLE PAPER TRADING"` constants; exact case-sensitive match (`input === targetPhrase`); Confirm button `disabled={!isMatch || modeMutation.isPending}`; `variant="destructive"` for paper→live, `variant="default"` for live→paper; `api.setMode()` mutation with `queryClient.invalidateQueries(["portfolio-mode"])` on success; error text "Failed to switch mode. Try again."; dismiss buttons "Keep PAPER mode" / "Keep LIVE mode"; warning text about real money (paper→live only)
- `frontend/src/components/AppShell.tsx` — patched: `LineChart` added to lucide-react import; Benchmarks nav item `{ to: "/benchmarks", icon: LineChart, label: "Benchmarks" }` between Portfolio and Settings; `useQuery(["portfolio-mode"])` in AppShell function body; LIVE banner `<div className="bg-red-500/10 border-b border-red-500/30 ...">LIVE TRADING ACTIVE — real money at risk</div>` rendered conditionally before `<Outlet />`
- `frontend/src/pages/SettingsPage.tsx` — patched: `import { LiveModeModal }` added; `TradingModeSection` component with `useQuery(["portfolio-mode"])`, PAPER/LIVE badge, switch button, `LiveModeModal` wired; section added as third card after RiskControlsSection

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | LiveModeModal + AppShell + SettingsPage | 7001a68 | LiveModeModal.tsx (new), AppShell.tsx, SettingsPage.tsx |
| 2 | Checkpoint: human-verify | (auto-approved in auto mode) | — |

## Deviations from Plan

None — plan executed exactly as written. Auto mode auto-approved the human-verify checkpoint.

## Known Stubs

None — `api.setMode()` calls real POST /trading/set-mode (implemented in 07-02); `api.portfolio()` calls real GET /portfolio (implemented in prior phases).

## Threat Model Coverage

- T-07-09 (Spoofing — bypass typed phrase): `disabled={!isMatch}` prevents API call before exact phrase match; server double-validates `confirmed=True`
- T-07-10 (Tampering — AppShell reads wrong mode): 60s refetch interval; worst-case stale banner for 60s — accepted per plan
- T-07-11 (Information Disclosure — LIVE banner always visible): intended behavior per D-11

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| frontend/src/components/LiveModeModal.tsx exists | FOUND |
| ENABLE LIVE TRADING phrase constant | FOUND |
| ENABLE PAPER TRADING phrase constant | FOUND |
| Keep PAPER mode dismiss button | FOUND |
| Keep LIVE mode dismiss button | FOUND |
| destructive variant for paper→live | FOUND |
| disabled={!isMatch} on Confirm | FOUND |
| api.setMode() call | FOUND |
| invalidateQueries(["portfolio-mode"]) | FOUND |
| LineChart in AppShell imports | FOUND |
| /benchmarks nav item | FOUND |
| LIVE TRADING ACTIVE banner text | FOUND |
| mode === "live" conditional banner | FOUND |
| LiveModeModal in SettingsPage | FOUND (import + JSX) |
| Trading Mode section heading | FOUND |
| Switch to LIVE Trading / Switch to PAPER Trading buttons | FOUND |
| TypeScript 0 errors (tsc --noEmit --skipLibCheck) | PASSED |
| Commit 7001a68 exists | FOUND |
