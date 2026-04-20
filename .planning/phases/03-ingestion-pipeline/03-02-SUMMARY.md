---
phase: "03-ingestion-pipeline"
plan: "02"
subsystem: ingestion
tags: [truth-social, poller, cursor, dedup, sha256, INGEST-01, INGEST-03]
one_liner: "Truth Social async poller with since-ID cursor, HTML-stripping SHA-256 dedup, SAVEPOINT insert, and graceful 401/403 handling"

dependency_graph:
  requires:
    - trumptrade.core.db.AsyncSessionLocal
    - trumptrade.core.models.Post
    - trumptrade.core.models.AppSettings
    - trumptrade.core.config.get_settings
    - trumptrade.ingestion.filters.apply_filters
    - httpx
  provides:
    - trumptrade.ingestion.truth_social.poll_truth_social
    - trumptrade.ingestion.truth_social._strip_html
    - trumptrade.core.config.Settings.truth_social_token
  affects:
    - trumptrade/ingestion/__init__.py  (Wave 3 will register poll_truth_social as a job)
    - trumptrade/core/config.py         (truth_social_token field added)

tech_stack:
  added: []
  patterns:
    - httpx.AsyncClient with timeout=10.0 for external API calls
    - begin_nested() SAVEPOINT for per-row IntegrityError dedup inside outer session
    - since-ID cursor stored in app_settings (string-encoded Snowflake ID)
    - HTML stripped via re.sub before SHA-256 hash — raw HTML stored for audit
    - empty-string-to-None coercion for optional Bearer Token (token or None)

key_files:
  created:
    - trumptrade/ingestion/truth_social.py
  modified:
    - trumptrade/core/config.py

decisions:
  - "HTML stripped before hashing (not stored hash) — avoids false-new-post on markup changes"
  - "posted_at stored as naive UTC to match SQLite server_default=func.now() behavior"
  - "max_id tracked numerically (int comparison on Snowflake strings) to handle out-of-order IDs"
  - "token or None converts empty config default to no Authorization header"
  - "_set_setting called after session.commit() to prevent cursor advance on rolled-back batch"

metrics:
  duration_seconds: 72
  completed_date: "2026-04-20"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 1
---

# Phase 03 Plan 02: Truth Social Poller — truth_social.py

**Summary:** Truth Social async poller with since-ID cursor, HTML-stripping SHA-256 dedup, SAVEPOINT insert, and graceful 401/403 handling

## What Was Built

Two changes delivering INGEST-01 (Truth Social polling with cursor) and INGEST-03 (SHA-256 dedup):

1. **`trumptrade/ingestion/truth_social.py`** — `poll_truth_social()` async coroutine:
   - Reads `last_truth_post_id` from `app_settings` as the since-ID cursor (None on first run)
   - Calls `_fetch_posts()` — GET to `https://truthsocial.com/api/v1/accounts/{id}/statuses` with `limit=20` and optional `since_id` param
   - `_strip_html()` removes all HTML tags via `re.sub(r'<[^>]+>', '', html)` before hashing
   - SHA-256 of stripped text stored in `content_hash`; raw HTML stored in `content` for audit
   - `apply_filters(text)` classifies each post (from Plan 01 Wave 1 utility)
   - `begin_nested()` SAVEPOINT wraps each `session.add(post)` + `flush()` — `IntegrityError` on duplicate hash silently discarded at DEBUG level
   - 401/403 returns empty list (logs ERROR); 5xx propagates via `raise_for_status()` for APScheduler retry
   - `httpx.AsyncClient(timeout=10.0)` prevents indefinite hang
   - Cursor advanced to max numeric platform_post_id after `session.commit()`

2. **`trumptrade/core/config.py`** — `truth_social_token: str = ""` added to Settings class:
   - Empty default means no Authorization header is sent
   - User sets `TRUTH_SOCIAL_TOKEN` in `.env` if Truth Social tightens access in future

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add truth_social_token to Settings | 5cdb9bf | trumptrade/core/config.py |
| 2 | Create truth_social.py poller | 42ff9f7 | trumptrade/ingestion/truth_social.py |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — truth_social.py is fully implemented. The `truth_social_token` config field is intentionally empty by default (not a stub — it is correct behavior to send no auth header until credentials are needed).

## Threat Flags

All threats from the plan's threat model are addressed:

| Threat ID | Mitigation | Status |
|-----------|------------|--------|
| T-03-04 | `re.sub(r'<[^>]+>', '', html)` strips all tags before hash/filter | Implemented |
| T-03-05 | Only HTTP status code logged — never bearer token or response body | Implemented |
| T-03-06 | SHA-256 collision accepted; DB unique constraint is authoritative | Accepted |
| T-03-07 | `httpx.AsyncClient(timeout=10.0)` prevents event loop block | Implemented |
| T-03-08 | Token read from .env only; never logged | Implemented |

## Self-Check

### Files Exist

- [x] `trumptrade/ingestion/truth_social.py` — FOUND
- [x] `trumptrade/core/config.py` (modified) — FOUND

### Commits Exist

- [x] 5cdb9bf — Task 1 (truth_social_token config field)
- [x] 42ff9f7 — Task 2 (Truth Social poller)

## Self-Check: PASSED
