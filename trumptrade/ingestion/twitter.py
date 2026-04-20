from __future__ import annotations

"""X/Twitter poller — fetches Trump tweets via tweepy v4 API v2 (INGEST-02, INGEST-03).

tweepy.Client is a synchronous library. ALL calls are wrapped in run_in_executor to avoid
blocking the asyncio/uvicorn event loop.
"""

import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from functools import partial

import tweepy
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from trumptrade.core.config import get_settings
from trumptrade.core.db import AsyncSessionLocal
from trumptrade.core.models import AppSettings, Post
from trumptrade.ingestion.filters import apply_filters

logger = logging.getLogger(__name__)

# Monthly request cap and warning threshold (per D-04)
_MONTHLY_CAP = 10_000
_WARNING_THRESHOLD = 8_000  # 80% of cap

# Module-level cache for Trump's numeric X user_id.
# Populated on first successful poll. Avoids repeated get_user() calls.
_trump_user_id: str | None = None


# ── Sync functions (safe to pass to run_in_executor) ──────────────────────────

def _lookup_user_id_sync(bearer_token: str) -> str | None:
    """Look up @realDonaldTrump numeric user_id via tweepy. Returns None on failure."""
    try:
        client = tweepy.Client(bearer_token=bearer_token, wait_on_rate_limit=False)
        response = client.get_user(username="realDonaldTrump")
        if response.data is None:
            logger.error("Twitter: get_user('realDonaldTrump') returned no data")
            return None
        return str(response.data.id)
    except Exception as exc:
        logger.error("Twitter: user_id lookup failed: %s", exc)
        return None


def _fetch_tweets_sync(
    bearer_token: str,
    user_id: str,
    since_id: str | None,
) -> list:
    """Fetch new tweets from Trump's X account. Returns list of tweepy.Tweet objects.

    CRITICAL: tweet_fields=["created_at", "author_id"] MUST be explicitly requested.
    Without created_at, tweet.created_at is None and Post insert fails NOT NULL on posted_at.
    (RESEARCH.md Pitfall 3)
    """
    client = tweepy.Client(bearer_token=bearer_token, wait_on_rate_limit=False)
    kwargs: dict = {
        "id": user_id,
        "max_results": 10,
        "tweet_fields": ["created_at", "author_id"],
    }
    if since_id:
        kwargs["since_id"] = since_id
    try:
        response = client.get_users_tweets(**kwargs)
        return response.data or []  # response.data is None when no new tweets
    except tweepy.errors.TooManyRequests:
        logger.warning("Twitter: rate limit hit — will retry on next poll tick (D-05)")
        return []
    except Exception as exc:
        logger.error("Twitter: get_users_tweets failed: %s", exc)
        return []


# ── Async helpers ─────────────────────────────────────────────────────────────

async def _get_setting(key: str) -> str | None:
    """Read a single app_settings value. Returns None if key does not exist."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AppSettings.value).where(AppSettings.key == key)
        )
        return result.scalar_one_or_none()


async def _set_setting(key: str, value: str) -> None:
    """Upsert a single app_settings value."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AppSettings).where(AppSettings.key == key)
        )
        row = result.scalar_one_or_none()
        if row is not None:
            row.value = value
        else:
            session.add(AppSettings(key=key, value=value))
        await session.commit()


async def _update_request_counter() -> None:
    """Increment x_requests_this_month. Reset if month changed. Warn at 80% cap.

    Per D-04: counter stored as string int in app_settings.
    Reset key: x_requests_reset_month stored as "YYYY-MM" (UTC).
    Warn when counter exceeds 8,000 (80% of 10,000/month Basic cap).
    """
    current_month = datetime.now(timezone.utc).strftime("%Y-%m")

    reset_month = await _get_setting("x_requests_reset_month")
    count_raw = await _get_setting("x_requests_this_month")

    # Reset counter if entering a new calendar month
    if reset_month != current_month:
        await _set_setting("x_requests_reset_month", current_month)
        await _set_setting("x_requests_this_month", "1")
        logger.info("Twitter: monthly request counter reset for %s", current_month)
        return

    count = int(count_raw) + 1 if count_raw else 1
    await _set_setting("x_requests_this_month", str(count))

    if count >= _WARNING_THRESHOLD:
        logger.warning(
            "Twitter: x_requests_this_month=%d — approaching monthly cap of %d",
            count,
            _MONTHLY_CAP,
        )


