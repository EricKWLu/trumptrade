from __future__ import annotations

"""Ingestion package — Truth Social + X/Twitter pollers, heartbeat, and APScheduler job registration."""

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from trumptrade.ingestion.heartbeat import check_heartbeat
from trumptrade.ingestion.truth_social import poll_truth_social
from trumptrade.ingestion.twitter import poll_twitter


def register_ingestion_jobs(scheduler: AsyncIOScheduler) -> None:
    """Register all ingestion APScheduler jobs on the provided scheduler instance.

    Called from create_app() via local import to avoid circular imports (D-03).
    All jobs use replace_existing=True + stable string id to prevent duplicate
    registrations on hot-reload (RESEARCH.md Pattern 3).

    Jobs registered:
    - ingestion_truth_social: every 60 seconds (D-01)
    - ingestion_twitter:      every 5 minutes  (D-02)
    - ingestion_heartbeat:    every 15 minutes (D-09)
    """
    scheduler.add_job(
        poll_truth_social,
        trigger="interval",
        seconds=60,
        id="ingestion_truth_social",
        replace_existing=True,   # idempotent — safe to call multiple times
        misfire_grace_time=30,   # allow up to 30s late start before skipping
        coalesce=True,           # if multiple misfires, run once not N times
        max_instances=1,         # never run concurrent instances
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


__all__ = ["register_ingestion_jobs"]
