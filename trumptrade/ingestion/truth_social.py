from __future__ import annotations

"""Truth Social poller — fetches Trump posts via truthbrush (INGEST-01, INGEST-03)."""

import asyncio
import hashlib
import logging
import re
from datetime import datetime, timezone
from functools import partial

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from trumptrade.core.config import get_settings
from trumptrade.core.db import AsyncSessionLocal
from trumptrade.core.models import AppSettings, Post
from trumptrade.ingestion.filters import apply_filters

logger = logging.getLogger(__name__)


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", "", html)
    return " ".join(text.split())


async def _get_setting(key: str) -> str | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AppSettings.value).where(AppSettings.key == key)
        )
        return result.scalar_one_or_none()


async def _set_setting(key: str, value: str) -> None:
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


def _pull_statuses_sync(
    username: str | None,
    password: str | None,
    token: str | None,
    account_username: str,
    since_id: str | None,
) -> list[dict]:
    """Sync wrapper around truthbrush — runs in a thread via run_in_executor."""
    try:
        from truthbrush import Api  # type: ignore[import]
    except ImportError:
        logger.error("truthbrush not installed — run: pip install truthbrush")
        return []

    try:
        api = Api(username=username, password=password, token=token)
        statuses = list(api.pull_statuses(username=account_username, since_id=since_id))
        return statuses
    except Exception as exc:
        logger.error("truthbrush pull_statuses failed: %s", exc)
        return []


def _get_latest_post_id_sync(
    username: str | None,
    password: str | None,
    token: str | None,
    account_username: str,
) -> str | None:
    """Fetch only the most recent post ID — used to bootstrap the cursor on first run.

    Consumes just the first item from the generator (one API page) rather than
    paginating through all history, avoiding bulk-fetch rate limiting.
    """
    try:
        from truthbrush import Api  # type: ignore[import]
    except ImportError:
        return None

    try:
        api = Api(username=username, password=password, token=token)
        first = next(iter(api.pull_statuses(username=account_username)), None)
        return first["id"] if first else None
    except Exception as exc:
        logger.error("truthbrush bootstrap failed: %s", exc)
        return None


async def poll_truth_social() -> None:
    """Fetch new Trump Truth Social posts and store in the posts table.

    Called every 60 seconds by APScheduler (D-01). Implements:
    - Since-ID cursor for incremental fetch (D-12)
    - HTML strip before hashing (Pitfall 4)
    - SHA-256 content_hash dedup via SAVEPOINT (D-06)
    - Pre-filter via apply_filters() (INGEST-04 — sets is_filtered/filter_reason)
    - Cursor advance to max platform_post_id after successful poll (D-12)
    """
    settings = get_settings()
    account_username = settings.truth_social_account_username
    ts_username = settings.truth_social_username
    ts_password = settings.truth_social_password
    ts_token = settings.truth_social_token or None

    since_id = await _get_setting("last_truth_post_id")

    # Bootstrap: on first run set cursor to latest post ID and skip history entirely
    if since_id is None:
        loop = asyncio.get_event_loop()
        latest_id = await loop.run_in_executor(
            None,
            partial(_get_latest_post_id_sync, ts_username, ts_password, ts_token, account_username),
        )
        if latest_id:
            await _set_setting("last_truth_post_id", latest_id)
            logger.info("Truth Social: bootstrapped cursor to %s — skipping historical posts", latest_id)
        return

    staleness_minutes = int(await _get_setting("signal_staleness_minutes") or "5")

    loop = asyncio.get_event_loop()
    statuses = await loop.run_in_executor(
        None,
        partial(
            _pull_statuses_sync,
            ts_username,
            ts_password,
            ts_token,
            account_username,
            since_id,
        ),
    )

    if not statuses:
        return

    max_id: str | None = since_id
    inserted = 0
    skipped = 0

    async with AsyncSessionLocal() as session:
        for status in statuses:
            raw_html: str = status.get("content", "")
            text = _strip_html(raw_html)
            content_hash = hashlib.sha256(text.encode()).hexdigest()
            is_filtered, filter_reason = apply_filters(text)

            created_at_str: str = status.get("created_at", "")
            try:
                posted_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                posted_at = posted_at.astimezone(timezone.utc).replace(tzinfo=None)
            except (ValueError, AttributeError):
                logger.error("Truth Social: could not parse created_at=%r", created_at_str)
                continue

            if not is_filtered:
                age_seconds = (datetime.now(timezone.utc).replace(tzinfo=None) - posted_at).total_seconds()
                if age_seconds > staleness_minutes * 60:
                    is_filtered = True
                    filter_reason = "stale_on_ingest"

            account = status.get("account") or {}
            author: str | None = account.get("username") if isinstance(account, dict) else None
            platform_post_id: str = status["id"]

            post = Post(
                platform="truth_social",
                platform_post_id=platform_post_id,
                content=raw_html,
                content_hash=content_hash,
                author=author,
                posted_at=posted_at,
                is_filtered=is_filtered,
                filter_reason=filter_reason,
            )

            try:
                async with session.begin_nested():
                    session.add(post)
                    await session.flush()
                inserted += 1
                if max_id is None or int(platform_post_id) > int(max_id):
                    max_id = platform_post_id
            except IntegrityError:
                skipped += 1
                logger.debug("Truth Social: duplicate skipped hash=%s", content_hash)

        await session.commit()

    logger.info(
        "Truth Social poll complete: inserted=%d skipped=%d since_id=%s",
        inserted, skipped, since_id,
    )

    if max_id and max_id != since_id:
        await _set_setting("last_truth_post_id", max_id)
