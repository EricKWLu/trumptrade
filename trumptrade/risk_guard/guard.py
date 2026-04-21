from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import partial

import pytz
from alpaca.common.exceptions import APIError
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestTradeRequest
from alpaca.trading.client import TradingClient
from fastapi import HTTPException
from sqlalchemy import select, update

from trumptrade.core.config import get_settings
from trumptrade.core.db import AsyncSessionLocal
from trumptrade.core.models import AppSettings, Signal

logger = logging.getLogger(__name__)


# ── Module-level constants ────────────────────────────────────────────────────

_EASTERN = pytz.timezone("America/New_York")
_AFTER_HOURS_HOLD_THRESHOLD: float = 0.85   # D-17: hardcoded, not configurable
_HOLD_EXPIRY_HOURS: int = 24
_hold_list: list[tuple[datetime, "QueueItem"]] = []   # (enqueued_at_utc, item)


# ── QueueItem dataclass ───────────────────────────────────────────────────────

@dataclass
class QueueItem:
    signal_id: int
    post_id: int
    tickers: list[str]    # already list[str] — NOT a JSON string
    side: str             # "BUY" | "SELL"
    confidence: float
    posted_at: datetime   # naive UTC datetime from SQLite (post.posted_at)


# ── DB helpers ────────────────────────────────────────────────────────────────

