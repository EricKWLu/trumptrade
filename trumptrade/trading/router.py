from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from trumptrade.trading.executor import AlpacaExecutor, BotDisabledError

logger = logging.getLogger(__name__)

router = APIRouter()
_executor = AlpacaExecutor()   # module-level instance — keeps HTTP layer thin


class ExecuteSignalRequest(BaseModel):
    symbol: str
    side: str        # "buy" | "sell"
    qty: float = Field(gt=0)   # Security: reject zero or negative quantity at validation layer


class ExecuteSignalResponse(BaseModel):
    order_id: str
    status: str


class KillSwitchRequest(BaseModel):
    enabled: bool


class KillSwitchResponse(BaseModel):
    bot_enabled: bool
    ok: bool


class SetModeRequest(BaseModel):
    mode: str        # "paper" | "live"
    confirmed: bool  # must be True — extra safety gate (D-09/D-12)


class SetModeResponse(BaseModel):
    trading_mode: str
    ok: bool


@router.post("/execute", response_model=ExecuteSignalResponse)
async def execute_signal(body: ExecuteSignalRequest) -> ExecuteSignalResponse:
    """Place a bracket order on Alpaca. Returns order_id on success.

    Returns 503 if bot is disabled (bot_enabled=false in app_settings).
    Returns 400/429/502 on Alpaca API errors.
    """
    try:
        result = await _executor.execute(body.symbol, body.side, body.qty)
        return ExecuteSignalResponse(**result)
    except BotDisabledError:
        raise HTTPException(status_code=503, detail={"error": "bot_disabled"})


@router.post("/kill-switch", response_model=KillSwitchResponse)
async def kill_switch(body: KillSwitchRequest) -> KillSwitchResponse:
    """Enable or disable the trading bot.

    Updates bot_enabled in app_settings. Changes take effect on the next
    call to /execute — no restart required.
    """
    await _executor.set_bot_enabled(body.enabled)
    logger.info("Kill switch toggled: bot_enabled=%s", body.enabled)
    return KillSwitchResponse(bot_enabled=body.enabled, ok=True)


@router.get("/status")
async def trading_status() -> dict:
    """Return current bot_enabled state for KillSwitchBtn initial load (D-09).

    Reads from AppSettings — same source as the executor's kill-switch check.
    bot_enabled is stored as string "true"/"false" in AppSettings (see executor.py line 32).
    """
    from sqlalchemy import select
    from trumptrade.core.db import AsyncSessionLocal
    from trumptrade.core.models import AppSettings

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AppSettings.value).where(AppSettings.key == "bot_enabled")
        )
        val = result.scalar_one_or_none()
    return {"bot_enabled": val == "true"}


@router.post("/set-mode", response_model=SetModeResponse)
async def set_trading_mode(body: SetModeRequest) -> SetModeResponse:
    """Write trading_mode to app_settings (D-12, TRADE-02).

    Requires mode in {"paper", "live"} and confirmed=True.
    Changes take effect immediately — executor reads trading_mode per-request.
    Returns 422 if mode is invalid or confirmed is False.
    """
    if body.mode not in ("paper", "live"):
        raise HTTPException(status_code=422, detail="mode must be 'paper' or 'live'")
    if not body.confirmed:
        raise HTTPException(status_code=422, detail="confirmed must be true")

    from sqlalchemy import update
    from trumptrade.core.db import AsyncSessionLocal
    from trumptrade.core.models import AppSettings

    async with AsyncSessionLocal() as session:
        await session.execute(
            update(AppSettings)
            .where(AppSettings.key == "trading_mode")
            .values(value=body.mode)
        )
        await session.commit()

    logger.info("Trading mode changed to %s", body.mode)
    return SetModeResponse(trading_mode=body.mode, ok=True)
