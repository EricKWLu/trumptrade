from __future__ import annotations

"""Benchmarks package — shadow portfolio snapshot job + APScheduler registration (Phase 7)."""

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from trumptrade.benchmarks.job import benchmark_snapshot_job


def register_benchmark_jobs(scheduler: AsyncIOScheduler) -> None:
    """Register the daily EOD benchmark snapshot CronTrigger job (D-06).

    Fires Mon-Fri at 4:01pm ET (1 min after market close).
    Called from create_app() via local import to avoid circular imports.
    """
    from apscheduler.triggers.cron import CronTrigger

    scheduler.add_job(
        benchmark_snapshot_job,
        trigger=CronTrigger(
            day_of_week="mon-fri",
            hour=16,
            minute=1,
            timezone="US/Eastern",
        ),
        id="benchmarks_snapshot",
        replace_existing=True,
        misfire_grace_time=300,  # 5 min grace — cron may miss briefly at startup
        coalesce=True,
        max_instances=1,
    )


__all__ = ["register_benchmark_jobs"]
