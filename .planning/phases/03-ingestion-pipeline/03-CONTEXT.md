# Phase 3: Ingestion Pipeline - Context

**Gathered:** 2026-04-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Poll Truth Social and X/Twitter for new Trump posts on a schedule, deduplicate posts across
platforms via SHA-256 hash, pre-filter low-value posts, and store the result in the `posts`
table with `is_filtered` / `filter_reason` flags. Trigger a heartbeat alert when no posts
are seen during a daytime window. No LLM analysis in this phase — posts flow to the `posts`
table only; Phase 4 picks them up from there.

</domain>

<decisions>
## Implementation Decisions

### Polling Cadence
- **D-01:** Truth Social poller runs every **60 seconds**. The Mastodon-compatible endpoint
  (`/api/v1/accounts/:id/statuses`) has no documented rate limit — polling every minute is safe
  and keeps post-to-pipeline lag under 1 minute.
- **D-02:** X/Twitter poller runs every **5 minutes** (~8,640 requests/month against the
  ~10,000/month Basic tier cap). This leaves ~1,360 requests/month buffer for retries and
  manual calls.
- **D-03:** Both pollers register jobs via `scheduler.add_job()` on the module-level
  `scheduler` instance imported from `trumptrade.core.app`. Jobs are registered at app
  startup by calling a `register_ingestion_jobs(scheduler)` function from the ingestion
  package, invoked inside `create_app()`.

### X/Twitter Rate-Limit Budget Tracking (INGEST-02)
- **D-04:** After each X poll, increment `x_requests_this_month` counter in `app_settings`
  (string-encoded integer, reset to 0 on the first poll of a new calendar month). Log a
  WARNING when usage crosses 80% of the monthly cap (8,000 requests). No new table needed.

### Poll Failure Handling
- **D-05:** On network error or non-200 response from either platform: log the error at ERROR
  level and let APScheduler retry on the next scheduled tick. No exponential backoff, no
  immediate alert. Repeated failures will surface via the heartbeat alert (zero posts seen).

### Deduplication (INGEST-03)
- **D-06:** SHA-256 hash of the raw post `content` string. Hash stored in `posts.content_hash`
  (already unique-indexed in schema). On insert, catch `IntegrityError` on the unique constraint
  — discard silently and log at DEBUG level. No cross-platform join needed; the unique
  constraint does the work.

### Pre-Filter Criteria (INGEST-04)
- **D-07:** A post is filtered if ANY of the following are true (sets `is_filtered=True`,
  `filter_reason` to first matching reason):
  1. `len(content) < 100` characters → `filter_reason = "too_short"`
  2. Content starts with `"RT @"` (case-insensitive) → `filter_reason = "pure_repost"`
  3. No word in content matches the hardcoded financial keyword list →
     `filter_reason = "no_financial_keywords"`
- **D-08:** Financial keyword list is hardcoded in Phase 3 (not the `keyword_rules` DB table,
  which Phase 4 populates). Starting list: tariffs, trade, tax, stock, market, economy,
  economic, deal, sanction, china, invest, dollar, rate, inflation, bank, energy, oil, gas,
  crypto, bitcoin, crypto, fed, reserve, deficit, debt, budget, jobs, employment, manufacturing,
  import, export. The `keyword_rules` table is the Phase 4 concern.

### Heartbeat Alert (INGEST-01)
- **D-09:** Heartbeat check runs every 15 minutes between 9am–5pm US Eastern time
  (configurable via `app_settings` keys `heartbeat_start_hour` and `heartbeat_end_hour`,
  defaulting to 9 and 17 in ET). If zero new Truth Social posts have been stored in the
  last 30 minutes during the daytime window, log a WARNING with message
  `"HEARTBEAT: no Truth Social posts in last 30 minutes"`. Phase 6 dashboard can surface
  this by reading recent logs or a future alerts table — for Phase 3, log-only is sufficient.
- **D-10:** Daytime window: **9am–5pm US Eastern** (`pytz` is already in dependencies from
  Phase 2). The heartbeat job skips silently outside this window.

