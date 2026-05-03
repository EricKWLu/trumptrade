"""Risk settings router — GET/PATCH /settings/risk endpoints (D-18, SETT-02).

Exposes the 4 configurable risk controls from app_settings:
  - max_position_size_pct  (float, %)
  - stop_loss_pct          (float, % — pre-existing from Phase 2)
  - max_daily_loss_dollars (float, dollars)
  - signal_staleness_minutes (int, minutes)

Changes take effect on the next signal (D-19: consumer reads per-cycle).
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, update

from trumptrade.core.db import AsyncSessionLocal
from trumptrade.core.models import AppSettings

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Pydantic models ───────────────────────────────────────────────────────────

class RiskSettingsResponse(BaseModel):
    """All 5 risk settings — returned by GET and PATCH."""
    max_position_size_pct: float
    stop_loss_pct: float
    max_daily_loss_dollars: float
    signal_staleness_minutes: int
    after_hours_hold_threshold: float


class RiskSettingsPatch(BaseModel):
    """Partial update — only non-None fields are written to app_settings (PATCH semantics)."""
    max_position_size_pct: Optional[float] = Field(default=None, gt=0, le=100)
    stop_loss_pct: Optional[float] = Field(default=None, gt=0, le=100)
    max_daily_loss_dollars: Optional[float] = Field(default=None, gt=0)
    signal_staleness_minutes: Optional[int] = Field(default=None, gt=0)
    after_hours_hold_threshold: Optional[float] = Field(default=None, ge=0, le=1)


# ── DB helpers ────────────────────────────────────────────────────────────────

async def _read_setting(key: str, default: str) -> str:
    """Read a single app_settings value. Returns default if key missing."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AppSettings.value).where(AppSettings.key == key)
        )
        val = result.scalar_one_or_none()
        return val if val is not None else default


async def _read_all_risk_settings() -> RiskSettingsResponse:
    """Read all 5 risk settings and return as RiskSettingsResponse."""
    max_pos = await _read_setting("max_position_size_pct", "2.0")
    stop_loss = await _read_setting("stop_loss_pct", "5.0")
    max_daily = await _read_setting("max_daily_loss_dollars", "500.0")
    staleness = await _read_setting("signal_staleness_minutes", "5")
    after_hours = await _read_setting("after_hours_hold_threshold", "0.85")
    return RiskSettingsResponse(
        max_position_size_pct=float(max_pos),
        stop_loss_pct=float(stop_loss),
        max_daily_loss_dollars=float(max_daily),
        signal_staleness_minutes=int(staleness),
        after_hours_hold_threshold=float(after_hours),
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/risk", response_model=RiskSettingsResponse)
async def get_risk_settings() -> RiskSettingsResponse:
    """Return current values of all risk settings from app_settings."""
    try:
        return await _read_all_risk_settings()
    except Exception as exc:
        logger.error("get_risk_settings: DB error: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to read risk settings")


@router.patch("/risk", response_model=RiskSettingsResponse)
async def patch_risk_settings(body: RiskSettingsPatch) -> RiskSettingsResponse:
    """Update one or more risk settings atomically. Returns all current values after update.

    Changes take effect on the next signal (D-19).
    Uses model_dump(exclude_none=True) — only non-None fields are written.
    """
    updates = body.model_dump(exclude_none=True)
    if not updates:
        # No fields provided — return current values unchanged
        return await _read_all_risk_settings()

    try:
        async with AsyncSessionLocal() as session:
            for key, value in updates.items():
                # Upsert: update if exists, insert if not (handles new keys with no seed)
                existing = await session.execute(
                    select(AppSettings).where(AppSettings.key == key)
                )
                row = existing.scalar_one_or_none()
                if row is not None:
                    await session.execute(
                        update(AppSettings)
                        .where(AppSettings.key == key)
                        .values(value=str(value))
                    )
                else:
                    session.add(AppSettings(key=key, value=str(value)))
            await session.commit()
        logger.info("patch_risk_settings: updated %s", list(updates.keys()))
    except Exception as exc:
        logger.error("patch_risk_settings: DB error: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to update risk settings")

    return await _read_all_risk_settings()


__all__ = ["router"]
