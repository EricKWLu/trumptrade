from __future__ import annotations

"""Truth Social poller — fetches Trump posts via Truth Social's public Mastodon-compatible API.

No authentication required — the /api/v1/accounts/{id}/statuses endpoint is publicly readable
for accounts with `unauth_visibility: true` (which Trump's account has).

A Chrome-like User-Agent header is required to bypass Cloudflare's basic bot filtering.
"""

import hashlib
import logging
import re
from datetime import datetime, timezone

from curl_cffi.requests import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from trumptrade.core.config import get_settings
from trumptrade.core.db import AsyncSessionLocal
from trumptrade.core.models import AppSettings, Post
from trumptrade.ingestion.filters import apply_filters

logger = logging.getLogger(__name__)

_BASE_URL = "https://truthsocial.com/api/v1/accounts/{account_id}/statuses"
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


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


async def _fetch_statuses(account_id: str, since_id: str | None, limit: int = 20) -> list[dict]:
    """GET /api/v1/accounts/{account_id}/statuses unauthenticated.

    Cloudflare checks both User-Agent AND TLS fingerprint. curl_cffi's
    impersonate="chrome" mimics Chrome's TLS handshake to pass these checks.
    Returns [] on any error (logged); cursor advance is skipped on empty results.
    """
    url = _BASE_URL.format(account_id=account_id)
    params: dict[str, object] = {"limit": limit}
    if since_id:
        params["since_id"] = since_id

    headers = {
        "User-Agent": _USER_AGENT,
        "Accept": "application/json",
    }

    try:
        async with AsyncSession(impersonate="chrome") as session:
            resp = await session.get(url, params=params, headers=headers, timeout=10.0)
        if resp.status_code != 200:
            logger.error(
                "Truth Social fetch failed: status=%d body=%s",
                resp.status_code, resp.text[:200],
            )
            return []
        return resp.json()
    except Exception as exc:
        logger.error("Truth Social fetch error: %s", exc)
        return []


async def poll_truth_social() -> None:
    """Fetch new Trump Truth Social posts and store in the posts table.

    Called every 60 seconds by APScheduler (D-01). Implements:
    - Since-ID cursor for incremental fetch (D-12)
    - HTML strip before hashing (Pitfall 4)
    - SHA-256 content_hash dedup via SAVEPOINT (D-06)
    - Pre-filter via apply_filters() (INGEST-04 — sets is_filtered/filter_reason)
    - Cursor advance to max platform_post_id after successful poll (D-12)
    - Bootstrap on first run: set cursor to latest post ID without ingesting history
    """
    settings = get_settings()
    account_id = settings.truth_social_account_id

    since_id = await _get_setting("last_truth_post_id")

    # Bootstrap: on first run set cursor to latest post and skip history
    if since_id is None:
        latest = await _fetch_statuses(account_id, since_id=None, limit=1)
        if latest:
            latest_id = latest[0]["id"]
            await _set_setting("last_truth_post_id", latest_id)
            logger.info(
                "Truth Social: bootstrapped cursor to %s — skipping historical posts",
                latest_id,
            )
        return

    staleness_minutes = int(await _get_setting("signal_staleness_minutes") or "5")
    statuses = await _fetch_statuses(account_id, since_id=since_id, limit=20)

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
                age_seconds = (
                    datetime.now(timezone.utc).replace(tzinfo=None) - posted_at
                ).total_seconds()
                if age_seconds > staleness_minutes * 60:
                    is_filtered = True
                    filter_reason = "stale_on_ingest"

            account = status.get("account") or {}
            author: str | None = (
                account.get("username") if isinstance(account, dict) else None
            )
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
