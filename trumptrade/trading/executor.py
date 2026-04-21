from __future__ import annotations

import asyncio
import logging
from functools import partial

from alpaca.common.exceptions import APIError
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestTradeRequest
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest, StopLossRequest
from fastapi import HTTPException
from sqlalchemy import select, update

from trumptrade.core.config import get_settings
from trumptrade.core.db import AsyncSessionLocal
from trumptrade.core.models import AppSettings, Order

logger = logging.getLogger(__name__)


class BotDisabledError(Exception):
    """Raised when bot_enabled=false in app_settings."""


class AlpacaExecutor:

    async def execute(self, symbol: str, side: str, qty: float, signal_id: int | None = None) -> dict:
        # STEP 1: Kill-switch check FIRST — before any network call (per D-05 + CONTEXT.md specifics)
        bot_enabled_raw = await self._get_setting("bot_enabled")
        if bot_enabled_raw != "true":           # CRITICAL: compare to string "true", NOT bool()
            raise BotDisabledError()

        # STEP 2: Read runtime settings from DB (re-read per request per D-06 — no caching)
        trading_mode = await self._get_setting("trading_mode")   # "paper" | "live"
        stop_loss_pct = float(await self._get_setting("stop_loss_pct"))  # "5.0" → 5.0
        is_paper = (trading_mode == "paper")

        # STEP 3: Instantiate clients per-request (NOT cached — D-06 requires mode re-read)
        settings = get_settings()
        try:
            trading_client = TradingClient(
                api_key=settings.alpaca_api_key,
                secret_key=settings.alpaca_secret_key,
                paper=is_paper,  # True → paper-api.alpaca.markets, False → api.alpaca.markets
            )
            data_client = StockHistoricalDataClient(
                api_key=settings.alpaca_api_key,
                secret_key=settings.alpaca_secret_key,
            )
        except ValueError as exc:
            raise HTTPException(status_code=502, detail=f"Alpaca credentials not configured: {exc}")

        # STEP 4: Fetch last trade price — sync call MUST use run_in_executor (alpaca-py has NO async methods)
        loop = asyncio.get_running_loop()
        try:
            trade_map = await loop.run_in_executor(
                None,
                partial(
                    data_client.get_stock_latest_trade,
                    StockLatestTradeRequest(symbol_or_symbols=symbol),
                ),
            )
        except APIError as exc:
            logger.error("Alpaca data API error fetching price for %s: %s", symbol, exc)
            raise HTTPException(status_code=502, detail=f"Alpaca data error: {exc.message}")
        last_price: float = trade_map[symbol].price

        # STEP 5: Calculate stop price (D-02)
        stop_price = round(last_price * (1 - stop_loss_pct / 100), 2)  # round to 2dp — Alpaca precision

        # STEP 6: Build bracket order (D-03 + TRADE-03 — stop_loss MUST be atomic, never separate)
        order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
        order_request = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=order_side,
            time_in_force=TimeInForce.DAY,       # DAY safer than GTC in paper mode
            order_class=OrderClass.BRACKET,       # MANDATORY — makes stop_loss atomic
            stop_loss=StopLossRequest(stop_price=stop_price),  # no take_profit in Phase 2
        )

        # STEP 7: Submit order — sync call MUST use run_in_executor
        try:
            alpaca_order = await loop.run_in_executor(
                None, trading_client.submit_order, order_request
            )
        except APIError as exc:
            logger.error("Alpaca order submission failed for %s: %s", symbol, exc)
            if exc.status_code == 403:
                raise HTTPException(status_code=502, detail="Alpaca auth failed")
            elif exc.status_code == 422:
                raise HTTPException(status_code=400, detail=f"Invalid order: {exc.message}")
            elif exc.status_code == 429:
                raise HTTPException(status_code=429, detail="Alpaca rate limit exceeded")
            else:
                raise HTTPException(status_code=502, detail=f"Alpaca error: {exc.message}")

        alpaca_order_id = str(alpaca_order.id)   # CRITICAL: UUID → str before DB write

        # STEP 8: Log confirmed order to DB (D-04 — "confirmed" = order ID assigned, status=submitted)
        await self._log_order(alpaca_order_id, symbol, side, qty, trading_mode, signal_id=signal_id)

        logger.info("Order submitted: %s %s %s qty=%s mode=%s", alpaca_order_id, side, symbol, qty, trading_mode)
        return {"order_id": alpaca_order_id, "status": "submitted"}

    async def set_bot_enabled(self, enabled: bool) -> None:
        """Update bot_enabled in app_settings. Used by kill-switch endpoint (D-05)."""
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(AppSettings)
                .where(AppSettings.key == "bot_enabled")
                .values(value="true" if enabled else "false")   # always string, never Python bool
            )
            await session.commit()
        logger.info("bot_enabled set to %s", enabled)

    async def _get_setting(self, key: str) -> str:
        """Read a single app_settings value by key. Returns raw string."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(AppSettings.value).where(AppSettings.key == key)
            )
            return result.scalar_one()  # raises NoResultFound if key missing — acceptable

    async def _log_order(
        self, alpaca_order_id: str, symbol: str, side: str, qty: float, trading_mode: str,
        signal_id: int | None = None,
    ) -> None:
        """Write submitted order to the orders table."""
        async with AsyncSessionLocal() as session:
            session.add(Order(
                alpaca_order_id=alpaca_order_id,  # already str() converted
                symbol=symbol,
                side=side,
                qty=qty,
                order_type="bracket",
                status="submitted",
                trading_mode=trading_mode,
                signal_id=signal_id,  # Phase 5: links order to signal for full audit chain (SC-4)
            ))
            await session.commit()