### Data Flow
- **D-11:** Pollers write directly to the `posts` table via `AsyncSessionLocal`. No queue,
  no intermediary — posts land in DB immediately on receipt. Phase 4's analyzer reads
  unanalyzed, non-filtered posts from the same table.
- **D-12:** Use `platform_post_id` (already in schema) as the "since ID" cursor to avoid
  re-fetching old posts. Store the last-seen ID per platform in `app_settings`
  (`last_truth_post_id`, `last_x_post_id`). On first run these are empty — fetch the most
  recent N posts to initialize.

### Claude's Discretion
- Initial fetch count on first run (suggested: 20 recent posts to initialize the cursor)
- Exact truth social Mastodon API parameters (`limit`, `since_id`)
- Tweepy client setup (OAuth 2.0 Bearer Token for read-only access)
- Module structure inside `trumptrade/ingestion/` (e.g., `truth_social.py`, `twitter.py`,
  `filters.py`, `poller.py`)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — INGEST-01 through INGEST-04 (full text)
- `.planning/ROADMAP.md` §Phase 3 — success criteria SC1–SC4

### Existing Code (read before implementing)
- `trumptrade/core/models.py` — `Post` model (fields: platform, platform_post_id,
  content, content_hash, author, posted_at, is_filtered, filter_reason)
- `trumptrade/core/db.py` — `AsyncSessionLocal` for service-layer DB writes
- `trumptrade/core/config.py` — `x_api_key`, `x_api_secret`, `x_bearer_token`,
  `truth_social_account_id` (already defined, read from .env)
- `trumptrade/core/app.py` — `scheduler` module-level instance; Phase 3 registers jobs by
  calling `register_ingestion_jobs(scheduler)` inside `create_app()`
- `trumptrade/ingestion/__init__.py` — currently empty stub; this is the package to build

### Stack
- Truth Social: `httpx` async GET to
  `https://truthsocial.com/api/v1/accounts/{truth_social_account_id}/statuses`
  with `?since_id=` param for incremental fetch
- X/Twitter: `tweepy` with Bearer Token auth (`tweepy.Client(bearer_token=...)`)
  — use `get_users_tweets(user_id=..., since_id=..., max_results=10)`
- `pytz` (already installed) for Eastern timezone heartbeat window
- `apscheduler` `AsyncIOScheduler` (already running) for job scheduling

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `trumptrade/core/db.py` `AsyncSessionLocal` — same pattern as executor; use
  `async with AsyncSessionLocal() as session:` inside poller coroutines
- `trumptrade/core/config.py` `get_settings()` — provides all credential fields needed
- `trumptrade/core/app.py` `scheduler` — already running; just add jobs to it
- `pytz` — already installed (Phase 2 dependency); use for ET timezone conversion

### Established Patterns
- `from __future__ import annotations` as first line in every file
- New domain packages go in `trumptrade/{domain}/` with an `__init__.py`
- Integration into `create_app()` via local import to avoid circular imports
- `AsyncSessionLocal` for service layer (not `Depends(get_db)` which is for route handlers)
- All app_settings reads/writes are string-encoded; cast to target type after fetch

### Integration Points
- `trumptrade/core/app.py` `create_app()` — call `register_ingestion_jobs(scheduler)` here
  (local import inside `create_app()` to avoid circular imports)
- `posts` table — insert new rows; catch `IntegrityError` on `content_hash` for dedup
- `app_settings` table — read/write `last_truth_post_id`, `last_x_post_id`,
  `x_requests_this_month`, `heartbeat_start_hour`, `heartbeat_end_hour`

</code_context>

<specifics>
## Specific Ideas

- The Truth Social account ID is already defaulted in config (`"107780257626128497"`) —
  no hardcoding needed in the poller
- Keep pollers thin: fetch → dedup check → filter → insert. No business logic in the
  poller itself; filtering lives in a separate `filters.py`

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 03-ingestion-pipeline*
*Context gathered: 2026-04-20*
