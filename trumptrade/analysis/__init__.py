from __future__ import annotations

"""Analysis package — LLM signal classification + APScheduler job registration (Phase 4)."""

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from trumptrade.analysis.worker import analysis_worker


def register_analysis_jobs(scheduler: AsyncIOScheduler) -> None:
    """Register the analysis_worker APScheduler job (D-05).

    Called from create_app() via local import to avoid circular imports.
    Job parameters:
    - 30-second interval
    - misfire_grace_time=15: allow up to 15s late start before skipping
    - coalesce=True: if multiple misfires, run once not N times
    - max_instances=1: never run concurrent analysis cycles
    """
    scheduler.add_job(
        analysis_worker,
        trigger="interval",
        seconds=30,
        id="analysis_worker",
        replace_existing=True,
        misfire_grace_time=15,
        coalesce=True,
        max_instances=1,
    )


__all__ = ["register_analysis_jobs"]
