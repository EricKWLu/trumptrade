from __future__ import annotations

"""Truth Social poller — fetches Trump posts via Mastodon-compatible API (INGEST-01, INGEST-03)."""

import hashlib
import logging
import re
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from trumptrade.core.config import get_settings
from trumptrade.core.db import AsyncSessionLocal
from trumptrade.core.models import AppSettings, Post
from trumptrade.ingestion.filters import apply_filters

logger = logging.getLogger(__name__)

_BASE_URL = "https://truthsocial.com/api/v1/accounts/{account_id}/statuses"
_OAUTH_TOKEN_URL = "https://truthsocial.com/oauth/token"
_APPS_URL = "https://truthsocial.com/api/v1/apps"

# In-process token cache — refreshed automatically on 401/403
_cached_token: str | None = None


async def _login() -> str | None:
    """Obtain a fresh bearer token via Mastodon OAuth password grant.

    Registers a one-off app to get client credentials, then exchanges
    username+password for an access token. Returns None if credentials
    are missing or the request fails.
    """
    settings = get_settings()
    username = settings.truth_social_username
    password = settings.truth_social_password
    if not username or not password:
        return None

    async with httpx.AsyncClient(timeout=15.0) as client:
        # Step 1: register app → get client_id + client_secret
        try:
            app_resp = await client.post(_APPS_URL, data={
                "client_name": "trumptrade",
                "redirect_uris": "urn:ietf:wg:oauth:2.0:oob",
                "scopes": "read",
            })
            app_resp.raise_for_status()
            app_data = app_resp.json()
            client_id = app_data["client_id"]
            client_secret = app_data["client_secret"]
        except Exception as exc:
            logger.error("Truth Social app registration failed: %s", exc)
            return None

        # Step 2: password grant → access_token
        try:
            token_resp = await client.post(_OAUTH_TOKEN_URL, data={
                "grant_type": "password",
                "client_id": client_id,
                "client_secret": client_secret,
                "username": username,
                "password": password,
                "scope": "read",
            })
            token_resp.raise_for_status()
            token = token_resp.json().get("access_token")
            if token:
                logger.info("Truth Social: obtained fresh access token via login")
            return token
        except Exception as exc:
            logger.error("Truth Social login failed: %s", exc)
            return None


def _strip_html(html: str) -> str:
    """Strip HTML tags and unescape HTML entities from Mastodon content.

    Per RESEARCH.md Pitfall 4: hash the stripped text, not raw HTML, to avoid
    false-new-post detections when the platform changes markup around identical text.
    """
    text = re.sub(r"<[^>]+>", "", html)
    # Collapse whitespace and strip leading/trailing
    return " ".join(text.split())


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


async def _fetch_posts(account_id: str, since_id: str | None, token: str | None) -> list[dict]:
    """GET /api/v1/accounts/{account_id}/statuses from Truth Social.

    On 401/403: attempts auto-login once using username/password, then retries.
    On 5xx: raise_for_status() propagates to APScheduler for next-tick retry.
    """
    global _cached_token

    params: dict[str, object] = {"limit": 20}
    if since_id:
        params["since_id"] = since_id

    url = _BASE_URL.format(account_id=account_id)

    async def _do_get(t: str | None) -> httpx.Response:
        headers = {"Authorization": f"Bearer {t}"} if t else {}
        async with httpx.AsyncClient(timeout=10.0) as client:
            return await client.get(url, params=params, headers=headers)

    try:
        resp = await _do_get(token)
    except httpx.RequestError as exc:
        logger.error("Truth Social network error: %s", exc)
        return []

    if resp.status_code in (401, 403):
        logger.warning("Truth Social %s — attempting auto-login", resp.status_code)
        fresh = await _login()
        if not fresh:
            logger.error("Truth Social auto-login failed — set TRUTH_SOCIAL_USERNAME/PASSWORD in .env")
            return []
        _cached_token = fresh
        try:
            resp = await _do_get(fresh)
        except httpx.RequestError as exc:
            logger.error("Truth Social network error after login: %s", exc)
            return []
        if resp.status_code in (401, 403):
            logger.error("Truth Social still %s after fresh login — credentials may be wrong", resp.status_code)
            return []

    resp.raise_for_status()
    return resp.json()


async def poll_truth_social() -> None:
    """Fetch new Trump Truth Social posts and store in the posts table.

    Called every 60 seconds by APScheduler (D-01). Implements:
    - Since-ID cursor for incremental fetch (D-12)
    - HTML strip before hashing (Pitfall 4)
    - SHA-256 content_hash dedup via SAVEPOINT (D-06)
    - Pre-filter via apply_filters() (INGEST-04 — sets is_filtered/filter_reason)
    - Cursor advance to max platform_post_id after successful poll (D-12)
    """
    global _cached_token
    settings = get_settings()
    account_id = settings.truth_social_account_id
    # Priority: in-process cached token > static token from .env
    token = _cached_token or settings.truth_social_token or None

    since_id = await _get_setting("last_truth_post_id")  # None on first run
    staleness_minutes = int(await _get_setting("signal_staleness_minutes") or "5")
    statuses = await _fetch_posts(account_id, since_id, token)

    if not statuses:
        return  # network error already logged; heartbeat will catch silence

    max_id: str | None = since_id
    inserted = 0
    skipped = 0

    async with AsyncSessionLocal() as session:
        for status in statuses:
            raw_html: str = status.get("content", "")
            text = _strip_html(raw_html)
            content_hash = hashlib.sha256(text.encode()).hexdigest()
            is_filtered, filter_reason = apply_filters(text)

            # Parse posted_at — Mastodon returns ISO 8601 with Z suffix
            created_at_str: str = status.get("created_at", "")
            try:
                posted_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                # Store as naive UTC — consistent with SQLite server_default=func.now()
                posted_at = posted_at.astimezone(timezone.utc).replace(tzinfo=None)
            except (ValueError, AttributeError):
                logger.error("Truth Social: could not parse created_at=%r", created_at_str)
                continue

            # Mark catch-up posts as stale so they never reach analysis/trading
            if not is_filtered:
                age_seconds = (datetime.now(timezone.utc).replace(tzinfo=None) - posted_at).total_seconds()
                if age_seconds > staleness_minutes * 60:
                    is_filtered = True
                    filter_reason = "stale_on_ingest"

            author: str | None = status.get("account", {}).get("username")
            platform_post_id: str = status["id"]

            post = Post(
                platform="truth_social",
                platform_post_id=platform_post_id,
                content=raw_html,       # store raw HTML; display layer strips it
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
                # Track max ID seen (IDs are Snowflake strings; compare numerically)
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

    # Advance cursor only if we saw new posts (D-12)
    if max_id and max_id != since_id:
        await _set_setting("last_truth_post_id", max_id)
