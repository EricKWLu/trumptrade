from __future__ import annotations

"""Heartbeat check — alerts when Truth Social goes silent during market hours (INGEST-01)."""

import logging
from datetime import datetime, timedelta, timezone

import pytz
from sqlalchemy import func, select

from trumptrade.core.db import AsyncSessionLocal
from trumptrade.core.models import AppSettings, Post

logger = logging.getLogger(__name__)

_EASTERN = pytz.timezone("US/Eastern")


def _is_market_hours(start_hour: int = 9, end_hour: int = 17) -> bool:
    """Return True if current US/Eastern time is within [start_hour, end_hour).

    Uses datetime.now(utc).astimezone() — NOT pytz.localize() on a naive datetime.
    Per RESEARCH.md Pattern 5: localize() is bug-prone on DST boundaries.
    """
    now_et = datetime.now(timezone.utc).astimezone(_EASTERN)
    return start_hour <= now_et.hour < end_hour


async def check_heartbeat() -> None:
    """Check if any Truth Social posts arrived in the last 30 minutes.

    Runs every 15 minutes via APScheduler (registered in ingestion/__init__.py).
    Skips silently outside the configured daytime window (default 9am-5pm ET).
    Logs WARNING if zero posts seen during the window.

    Per D-09/D-10.
    """
    async with AsyncSessionLocal() as session:
        # Read configurable window hours from app_settings (string-encoded, cast to int)
        start_result = await session.execute(
            select(AppSettings.value).where(AppSettings.key == "heartbeat_start_hour")
        )
        end_result = await session.execute(
            select(AppSettings.value).where(AppSettings.key == "heartbeat_end_hour")
        )
        start_raw = start_result.scalar_one_or_none()
        end_raw = end_result.scalar_one_or_none()
        start_hour = int(start_raw) if start_raw is not None else 9
        end_hour = int(end_raw) if end_raw is not None else 17

    # Skip silently outside market hours — no further DB query needed
    if not _is_market_hours(start_hour, end_hour):
        return

    # Count posts stored in last 30 minutes.
    # posts.created_at is stored as naive UTC (server_default=func.now() on SQLite).
    # Compare with naive UTC to avoid tzinfo mismatch.
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=30)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(func.count())
            .select_from(Post)
            .where(Post.platform == "truth_social")
            .where(Post.created_at >= cutoff)
        )
        count = result.scalar() or 0

    if count == 0:
        logger.warning("HEARTBEAT: no Truth Social posts in last 30 minutes")
