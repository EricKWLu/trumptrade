# Phase 3: Ingestion Pipeline - Research

**Researched:** 2026-04-20
**Domain:** Social media polling (Truth Social Mastodon API + Twitter/X v2 API), APScheduler async job registration, SQLAlchemy async deduplication
**Confidence:** MEDIUM-HIGH (API mechanics verified; Truth Social auth requirement flagged as partially uncertain)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Truth Social poller runs every 60 seconds. Mastodon-compatible endpoint, no documented rate limit.
- **D-02:** X/Twitter poller runs every 5 minutes (~8,640 requests/month against ~10,000/month Basic cap; ~1,360 buffer).
- **D-03:** Both pollers register jobs via `scheduler.add_job()` on the module-level `scheduler` imported from `trumptrade.core.app`. Jobs registered at app startup by calling `register_ingestion_jobs(scheduler)` from inside `create_app()`.
- **D-04:** After each X poll, increment `x_requests_this_month` in `app_settings` (string-encoded int, reset on new calendar month). Log WARNING at 80% cap (8,000 requests). No new table needed.
- **D-05:** On network error or non-200: log ERROR, let APScheduler retry on next tick. No exponential backoff, no immediate alert.
- **D-06:** SHA-256 hash of raw post content string stored in `posts.content_hash` (unique-indexed). On insert, catch `IntegrityError` — discard silently, log DEBUG. No cross-platform join needed.
- **D-07:** Pre-filter post if: `len(content) < 100` → `"too_short"`, starts with `"RT @"` (case-insensitive) → `"pure_repost"`, no financial keyword match → `"no_financial_keywords"`. Set `is_filtered=True`, first-matching `filter_reason`.
- **D-08:** Financial keyword list hardcoded in Phase 3 (not `keyword_rules` DB table — that's Phase 4). See list in CONTEXT.md §D-08.
- **D-09:** Heartbeat check runs every 15 minutes between 9am–5pm US Eastern. If zero new Truth Social posts stored in last 30 minutes during daytime window, log WARNING: `"HEARTBEAT: no Truth Social posts in last 30 minutes"`. Log-only in Phase 3.
- **D-10:** Daytime window 9am–5pm US Eastern using pytz (already installed). Heartbeat job skips silently outside window.
- **D-11:** Pollers write directly to `posts` table via `AsyncSessionLocal`. No queue, no intermediary.
- **D-12:** Use `platform_post_id` as cursor. Store last-seen ID per platform in `app_settings` (`last_truth_post_id`, `last_x_post_id`). On first run (empty), fetch most recent N posts to initialize.

### Claude's Discretion
- Initial fetch count on first run (suggested: 20 recent posts)
- Exact Truth Social Mastodon API parameters (`limit`, `since_id`)
- Tweepy client setup (OAuth 2.0 Bearer Token for read-only)
- Module structure inside `trumptrade/ingestion/` (e.g., `truth_social.py`, `twitter.py`, `filters.py`, `poller.py`)

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INGEST-01 | System polls Truth Social for new Trump posts on a schedule with a heartbeat alert when zero posts are seen during a daytime window | Truth Social Mastodon API endpoint + pytz ET window + APScheduler interval job |
| INGEST-02 | System polls Trump's X/Twitter account for new posts with rate-limit budget tracking and retry on limit headers | tweepy.Client get_users_tweets + x-rate-limit-remaining header + app_settings counter |
| INGEST-03 | System deduplicates posts across platforms using SHA-256 content hash before any signal is routed | hashlib.sha256 + IntegrityError catch pattern or SQLite on_conflict_do_nothing |
| INGEST-04 | System pre-filters posts for relevance (skips short posts, pure reposts, and posts with no financial keywords) before calling LLM | Pure Python filter logic in filters.py; sets is_filtered + filter_reason fields |
</phase_requirements>

---

## Summary

Phase 3 builds a dual-platform polling system that ingests Trump's posts from Truth Social (via Mastodon-compatible JSON API using httpx) and X/Twitter (via tweepy v4 Client with Bearer Token), deduplicates them via SHA-256 content hash, pre-filters low-value posts, and writes survivors to the `posts` table. A heartbeat job running every 15 minutes on the APScheduler checks for silence during market hours.

The key risks are: (1) Truth Social may require authentication for the accounts statuses endpoint — empirical evidence is contradictory (see §Authentication Risk below); (2) tweepy's `get_users_tweets` requires `tweet_fields=["created_at"]` to be explicitly requested or timestamps will be missing from responses; (3) SQLAlchemy async sessions go into an invalid state after IntegrityError without proper savepoint handling.

**Primary recommendation:** Implement Truth Social polling with a graceful 401/403 fallback that logs a clear error and skips — not crashes — so the heartbeat catches the silence. Use `async with session.begin_nested()` savepoint pattern for IntegrityError handling to keep the session usable across multiple inserts in a single poll tick.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Truth Social polling | Backend (in-process scheduler) | — | APScheduler coroutine; no external worker needed |
| X/Twitter polling | Backend (in-process scheduler) | — | APScheduler coroutine; tweepy is sync, must be run in executor |
| SHA-256 deduplication | Backend (service layer) | — | Pure CPU work before any DB insert |
| Pre-filter logic | Backend (service layer) | — | Stateless keyword/length check; no DB read needed |
| DB insert (posts table) | Backend (service layer) | DB | AsyncSessionLocal writes to SQLite |
| Rate-limit budget tracking | Backend (service layer) | DB | app_settings key/value; read-then-increment per poll |
| Heartbeat alert | Backend (in-process scheduler) | DB | Reads posts table for count; logs WARNING |
| Cursor management | Backend (service layer) | DB | app_settings keys last_truth_post_id / last_x_post_id |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | 0.28.1 | Async HTTP GET for Truth Social Mastodon API | Async-native; already installed; project rule bans requests |
| tweepy | 4.16.0 | Twitter API v2 Client for X polling | Official Python Twitter client; Bearer Token read-only support |
| apscheduler | 3.11.2 | Interval job scheduling (60s + 5min + 15min) | Already running in create_app(); AsyncIOScheduler |
| pytz | 2026.1.post1 | US/Eastern timezone for heartbeat window | Already installed; used in Phase 2 |
| sqlalchemy | 2.0.49 | Async ORM for posts table insert + app_settings read/write | Already in use; async session pattern established |
| hashlib | stdlib | SHA-256 content hashing | No install needed |

[VERIFIED: pip show tweepy httpx apscheduler pytz sqlalchemy — all confirmed installed at stated versions]

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| sqlalchemy.dialects.sqlite.insert | stdlib with sqlalchemy | `on_conflict_do_nothing()` for dedup without exception catch | Alternative to IntegrityError catch; cleaner for batch inserts |
| datetime, zoneinfo | stdlib | Aware datetime comparison for heartbeat window | zoneinfo is modern alternative to pytz for Python 3.9+ |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| catch IntegrityError | `on_conflict_do_nothing()` SQLite dialect | Dialect-specific but cleaner; avoids savepoint complexity |
| pytz US/Eastern | zoneinfo.ZoneInfo("America/New_York") | No install needed (Python 3.9+); pytz already present so either works |

**Installation:** No new packages needed — all dependencies already installed.

---

## Architecture Patterns

### System Architecture Diagram

```
[APScheduler - every 60s]          [APScheduler - every 5min]    [APScheduler - every 15min]
         |                                    |                              |
         v                                    v                              v
[poll_truth_social()]           [poll_twitter()]                 [check_heartbeat()]
         |                                    |                              |
    httpx.AsyncClient                   tweepy.Client              Query posts WHERE
    GET /api/v1/accounts/               (sync in executor)         platform='truth_social'
    {id}/statuses                       get_users_tweets()         AND created_at > now-30min
    ?since_id=&limit=20                 (id, since_id=, max_results=10)
         |                                    |                              |
         v                                    v                    Count == 0 AND
    JSON array of                       Response.data              9am <= ET hour < 17?
    Mastodon Status objects             list of Tweet objects              |
         |                                    |                      log.WARNING
         v                                    v                   "HEARTBEAT: no Truth..."
    for each status:                 for each tweet:
         |                                    |
         v                                    v
    SHA-256(content)              SHA-256(content)
         |                                    |
         v                                    v
    [filters.apply_filters()]     [filters.apply_filters()]
         |                                    |
         v                                    v
    async with session.begin_nested():
         session.add(Post(...))
         try: await session.flush()
         except IntegrityError: rollback savepoint, log DEBUG
         |
         v
    update app_settings:
    last_truth_post_id / last_x_post_id = max(platform_post_id seen)
```

### Recommended Project Structure
```
trumptrade/ingestion/
├── __init__.py          # exports register_ingestion_jobs()
├── truth_social.py      # poll_truth_social() coroutine
├── twitter.py           # poll_twitter() coroutine (sync tweepy run in executor)
├── filters.py           # apply_filters(content) -> (is_filtered, filter_reason | None)
└── heartbeat.py         # check_heartbeat() coroutine
```

### Pattern 1: Truth Social Mastodon API Call
**What:** httpx async GET with optional since_id parameter  
**When to use:** Every 60-second poll tick

```python
# Source: https://docs.joinmastodon.org/methods/accounts/ [CITED]
import httpx

async def fetch_truth_social_posts(account_id: str, since_id: str | None) -> list[dict]:
    params: dict = {"limit": 20}
    if since_id:
        params["since_id"] = since_id
    url = f"https://truthsocial.com/api/v1/accounts/{account_id}/statuses"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, params=params)
    if resp.status_code in (401, 403):
        # Auth required — log error, heartbeat will catch silence
        logger.error("Truth Social returned %s — may need credentials", resp.status_code)
        return []
    resp.raise_for_status()   # propagate 5xx to APScheduler retry
    return resp.json()         # list of Mastodon Status dicts
```

**Key response fields from Mastodon Status object:**
- `id` → `platform_post_id`
- `content` → raw HTML; strip with e.g. `re.sub(r'<[^>]+>', '', content)` for hash+filter
- `created_at` → ISO 8601 string (parse with `datetime.fromisoformat`)
- `account.username` → `author`

### Pattern 2: tweepy Client for X/Twitter (sync wrapped in executor)
**What:** tweepy.Client is synchronous; must be run in asyncio executor to avoid blocking event loop  
**When to use:** Every 5-minute poll tick

```python
# Source: https://docs.tweepy.org/en/stable/client.html [CITED]
import tweepy
import asyncio

def _fetch_twitter_sync(bearer_token: str, user_id: str, since_id: str | None) -> list:
    client = tweepy.Client(bearer_token=bearer_token, wait_on_rate_limit=False)
    kwargs: dict = {
        "id": user_id,
        "max_results": 10,
        "tweet_fields": ["created_at", "author_id", "text"],
    }
    if since_id:
        kwargs["since_id"] = since_id
    response = client.get_users_tweets(**kwargs)
    return response.data or []  # data is None when no new tweets

async def poll_twitter(bearer_token: str, user_id: str, since_id: str | None) -> list:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _fetch_twitter_sync, bearer_token, user_id, since_id
    )
```

**CRITICAL:** `tweet_fields=["created_at"]` MUST be explicitly requested. Without it, only `id` and `text` are returned. [VERIFIED: tweepy docs discussion #1756]

**Trump's X user_id:** `25073877` (numeric ID for @realDonaldTrump) — look up once at startup via `client.get_user(username="realDonaldTrump")` and cache. [ASSUMED — verify at runtime]

### Pattern 3: APScheduler Async Job Registration (deduplication-safe)
**What:** Add interval jobs to already-running AsyncIOScheduler with stable IDs  
**When to use:** Inside `register_ingestion_jobs()` called from `create_app()`

```python
# Source: https://apscheduler.readthedocs.io/en/3.x/userguide.html [CITED]
from apscheduler.schedulers.asyncio import AsyncIOScheduler

def register_ingestion_jobs(scheduler: AsyncIOScheduler) -> None:
    scheduler.add_job(
        poll_truth_social,
        trigger="interval",
        seconds=60,
        id="ingestion_truth_social",    # stable ID prevents duplicate on hot reload
        replace_existing=True,           # idempotent — safe to call multiple times
        misfire_grace_time=30,           # allow up to 30s late start before skipping
        coalesce=True,                   # if multiple misfires, run once not N times
        max_instances=1,                 # never overlap concurrent runs
    )
    scheduler.add_job(
        poll_twitter,
        trigger="interval",
        minutes=5,
        id="ingestion_twitter",
        replace_existing=True,
        misfire_grace_time=60,
        coalesce=True,
        max_instances=1,
    )
    scheduler.add_job(
        check_heartbeat,
        trigger="interval",
        minutes=15,
        id="ingestion_heartbeat",
        replace_existing=True,
        misfire_grace_time=120,
        coalesce=True,
        max_instances=1,
    )
```

`replace_existing=True` is the deduplication guard for hot-reload. Without a stable `id`, APScheduler creates duplicate jobs on every restart. [VERIFIED: APScheduler docs + github issue #559]

### Pattern 4: SQLAlchemy Async Deduplication with SAVEPOINT
**What:** Insert Post, catch IntegrityError on content_hash unique constraint without killing the session  
**When to use:** After SHA-256 hash computed, before committing to posts table

```python
# Source: https://docs.sqlalchemy.org/en/20/orm/session_transaction.html [CITED]
from sqlalchemy.exc import IntegrityError

async def save_post(session: AsyncSession, post: Post) -> bool:
    """Returns True if inserted, False if duplicate."""
    try:
        async with session.begin_nested():  # SAVEPOINT — preserves outer transaction
            session.add(post)
            await session.flush()
        return True
    except IntegrityError:
        # Unique constraint on content_hash triggered — duplicate post
        logger.debug("Duplicate post skipped: hash=%s", post.content_hash)
        return False
```

**Why SAVEPOINT matters:** In SQLite, an IntegrityError without a savepoint invalidates the entire transaction. `begin_nested()` creates a SAVEPOINT so only the failing insert is rolled back; the outer session remains usable for the next post in the same batch. [VERIFIED: SQLAlchemy docs discussion #8282]

**Alternative (no exception handling):**
```python
# Source: SQLAlchemy 2.0 SQLite dialect [CITED]
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

stmt = sqlite_insert(Post).values(**post_data).on_conflict_do_nothing(
    index_elements=["content_hash"]
)
await session.execute(stmt)
```
This is cleaner for batch inserts but returns no "was inserted" signal.

### Pattern 5: pytz Heartbeat Window Check
**What:** Check if current time is within 9am–5pm US Eastern  
**When to use:** At the start of `check_heartbeat()` to skip silently outside hours

```python
# Source: https://pythonhosted.org/pytz/ [CITED]
import pytz
from datetime import datetime, timezone

def is_market_hours(start_hour: int = 9, end_hour: int = 17) -> bool:
    eastern = pytz.timezone("US/Eastern")
    now_et = datetime.now(timezone.utc).astimezone(eastern)
    return start_hour <= now_et.hour < end_hour
```

**Note:** Use `datetime.now(timezone.utc).astimezone(eastern)` NOT `eastern.localize(datetime.now())`. The `localize()` form is for naive datetimes only and is bug-prone. [CITED: pytz docs]

### Pattern 6: app_settings Read/Write for Cursors and Counters
**What:** Read/write string-encoded values in app_settings table  
**When to use:** Cursor update after poll, monthly counter increment

```python
# [ASSUMED] — pattern follows established Phase 1/2 conventions
from sqlalchemy import select
from trumptrade.core.models import AppSettings

async def get_setting(session: AsyncSession, key: str) -> str | None:
    result = await session.execute(
        select(AppSettings).where(AppSettings.key == key)
    )
    row = result.scalar_one_or_none()
    return row.value if row else None

async def set_setting(session: AsyncSession, key: str, value: str) -> None:
    result = await session.execute(
        select(AppSettings).where(AppSettings.key == key)
    )
    row = result.scalar_one_or_none()
    if row:
        row.value = value
    else:
        session.add(AppSettings(key=key, value=value))
```

All app_settings values are string-encoded; cast after read (e.g., `int(value)` for counters).

### Anti-Patterns to Avoid
- **Blocking event loop with tweepy:** `tweepy.Client` is synchronous. Never call it directly in an `async def` without `run_in_executor`. It will block uvicorn's event loop. [VERIFIED: tweepy is not an async library]
- **Bare `session.rollback()` on IntegrityError:** Rolling back the full session after an IntegrityError discards all uncommitted work from the same poll batch. Use `begin_nested()` SAVEPOINT instead.
- **Missing `tweet_fields=["created_at"]`:** tweepy v2 Client returns only `id` and `text` by default. `posted_at` will be `None` and the Post model will fail to insert.
- **Not setting `replace_existing=True`:** Every app restart without this creates a new job copy, leading to N concurrent pollers after N restarts.
- **Comparing naive datetimes in heartbeat:** The 30-minute lookback query must compare UTC datetimes consistently; `posts.created_at` uses `server_default=func.now()` (SQLite stores naive UTC). Compare with `datetime.now(timezone.utc).replace(tzinfo=None)` when querying.
- **Stripping HTML from Truth Social content AFTER hashing:** Hash the raw content string; strip HTML for filter/display. Cross-platform dedup on raw content ensures consistency.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP client | Custom requests wrapper | `httpx.AsyncClient` | Async-native, timeout, redirects, keep-alive built in |
| Twitter API calls | Raw HTTP to x.com | `tweepy.Client` | Rate limit headers, pagination, auth handled |
| Unique constraint dedup | SELECT-then-INSERT race | IntegrityError catch + SAVEPOINT or `on_conflict_do_nothing` | DB-level guarantee; SELECT-then-INSERT has race condition |
| Timezone math | Manual UTC offset | `pytz` / `zoneinfo` | DST transitions handled automatically |
| Job scheduling | asyncio.create_task in loop | APScheduler with interval trigger | Missed job handling, coalesce, max_instances built in |

**Key insight:** The database unique constraint is the authoritative dedup gate, not application-layer pre-checks. Let the DB reject duplicates and handle the exception.

---

## Common Pitfalls

### Pitfall 1: Truth Social Authentication Requirement
**What goes wrong:** `GET /api/v1/accounts/{id}/statuses` returns 401 or 403 without credentials.
**Why it happens:** Truth Social has tightened access over time. As of mid-2025, public accounts (including Trump's) appear accessible without auth, but this is undocumented and may change. [MEDIUM confidence — contradictory reports]
**How to avoid:** Handle 401/403 gracefully — return empty list, log ERROR with status code. The heartbeat will surface the silence within 30 minutes. Add a `TRUTHSOCIAL_TOKEN` env var to config for future auth if needed.
**Warning signs:** Consistent 401/403 in logs with empty post stream; heartbeat WARNING firing every 15 minutes during market hours.

### Pitfall 2: tweepy Not Async — Event Loop Blocking
**What goes wrong:** `tweepy.Client.get_users_tweets()` blocks the asyncio event loop for the duration of the HTTP call (potentially 1-5 seconds).
**Why it happens:** tweepy v4 is a synchronous library. It has no `async` support.
**How to avoid:** Wrap every tweepy call in `await loop.run_in_executor(None, sync_fn, *args)`. Keep the sync function pure (no async calls inside).
**Warning signs:** uvicorn request handling slows during Twitter poll intervals; scheduler jobs start backing up.

### Pitfall 3: Missing tweet_fields — Silent None for posted_at
**What goes wrong:** `Post.posted_at` is set to `None`, causing a NOT NULL constraint failure on insert.
**Why it happens:** Twitter API v2 requires fields to be explicitly opted into. Without `tweet_fields=["created_at"]`, the response `Tweet` object has `.created_at = None`.
**How to avoid:** Always pass `tweet_fields=["created_at", "author_id"]` to `get_users_tweets`.
**Warning signs:** `IntegrityError` on `posted_at NOT NULL`, not on `content_hash` unique.

### Pitfall 4: Truth Social Content is HTML
**What goes wrong:** SHA-256 hash of raw HTML varies if platform adds/removes markup around identical text, causing false "new post" detections.
**Why it happens:** Mastodon's `content` field contains HTML like `<p>TEXT</p>` and `<a href=...>` links. Minor HTML changes re-hash as different.
**How to avoid:** Strip HTML tags before hashing AND before filtering. Use `re.sub(r'<[^>]+>', '', content)` or `html.unescape()` after stripping. Hash the stripped, whitespace-normalized text. Store raw HTML in `posts.content` but hash the clean version.
**Warning signs:** Same text appearing multiple times in posts table with different content_hash values.

### Pitfall 5: First-Run Cursor Initialization
**What goes wrong:** On first run, `last_truth_post_id` and `last_x_post_id` are empty in app_settings. Without a cursor, fetching without `since_id` returns the most recent N posts — which is correct for initialization. But if the poller then stores all N and sets the cursor, subsequent polls only fetch posts newer than the cursor. This is the desired behavior.
**Why it happens:** Not a bug but needs explicit handling: on first run, fetch with `limit=20` (no since_id), store all 20, set cursor to the max `platform_post_id` seen.
**How to avoid:** Check `last_truth_post_id` / `last_x_post_id` at poll start. If empty string or absent, omit `since_id` param (fetch most recent 20). After any successful poll that returns results, update cursor to `max(platform_post_id)`.
**Warning signs:** Cursor never advancing; same 20 posts being re-fetched every minute.

### Pitfall 6: SQLite Text ID Ordering for since_id
**What goes wrong:** Truth Social uses Snowflake-style numeric IDs stored as strings. `since_id=last_id` works correctly because Mastodon API compares IDs numerically, not lexicographically. But if stored in app_settings as a string and accidentally compared in Python with `>` operator, lexicographic comparison can break ordering (e.g., "9" > "10").
**Why it happens:** Python string comparison is lexicographic.
**How to avoid:** Never compare IDs in Python. Pass them directly to the API as strings. Let the API handle ordering. [ASSUMED — Mastodon spec guarantees numeric comparison on since_id]

### Pitfall 7: Monthly Counter Reset Logic
**What goes wrong:** `x_requests_this_month` counter never resets, eventually logging false "80% cap" warnings.
**Why it happens:** Reset logic checks if current calendar month differs from month of last reset; if that check uses the wrong timezone (UTC vs ET), the reset can fire at midnight UTC instead of midnight ET.
**How to avoid:** Store `x_requests_reset_month` as `YYYY-MM` string alongside the counter. Compare against `datetime.now(timezone.utc).strftime("%Y-%m")` for consistency.

---

## Code Examples

### Full Poll Cycle: Truth Social (condensed)
```python
# [ASSUMED pattern — adapts established project conventions]
from __future__ import annotations
import hashlib, re, logging
from datetime import datetime, timezone, timedelta
import httpx
from sqlalchemy.exc import IntegrityError
from trumptrade.core.db import AsyncSessionLocal
from trumptrade.core.models import Post
from trumptrade.ingestion.filters import apply_filters

logger = logging.getLogger(__name__)

async def poll_truth_social() -> None:
    async with AsyncSessionLocal() as session:
        since_id = await get_setting(session, "last_truth_post_id")
        posts_json = await fetch_truth_social_posts(ACCOUNT_ID, since_id)
        max_id = since_id
        for status in posts_json:
            raw_html = status["content"]
            text = re.sub(r'<[^>]+>', '', raw_html).strip()
            content_hash = hashlib.sha256(text.encode()).hexdigest()
            is_filtered, filter_reason = apply_filters(text)
            posted_at = datetime.fromisoformat(status["created_at"].replace("Z", "+00:00"))
            post = Post(
                platform="truth_social",
                platform_post_id=status["id"],
                content=raw_html,
                content_hash=content_hash,
                author=status.get("account", {}).get("username"),
                posted_at=posted_at,
                is_filtered=is_filtered,
                filter_reason=filter_reason,
            )
            try:
                async with session.begin_nested():
                    session.add(post)
                    await session.flush()
                if max_id is None or int(status["id"]) > int(max_id):
                    max_id = status["id"]
            except IntegrityError:
                logger.debug("Duplicate skipped: %s", content_hash)
        if max_id and max_id != since_id:
            await set_setting(session, "last_truth_post_id", max_id)
        await session.commit()
```

### Filter Logic (filters.py)
```python
# [ASSUMED — implements D-07/D-08]
from __future__ import annotations

FINANCIAL_KEYWORDS = {
    "tariffs", "trade", "tax", "stock", "market", "economy", "economic",
    "deal", "sanction", "china", "invest", "dollar", "rate", "inflation",
    "bank", "energy", "oil", "gas", "crypto", "bitcoin", "fed", "reserve",
    "deficit", "debt", "budget", "jobs", "employment", "manufacturing",
    "import", "export",
}

def apply_filters(text: str) -> tuple[bool, str | None]:
    """Return (is_filtered, filter_reason). reason is None if not filtered."""
    if len(text) < 100:
        return True, "too_short"
    if text.upper().startswith("RT @"):
        return True, "pure_repost"
    words = set(text.lower().split())
    if not words & FINANCIAL_KEYWORDS:
        return True, "no_financial_keywords"
    return False, None
```

---

## Authentication Risk: Truth Social

**Status:** MEDIUM confidence — contradictory evidence

Evidence FOR public access (no auth needed):
- Mastodon API spec: public accounts' statuses are publicly readable [CITED: docs.joinmastodon.org]
- Multiple reports that `https://truthsocial.com/api/v1/accounts/107780257626128497/statuses` is callable without cookies from incognito browsers [MEDIUM — WebSearch, unverified firsthand]

Evidence AGAINST (auth required):
- As of 2025, reports that authentication is being required for some access patterns [MEDIUM — WebSearch]
- truthbrush library (Stanford) uses credential-based auth, suggesting auth is needed in practice [CITED: github.com/stanfordio/truthbrush]

**Recommendation for planner:**
1. Implement httpx call without auth headers first (attempt unauthenticated)
2. Handle 401/403 with clear log message suggesting credentials may be needed
3. Add `truth_social_token` to `Settings` (empty default) in `config.py` so it can be populated if needed without code changes
4. If auth is needed: Truth Social OAuth flow requires client credentials (username + password → `/oauth/token`) — out of scope for Phase 3 implementation but config slot enables Phase 3.5 auth addition

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| tweepy v3 (OAuth 1.0 API v1.1) | tweepy v4 Client (Bearer Token, API v2) | 2021 | v1.1 endpoints deprecated; v2 required for user timeline |
| `requests` library | `httpx.AsyncClient` | Project rule | requests blocks asyncio event loop |
| Direct IntegrityError catch without savepoint | `begin_nested()` SAVEPOINT | SQLAlchemy 2.0 recommendation | Session remains usable after error |
| `pytz.localize()` with naive datetimes | `datetime.now(utc).astimezone(eastern)` | Current best practice | localize() is error-prone on DST boundaries |

---

## Open Questions

1. **Truth Social authentication requirement**
   - What we know: API is Mastodon-compatible; Trump's account is public; auth status contradictory
   - What's unclear: Whether unauthenticated requests succeed reliably in 2025/2026
   - Recommendation: Implement unauthenticated first, add config slot for token, handle 401/403 gracefully

2. **X/Twitter user_id for @realDonaldTrump**
   - What we know: `get_user(username="realDonaldTrump")` returns the numeric user ID
   - What's unclear: Whether the account is still `@realDonaldTrump` or has changed
   - Recommendation: Look up at startup via `get_user(username=...)`, cache result in memory; log ERROR if lookup fails and skip Twitter polling

3. **tweepy wait_on_rate_limit behavior with max_instances=1**
   - What we know: `wait_on_rate_limit=False` raises `tweepy.errors.TooManyRequests` on limit
   - What's unclear: Whether the 5-minute interval naturally stays under the per-15-minute limits
   - Recommendation: Use `wait_on_rate_limit=False` and catch `tweepy.errors.TooManyRequests`; log WARNING and return empty list (consistent with D-05)

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| httpx | Truth Social polling | ✓ | 0.28.1 | — |
| tweepy | X/Twitter polling | ✓ | 4.16.0 | — |
| apscheduler | Job scheduling | ✓ | 3.11.2 | — |
| pytz | Heartbeat ET window | ✓ | 2026.1.post1 | zoneinfo (stdlib Python 3.9+) |
| sqlalchemy + aiosqlite | DB writes | ✓ | 2.0.49 | — |
| X/Twitter Basic API access | INGEST-02 | UNKNOWN | — | Cannot poll without valid credentials |
| Truth Social unauthenticated | INGEST-01 | UNCERTAIN | — | Optional token via config |

**Missing dependencies with no fallback:**
- X/Twitter API credentials (`x_bearer_token` in .env) — must be configured before polling works. If missing, tweepy raises 401; poller should catch and log ERROR.

**Missing dependencies with fallback:**
- Truth Social auth: unauthenticated access attempted first; `truth_social_token` config slot as fallback if 401 received.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Trump's X numeric user_id is `25073877` | Code Examples | Twitter poll targets wrong user; look up at startup |
| A2 | Truth Social unauthenticated access works for public accounts in 2026 | Authentication Risk | Polling silently fails; heartbeat fires every 15 min |
| A3 | `app_settings` keys `last_truth_post_id`, `last_x_post_id`, `x_requests_this_month` are not yet seeded in DB | Standard Stack | First-run GET returns None; code must handle None cursor |
| A4 | Mastodon `since_id` comparison is numeric, not lexicographic | Pitfall 6 | Cursor logic correct; no risk if we never compare in Python |
| A5 | `get_setting` / `set_setting` helper does not yet exist — needs to be created | Code Examples | Would need to inline the ORM pattern everywhere |

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | No user auth in this phase |
| V3 Session Management | No | No user sessions |
| V4 Access Control | No | No user-facing endpoints |
| V5 Input Validation | Yes | Strip HTML from Truth Social content before storing; never eval/exec content |
| V6 Cryptography | No | SHA-256 is for dedup fingerprinting, not security crypto |

### Known Threat Patterns for Ingestion Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malicious HTML/script in post content | Tampering | `re.sub(r'<[^>]+>', '', content)` on display text; raw HTML stored but never rendered server-side |
| Credential leak in logs | Information Disclosure | Never log bearer_token or x_api_secret; log only truncated status info |
| Runaway API spend via rapid retry | Denial of Service (self) | D-05: no retry, no backoff; APScheduler coalesce=True prevents burst |

---

## Sources

### Primary (HIGH confidence)
- [VERIFIED: pip installed packages] — tweepy 4.16.0, httpx 0.28.1, apscheduler 3.11.2, pytz 2026.1, sqlalchemy 2.0.49
- [docs.joinmastodon.org/methods/accounts/](https://docs.joinmastodon.org/methods/accounts/) — GET /api/v1/accounts/:id/statuses parameters (since_id, limit, auth)
- [docs.tweepy.org/en/stable/client.html](https://docs.tweepy.org/en/stable/client.html) — get_users_tweets, get_user, tweet_fields
- [apscheduler.readthedocs.io/en/3.x/userguide.html](https://apscheduler.readthedocs.io/en/3.x/userguide.html) — AsyncIOScheduler add_job, replace_existing, id
- [docs.sqlalchemy.org/en/20/orm/session_transaction.html](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html) — begin_nested() SAVEPOINT pattern
- [docs.x.com/x-api/fundamentals/rate-limits](https://docs.x.com/x-api/fundamentals/rate-limits) — GET /2/users/:id/tweets: 10,000/15min app-level

### Secondary (MEDIUM confidence)
- [pythonhosted.org/pytz/](https://pythonhosted.org/pytz/) — pytz US/Eastern, astimezone pattern
- APScheduler GitHub issue #559 — confirmed replace_existing=True prevents duplicate jobs
- tweepy GitHub discussion #1756 — confirmed tweet_fields required for created_at

### Tertiary (LOW confidence)
- WebSearch results on Truth Social authentication status (contradictory; marked UNCERTAIN in Environment Availability)
- Trump numeric X user_id `25073877` (training knowledge; must verify at runtime)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages verified installed at stated versions
- Truth Social API mechanics: MEDIUM — Mastodon spec verified; Truth Social auth status uncertain
- tweepy/X API mechanics: HIGH — official docs accessed; tweet_fields requirement verified
- APScheduler patterns: HIGH — official docs + issue tracker verified
- SQLAlchemy dedup pattern: HIGH — official docs verified
- Pitfalls: MEDIUM-HIGH — most verified via official sources or issue trackers

**Research date:** 2026-04-20
**Valid until:** 2026-05-20 (30 days; Truth Social auth status may change sooner)
