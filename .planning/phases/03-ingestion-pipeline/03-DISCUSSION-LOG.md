# Phase 3: Ingestion Pipeline - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-20
**Phase:** 03-ingestion-pipeline
**Areas discussed:** Polling cadence

---

## Polling Cadence

| Option | Description | Selected |
|--------|-------------|----------|
| Truth Social: 60 seconds | Fast, no rate limit risk on Mastodon endpoint | ✓ |
| Truth Social: 5 minutes | Conservative, up to 5-min lag | |
| Truth Social: 30 seconds | Aggressive, unnecessary | |

**User's choice:** 60 seconds for Truth Social

| Option | Description | Selected |
|--------|-------------|----------|
| X/Twitter: 5 minutes | ~8,640 req/month, stays under 10K cap | ✓ |
| X/Twitter: 15 minutes | Very conservative, ~2,880 req/month | |
| X/Twitter: 2 minutes | Exceeds Basic tier cap | |

**User's choice:** 5 minutes for X/Twitter

| Option | Description | Selected |
|--------|-------------|----------|
| Log + app_settings counter | Increment counter in DB, warn at 80% | ✓ |
| Log only | Derive budget from log parsing | |
| New rate_limit_ledger table | Most accurate but schema complexity | |

**User's choice:** Log + app_settings counter for X rate-limit tracking

| Option | Description | Selected |
|--------|-------------|----------|
| Log error, retry next interval | Simple, no hammering down endpoint | ✓ |
| Exponential backoff | More complex, better for transient failures | |
| Alert immediately, skip poll | Treats any failure as monitoring event | |

**User's choice:** Log error, retry on next scheduled tick

---

## Claude's Discretion

Pre-filter criteria (short threshold, repost detection, keyword list), heartbeat alert
storage (log-only), and daytime window (9am–5pm ET) were not explicitly discussed —
defaults applied from INGEST-01/INGEST-04 requirements and codebase constraints.

## Deferred Ideas

None.