async def _get_setting(key: str, default: str = "") -> str:
    """Read a single app_settings value by key. Returns default if key missing."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AppSettings.value).where(AppSettings.key == key)
        )
        val = result.scalar_one_or_none()
        return val if val is not None else default


async def _update_signal_reason(signal_id: int, reason_code: str) -> None:
    """Update Signal.reason_code in DB for audit trail when consumer discards a signal."""
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(Signal)
            .where(Signal.id == signal_id)
            .values(reason_code=reason_code)
        )
        await session.commit()


# ── Alpaca client factory ─────────────────────────────────────────────────────

async def _make_clients() -> tuple[TradingClient, StockHistoricalDataClient]:
    """Instantiate Alpaca clients fresh each cycle — reads trading_mode from DB (D-06)."""
    trading_mode = await _get_setting("trading_mode", "paper")
    is_paper = (trading_mode == "paper")
    settings = get_settings()
    try:
        trading_client = TradingClient(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_secret_key,
            paper=is_paper,
        )
        data_client = StockHistoricalDataClient(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_secret_key,
        )
    except ValueError as exc:
        raise RuntimeError(f"Alpaca credentials not configured: {exc}") from exc
    return trading_client, data_client


# ── Risk check helpers ────────────────────────────────────────────────────────

async def _check_staleness(item: QueueItem) -> bool:
    """Return True if signal is NOT stale (fresh enough to act on). False = discard."""
    staleness_minutes = int(await _get_setting("signal_staleness_minutes", "5"))
    now_naive_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    age_seconds = (now_naive_utc - item.posted_at).total_seconds()
    if age_seconds > staleness_minutes * 60:
        logger.info(
            "risk_consumer: STALE discard (age=%.0fs > %dm) signal_id=%d",
            age_seconds, staleness_minutes, item.signal_id,
        )
        await _update_signal_reason(item.signal_id, "STALE")
        return False
    return True


async def _check_daily_cap(trading_client: TradingClient, loop: asyncio.AbstractEventLoop) -> bool:
    """Return True if daily cap NOT hit (trading allowed). False = DAILY_CAP_HIT."""
    max_daily_loss = float(await _get_setting("max_daily_loss_dollars", "500.0"))
    try:
        account = await loop.run_in_executor(None, trading_client.get_account)
        equity_raw = account.equity
        last_equity_raw = account.last_equity
        if equity_raw is None or last_equity_raw is None:
            logger.warning(
                "risk_consumer: account equity fields None — skipping daily cap check"
            )
            return True  # fail-open: don't block trades on missing data
        equity = float(equity_raw)
        last_equity = float(last_equity_raw)
        daily_loss = last_equity - equity
        if daily_loss >= max_daily_loss:
            logger.warning(
                "risk_consumer: DAILY_CAP_HIT (loss=%.2f >= cap=%.2f)",
                daily_loss, max_daily_loss,
            )
            return False
        return True
    except APIError as exc:
        logger.error("risk_consumer: get_account failed: %s — allowing trade", exc)
        return True  # fail-open: API error should not block all trades


async def _get_equity(trading_client: TradingClient, loop: asyncio.AbstractEventLoop) -> float | None:
    """Fetch live equity for position sizing. Returns None on error."""
    try:
        account = await loop.run_in_executor(None, trading_client.get_account)
        raw = account.equity
        return float(raw) if raw is not None else None
    except APIError as exc:
        logger.error("risk_consumer: get_account for equity failed: %s", exc)
        return None


# ── Position sizing ───────────────────────────────────────────────────────────

async def _compute_qty(
    symbol: str,
    equity: float,
    confidence: float,
    max_position_size_pct: float,
    data_client: StockHistoricalDataClient,
    loop: asyncio.AbstractEventLoop,
) -> int | None:
    """Compute integer share qty per D-07. Returns None if qty < 1 (skip trade)."""
    trade_dollars = equity * (max_position_size_pct / 100) * confidence
    try:
        trade_map = await loop.run_in_executor(
            None,
            partial(
                data_client.get_stock_latest_trade,
                StockLatestTradeRequest(symbol_or_symbols=symbol),
            ),
        )
        share_price: float = trade_map[symbol].price
    except Exception as exc:
        logger.error("risk_consumer: price lookup failed for %s: %s", symbol, exc)
        return None
    qty = math.floor(trade_dollars / share_price)
    if qty < 1:
        logger.info(
            "risk_consumer: qty=0 after floor (trade_dollars=%.2f price=%.2f) — skipping %s",
            trade_dollars, share_price, symbol,
        )
        return None
    return qty


# ── Execution ─────────────────────────────────────────────────────────────────

async def _execute_for_tickers(
    item: QueueItem,
    trading_client: TradingClient,
    data_client: StockHistoricalDataClient,
    loop: asyncio.AbstractEventLoop,
    already_traded: set[str] | None = None,
) -> None:
    """Place one trade per ticker in item.tickers. D-08: one trade per ticker, independent sizing."""
    from trumptrade.trading.executor import AlpacaExecutor, BotDisabledError  # local import — avoids circular

    executor = AlpacaExecutor()
    max_position_size_pct = float(await _get_setting("max_position_size_pct", "2.0"))
    equity = await _get_equity(trading_client, loop)
    if equity is None:
        logger.error("risk_consumer: could not fetch equity — skipping signal_id=%d", item.signal_id)
        return

    processed: set[str] = already_traded or set()

    for symbol in item.tickers:
        if symbol in processed:
            logger.info("risk_consumer: skipping duplicate ticker %s signal_id=%d", symbol, item.signal_id)
            continue
        processed.add(symbol)

        qty = await _compute_qty(symbol, equity, item.confidence, max_position_size_pct, data_client, loop)
        if qty is None:
            continue

        try:
            result = await executor.execute(symbol, item.side.lower(), qty, signal_id=item.signal_id)
            logger.info(
                "risk_consumer: order placed %s %s qty=%d signal_id=%d",
                item.side, symbol, qty, item.signal_id,
            )
        except BotDisabledError:
            logger.info(
                "risk_consumer: bot disabled — skipping %s signal_id=%d", symbol, item.signal_id
            )
        except HTTPException as exc:
            logger.error(
                "risk_consumer: executor HTTPException %d: %s %s signal_id=%d",
                exc.status_code, exc.detail, symbol, item.signal_id,
            )
        except Exception as exc:
            logger.exception(
                "risk_consumer: executor error %s signal_id=%d: %s", symbol, item.signal_id, exc
            )


# ── After-hours hold list ─────────────────────────────────────────────────────

async def _drain_hold_list_if_open(
    trading_client: TradingClient,
    data_client: StockHistoricalDataClient,
    loop: asyncio.AbstractEventLoop,
) -> None:
    """Drain _hold_list when market opens. Expire signals > 24h. One trade per ticker (D-08)."""
    global _hold_list
    if not _hold_list:
        return

    try:
        clock = await loop.run_in_executor(None, trading_client.get_clock)
    except Exception as exc:
        logger.error("risk_consumer: get_clock failed during hold drain: %s", exc)
        return

    if not clock.is_open:
        return

    now = datetime.now(timezone.utc)
    expiry_cutoff = now - timedelta(hours=_HOLD_EXPIRY_HOURS)

    to_process = sorted(_hold_list, key=lambda x: x[0])  # oldest first
    _hold_list = []  # clear before processing (prevent re-drain on same open)

    processed_tickers: set[str] = set()
    for enqueued_at, item in to_process:
        if enqueued_at < expiry_cutoff:
            logger.info(
                "risk_consumer: STALE held signal discarded (held >24h) signal_id=%d",
                item.signal_id,
            )
            await _update_signal_reason(item.signal_id, "STALE")
            continue
        # daily cap check before executing each held signal
        if not await _check_daily_cap(trading_client, loop):
            await _update_signal_reason(item.signal_id, "DAILY_CAP_HIT")
            continue
        await _execute_for_tickers(item, trading_client, data_client, loop, already_traded=processed_tickers)
        processed_tickers.update(item.tickers)


# ── Signal pipeline ───────────────────────────────────────────────────────────

async def _process_signal(
    item: QueueItem,
    trading_client: TradingClient,
    data_client: StockHistoricalDataClient,
    loop: asyncio.AbstractEventLoop,
) -> None:
    """Run staleness → market hours → daily cap → execute. Single signal pipeline."""
    # Check 1: staleness (D-15)
    if not await _check_staleness(item):
        return

    # Check 2: market hours (D-14, D-16) — authoritative check via get_clock().is_open
    try:
        clock = await loop.run_in_executor(None, trading_client.get_clock)
    except Exception as exc:
        logger.error("risk_consumer: get_clock failed: %s — skipping signal_id=%d", exc, item.signal_id)
        return

    if not clock.is_open:
        # After-hours: gate on confidence (D-16, D-17)
        if item.confidence >= _AFTER_HOURS_HOLD_THRESHOLD:
            enqueued_at = datetime.now(timezone.utc)
            _hold_list.append((enqueued_at, item))
            logger.info(
                "risk_consumer: after-hours hold (confidence=%.2f >= 0.85) signal_id=%d",
                item.confidence, item.signal_id,
            )
        else:
            logger.info(
                "risk_consumer: MARKET_CLOSED discard (confidence=%.2f < 0.85) signal_id=%d",
                item.confidence, item.signal_id,
            )
            await _update_signal_reason(item.signal_id, "MARKET_CLOSED")
        return

    # Check 3: daily loss cap (D-10, D-11, D-12)
    if not await _check_daily_cap(trading_client, loop):
        await _update_signal_reason(item.signal_id, "DAILY_CAP_HIT")
        return

    # Check 4: execute — position sizing computed inside _execute_for_tickers (D-07, D-08)
    await _execute_for_tickers(item, trading_client, data_client, loop)


# ── Main consumer coroutine ───────────────────────────────────────────────────

async def risk_consumer() -> None:
    """Consumer loop — started via asyncio.create_task() in FastAPI lifespan (D-03).

    Loops forever until cancelled. Each iteration:
    1. Drain held after-hours signals if market just opened.
    2. Wait for next signal from signal_queue.
    3. Run full risk check pipeline.

    CancelledError MUST propagate — never swallow it (Pitfall 1).
    """
    while True:
        try:
            loop = asyncio.get_running_loop()
            try:
                trading_client, data_client = await _make_clients()
            except RuntimeError as exc:
                logger.error("risk_consumer: client init failed: %s — waiting 10s", exc)
                await asyncio.sleep(10)
                continue

            # Step 1: drain hold list if market just opened
            await _drain_hold_list_if_open(trading_client, data_client, loop)

            # Step 2: wait for next signal (blocks until analysis_worker enqueues one)
            from trumptrade.risk_guard import signal_queue  # local import — avoids circular at module level
            item: QueueItem = await signal_queue.get()

            # Step 3: run risk check pipeline
            await _process_signal(item, trading_client, data_client, loop)

            signal_queue.task_done()

        except asyncio.CancelledError:
            raise  # CRITICAL: never swallow — allows graceful shutdown (Pitfall 1)
        except Exception as exc:
            logger.exception("risk_consumer: unhandled error — continuing: %s", exc)


__all__ = ["QueueItem", "risk_consumer"]
