from __future__ import annotations

"""Benchmarks REST endpoint — GET /benchmarks (Phase 7, COMP-04).

Returns all shadow portfolio snapshots for 4 portfolios (bot, spy, qqq, random)
normalized to % return from the first shared snapshot date.
"""

import logging
from collections import defaultdict

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from trumptrade.core.db import AsyncSessionLocal
from trumptrade.core.models import ShadowPortfolioSnapshot

logger = logging.getLogger(__name__)

router = APIRouter()

PORTFOLIO_NAMES = ("bot", "spy", "qqq", "random")


@router.get("/benchmarks")
async def get_benchmarks() -> dict:
    """Return benchmark comparison data for all 4 shadow portfolios.

    Response shape:
      {"snapshots": [{"date": "YYYY-MM-DD", "bot": 0.0, "spy": 0.0, "qqq": 0.0, "random": 0.0}, ...]}

    All values are % returns from the first shared date:
      0.0 on the first snapshot date for all portfolios.
      1.23 means +1.23% gain since start.
    """
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ShadowPortfolioSnapshot)
                .order_by(
                    ShadowPortfolioSnapshot.snapshot_date.asc(),
                    ShadowPortfolioSnapshot.portfolio_name.asc(),
                )
            )
            rows: list[ShadowPortfolioSnapshot] = list(result.scalars().all())
    except Exception as exc:
        logger.error("get_benchmarks: DB error: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to read benchmark data")

    if not rows:
        return {"snapshots": []}

    # ── Pivot into {date_str: {portfolio_name: nav_value}} ────────────────────
    date_map: dict[str, dict[str, float]] = defaultdict(dict)
    for row in rows:
        date_str = row.snapshot_date.isoformat()
        date_map[date_str][row.portfolio_name] = row.nav_value

    # ── Find dates where ALL 4 portfolios have a snapshot ────────────────────
    # Use all available dates, filling missing portfolios with None.
    all_dates = sorted(date_map.keys())

    # ── Compute first NAV for each portfolio (normalization baseline) ─────────
    first_navs: dict[str, float | None] = {name: None for name in PORTFOLIO_NAMES}
    for date_str in all_dates:
        for name in PORTFOLIO_NAMES:
            if first_navs[name] is None and name in date_map[date_str]:
                first_navs[name] = date_map[date_str][name]

    # ── Build normalized output ───────────────────────────────────────────────
    snapshots = []
    for date_str in all_dates:
        row_data: dict[str, object] = {"date": date_str}
        has_any = False
        for name in PORTFOLIO_NAMES:
            nav = date_map[date_str].get(name)
            first_nav = first_navs[name]
            if nav is not None and first_nav is not None and first_nav > 0:
                row_data[name] = round((nav / first_nav - 1.0) * 100.0, 4)
                has_any = True
            else:
                row_data[name] = None  # Portfolio not yet started or missing
        if has_any:
            snapshots.append(row_data)

    return {"snapshots": snapshots}


__all__ = ["router"]
