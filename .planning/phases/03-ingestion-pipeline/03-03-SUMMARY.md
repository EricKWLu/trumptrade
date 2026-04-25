---
phase: "03-ingestion-pipeline"
plan: "03"
subsystem: ingestion
tags: [twitter, tweepy, run_in_executor, rate-limit, cursor, dedup, sha256, INGEST-02, INGEST-03]
one_liner: "X/Twitter async poller wrapping tweepy in run_in_executor with monthly budget tracking, module-level user_id cache, and SAVEPOINT SHA-256 dedup"

dependency_graph:
  requires:
    - trumptrade.core.db.AsyncSessionLocal
    - trumptrade.core.models.Post
    - trumptrade.core.models.AppSettings
    - trumptrade.core.config.get_settings
    - trumptrade.ingestion.filters.apply_filters
    - tweepy
  provides:
    - trumptrade.ingestion.twitter.poll_twitter
    - trumptrade.ingestion.twitter._fetch_tweets_sync
    - trumptrade.ingestion.twitter._lookup_user_id_sync
  affects:
    - trumptrade/ingestion/__init__.py  (Wave 3 will register poll_twitter as a job)

tech_stack:
  added: []
  patterns:
    - asyncio.get_running_loop().run_in_executor(None, partial(sync_fn, ...)) for sync library isolation
    - Module-level variable cache for stable external ID (Trump's Twitter user_id)
    - begin_nested() SAVEPOINT for per-row IntegrityError dedup inside outer session
    - Since-ID cursor stored in app_settings (string-encoded tweet snowflake ID)
    - Monthly counter with YYYY-MM reset key stored as string int in app_settings
    - wait_on_rate_limit=False on tweepy.Client so TooManyRequests surfaces immediately

key_files:
  created:
    - trumptrade/ingestion/twitter.py
  modified: []

decisions:
  - "Module-level _trump_user_id cache — get_user() called once per process restart, not per poll tick"
  - "wait_on_rate_limit=False — surfaces TooManyRequests immediately; backoff loop would block executor thread"
  - "Budget counter incremented after fetch call (not after tweet inserts) — the HTTP request consumed quota regardless of response content"
  - "posted_at stored as naive UTC to match SQLite server_default=func.now() behavior"
  - "max_id tracked numerically (int comparison on snowflake strings) to handle out-of-order tweet delivery"
  - "bearer_token never logged — only 'not configured' sentinel logged (T-03-10)"

metrics:
  duration_seconds: 77
  completed_date: "2026-04-20"
  tasks_completed: 1
  tasks_total: 1
  files_created: 1
  files_modified: 0
---

# Phase 03 Plan 03: X/Twitter Poller — twitter.py

**Summary:** X/Twitter async poller wrapping tweepy in run_in_executor with monthly budget tracking, module-level user_id cache, and SAVEPOINT SHA-256 dedup

## What Was Built

**`trumptrade/ingestion/twitter.py`** — `poll_twitter()` async coroutine:

- `_lookup_user_id_sync(bearer_token)` — plain sync function that calls `tweepy.Client.get_user(username="realDonaldTrump")` and returns the numeric ID as a string. Result cached in module-level `_trump_user_id` after first success; avoids one extra API call per tick.
- `_fetch_tweets_sync(bearer_token, user_id, since_id)` — plain sync function that calls `client.get_users_tweets(id=..., max_results=10, tweet_fields=["created_at","author_id"], since_id=...)`. Catches `tweepy.errors.TooManyRequests` and logs WARNING, returns `[]` without crashing. Both sync functions safe for `run_in_executor`.
- `poll_twitter()` async coroutine:
  - Checks `x_bearer_token` configured; skips with ERROR log if not
  - Lazy user_id lookup: wraps `_lookup_user_id_sync` in `run_in_executor` once, then caches
  - Reads `last_x_post_id` cursor from `app_settings`
  - Wraps `_fetch_tweets_sync` in `run_in_executor` (tweepy is synchronous — never called directly in async context)
  - Calls `_update_request_counter()` after each API fetch (budget consumed regardless of tweet count)
  - For each tweet: SHA-256 hash of `tweet.text`, `apply_filters()` classification, SAVEPOINT insert
  - `tweet.created_at` stored as naive UTC; raises detailed error log if None (missing tweet_fields)
  - `tweet.author_id` (int from tweepy) cast to `str` for `Post.author` column
  - Cursor `last_x_post_id` advanced to max numeric tweet ID after `session.commit()`
- `_update_request_counter()` — increments `x_requests_this_month` counter in app_settings; resets to 1 on new calendar month (keyed by `x_requests_reset_month` "YYYY-MM"); logs WARNING when count reaches 8,000 (80% of 10,000 Basic tier cap)

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create twitter.py — X/Twitter poller | f521c11 | trumptrade/ingestion/twitter.py |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — twitter.py is fully implemented with no placeholders.

## Threat Flags

All threats from the plan's threat model are addressed:

| Threat ID | Mitigation | Status |
|-----------|------------|--------|
| T-03-09 | ALL tweepy calls in _lookup_user_id_sync and _fetch_tweets_sync wrapped in run_in_executor | Implemented |
| T-03-10 | bearer_token never logged; only tweet IDs and counts appear in log lines | Implemented |
| T-03-11 | WARNING logged at x_requests_this_month >= 8,000; TooManyRequests caught and returns [] | Implemented |
| T-03-12 | tweet.text stored verbatim (plain text, no HTML from Twitter API); display layer responsible for escaping | Accepted |

## Self-Check

### Files Exist

- [x] `trumptrade/ingestion/twitter.py` — FOUND

### Commits Exist

- [x] f521c11 — Task 1 (X/Twitter poller)

## Self-Check: PASSED