# ── Main poller coroutine ─────────────────────────────────────────────────────

async def poll_twitter() -> None:
    """Fetch new Trump tweets and store in the posts table.

    Called every 5 minutes by APScheduler (D-02). Implements:
    - Lazy user_id lookup via module-level cache (avoids repeated get_user() calls)
    - Since-ID cursor for incremental fetch (D-12)
    - tweepy wrapped in run_in_executor (tweepy is synchronous — Pitfall 2)
    - tweet_fields=["created_at", "author_id"] explicitly requested (Pitfall 3)
    - SHA-256 content_hash dedup via SAVEPOINT (D-06)
    - Pre-filter via apply_filters() (sets is_filtered/filter_reason)
    - Monthly request budget tracking (D-04)
    """
    global _trump_user_id

    settings = get_settings()
    bearer_token = settings.x_bearer_token

    if not bearer_token:
        logger.error("Twitter: x_bearer_token not configured — skipping poll")
        return

    # Lazy user_id lookup — cached in module-level variable after first success
    if _trump_user_id is None:
        loop = asyncio.get_running_loop()
        _trump_user_id = await loop.run_in_executor(
            None, partial(_lookup_user_id_sync, bearer_token)
        )
        if _trump_user_id is None:
            logger.error("Twitter: could not resolve Trump user_id — skipping poll")
            return

    since_id = await _get_setting("last_x_post_id")  # None on first run

    # Fetch tweets — sync call wrapped in executor (Pitfall 2)
    loop = asyncio.get_running_loop()
    tweets: list = await loop.run_in_executor(
        None,
        partial(_fetch_tweets_sync, bearer_token, _trump_user_id, since_id),
    )

    # Increment monthly request counter regardless of whether tweets were returned
    # (the API call was made, consuming budget)
    await _update_request_counter()

    if not tweets:
        return  # No new tweets or rate limit hit (already logged)

    max_id: str | None = since_id
    inserted = 0
    skipped = 0

    async with AsyncSessionLocal() as session:
        for tweet in tweets:
            text: str = tweet.text
            content_hash = hashlib.sha256(text.encode()).hexdigest()
            is_filtered, filter_reason = apply_filters(text)

            # tweet.created_at is a timezone-aware datetime from tweepy
            # Store as naive UTC to match SQLite server_default=func.now() behavior
            if tweet.created_at is None:
                logger.error(
                    "Twitter: tweet %s has no created_at — missing tweet_fields?", tweet.id
                )
                continue
            posted_at = tweet.created_at.astimezone(timezone.utc).replace(tzinfo=None)

            tweet_id = str(tweet.id)
            author = str(tweet.author_id) if tweet.author_id is not None else None

            post = Post(
                platform="twitter",
                platform_post_id=tweet_id,
                content=text,
                content_hash=content_hash,
                author=author,
                posted_at=posted_at,
                is_filtered=is_filtered,
                filter_reason=filter_reason,
            )

            try:
                async with session.begin_nested():  # SAVEPOINT — keeps outer session alive
                    session.add(post)
                    await session.flush()
                inserted += 1
                # Track max ID (numeric comparison — string > would be lexicographic)
                if max_id is None or int(tweet_id) > int(max_id):
                    max_id = tweet_id
            except IntegrityError:
                skipped += 1
                logger.debug("Twitter: duplicate skipped hash=%s", content_hash)

        await session.commit()

    logger.info(
        "Twitter poll complete: inserted=%d skipped=%d since_id=%s",
        inserted, skipped, since_id,
    )

    # Advance cursor only if we saw new tweets (D-12)
    if max_id and max_id != since_id:
        await _set_setting("last_x_post_id", max_id)
