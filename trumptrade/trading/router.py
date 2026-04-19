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
