from __future__ import annotations

import asyncio
import json
import logging
import random
from datetime import date, datetime, timedelta
from math import floor

from sqlalchemy import select

from trumptrade.core.db import AsyncSessionLocal
from trumptrade.core.models import AppSettings, ShadowPortfolioSnapshot, Watchlist

logger = logging.getLogger(__name__)

STARTING_NAV = 100_000.0  # Virtual starting NAV for all shadow portfolios


# ── Sync helpers (called via run_in_executor) ─────────────────────────────────

def _fetch_close_sync(api_key: str, secret_key: str, symbol: str, target_date: date) -> float | None:
    """Fetch the closing price for symbol on target_date. Returns None on holiday/missing bar.

    SYNC — must be called via run_in_executor in async context.
    Uses broad date window (midnight to midnight UTC) with limit=1 to capture EOD bar.
    Validates bar.timestamp.date() == target_date per assumption A4 in RESEARCH.md.
    """
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    client = StockHistoricalDataClient(api_key=api_key, secret_key=secret_key)
    start = datetime(target_date.year, target_date.month, target_date.day, 0, 0)
    end = datetime(target_date.year, target_date.month, target_date.day, 23, 59)
    request = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame.Day,
        start=start,
        end=end,
        limit=1,
    )
    bar_set = client.get_stock_bars(request)
    bars = bar_set.data.get(symbol, [])
    if not bars:
        return None  # holiday or weekend — caller skips snapshot
    bar = bars[-1]
    # Validate the bar is actually for target_date (A4 mitigation)
    bar_date = bar.timestamp.date() if hasattr(bar.timestamp, "date") else bar.timestamp.date()
    if bar_date != target_date:
        logger.warning(
            "Bar timestamp mismatch: expected %s, got %s — treating as holiday",
            target_date,
            bar_date,
        )
        return None
    return float(bar.close)


def _fetch_bot_equity_sync(api_key: str, secret_key: str, is_paper: bool) -> float:
    """Fetch current account equity from Alpaca. SYNC — run via run_in_executor."""
    from alpaca.trading.client import TradingClient

    client = TradingClient(api_key=api_key, secret_key=secret_key, paper=is_paper)
    account = client.get_account()
    return float(account.equity)


# ── DB helper ─────────────────────────────────────────────────────────────────

async def _read_setting(key: str, default: str) -> str:
    """Read a single app_settings value (matches dashboard/router.py pattern exactly)."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AppSettings.value).where(AppSettings.key == key)
        )
        val = result.scalar_one_or_none()
        return val if val is not None else default


async def _already_snapshotted(portfolio_name: str, snapshot_date: date) -> bool:
    """Return True if a snapshot already exists for this portfolio+date (idempotency guard)."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ShadowPortfolioSnapshot.id)
            .where(ShadowPortfolioSnapshot.portfolio_name == portfolio_name)
            .where(ShadowPortfolioSnapshot.snapshot_date == snapshot_date)
        )
        return result.scalar_one_or_none() is not None


async def _get_last_snapshot(portfolio_name: str) -> ShadowPortfolioSnapshot | None:
    """Return the most recent snapshot for this portfolio, or None if first run."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ShadowPortfolioSnapshot)
            .where(ShadowPortfolioSnapshot.portfolio_name == portfolio_name)
            .order_by(ShadowPortfolioSnapshot.snapshot_date.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


# ── NAV helpers ───────────────────────────────────────────────────────────────

def _compute_index_nav(
    today_close: float,
    last_snapshot: ShadowPortfolioSnapshot | None,
    symbol: str,
) -> tuple[float, float, str]:
    """Compute NAV for an index-tracking portfolio (SPY or QQQ).

    Returns (nav_value, cash=0.0, positions_json).
    On first run: buy STARTING_NAV worth of shares at today_close.
    Subsequent runs: revalue shares at today_close.
    """
    if last_snapshot is None:
        # First snapshot — buy qty shares at today's close
        qty = STARTING_NAV / today_close
        positions = {symbol: {"qty": qty, "avg_price": today_close}}
        nav = STARTING_NAV
    else:
        prev_positions = json.loads(last_snapshot.positions_json)
        qty = prev_positions.get(symbol, {}).get("qty", STARTING_NAV / today_close)
        avg_price = prev_positions.get(symbol, {}).get("avg_price", today_close)
        positions = {symbol: {"qty": qty, "avg_price": avg_price}}
        nav = qty * today_close
    return nav, 0.0, json.dumps(positions)


async def _simulate_random_trade(
    today_close_prices: dict[str, float],
    max_pos_pct: float,
) -> tuple[float, float, str]:
    """Simulate one random buy/sell decision on the watchlist for the random baseline.

    Returns (nav_value, cash, positions_json).
    Reads watchlist and last snapshot from DB. Skips trade if watchlist empty.
    """
    # Read watchlist
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Watchlist.symbol))
        watchlist = [row[0] for row in result.all()]

    last_snap = await _get_last_snapshot("random")

    # Restore state from last snapshot
    if last_snap is None:
        cash = STARTING_NAV
        positions: dict = {}
    else:
        prev = json.loads(last_snap.positions_json)
        cash = float(prev.get("cash", STARTING_NAV))
        positions = {k: v for k, v in prev.items() if k != "cash"}

    if watchlist:
        ticker = random.choice(watchlist)
        # Fetch current price — use close price if available; otherwise skip trade
        current_price = today_close_prices.get(ticker)
        if current_price is None:
            # Ticker not in today's fetched prices — skip trade this day
            logger.info("random_baseline: no price for %s — skipping trade today", ticker)
        else:
            buy_or_sell = random.random() < 0.5  # True = buy
            if buy_or_sell:
                # BUY: allocate max_pos_pct of current NAV (cash + positions value)
                current_nav = cash + sum(
                    p["qty"] * today_close_prices.get(sym, p["avg_price"])
                    for sym, p in positions.items()
                )
                spend = current_nav * (max_pos_pct / 100.0)
                if cash >= spend and spend > 0 and current_price > 0:
                    qty = floor(spend / current_price)
                    if qty > 0:
                        cost = qty * current_price
                        cash -= cost
                        if ticker in positions:
                            # Average up
                            old_qty = positions[ticker]["qty"]
                            old_avg = positions[ticker]["avg_price"]
                            new_qty = old_qty + qty
                            positions[ticker] = {
                                "qty": new_qty,
                                "avg_price": (old_qty * old_avg + qty * current_price) / new_qty,
                            }
                        else:
                            positions[ticker] = {"qty": qty, "avg_price": current_price}
                        logger.info(
                            "random_baseline: BUY %s qty=%s @ %.2f", ticker, qty, current_price
                        )
            else:
                # SELL: liquidate entire position in this ticker if held
                if ticker in positions and positions[ticker]["qty"] > 0:
                    qty = positions[ticker]["qty"]
                    proceeds = qty * current_price
                    cash += proceeds
                    del positions[ticker]
                    logger.info(
                        "random_baseline: SELL %s qty=%s @ %.2f", ticker, qty, current_price
                    )

    # Compute final NAV
    nav = cash + sum(
        p["qty"] * today_close_prices.get(sym, p["avg_price"])
        for sym, p in positions.items()
    )

    # Store cash inside positions_json (keyed as "cash")
    positions_json_dict = dict(positions)
    positions_json_dict["cash"] = cash

    return nav, cash, json.dumps(positions_json_dict)


# ── Main job ──────────────────────────────────────────────────────────────────

async def benchmark_snapshot_job() -> None:
    """Daily EOD benchmark snapshot job — fires Mon-Fri at 4:01pm ET via CronTrigger.

    Writes 4 ShadowPortfolioSnapshot rows: bot, spy, qqq, random.
    Skips entirely on market holidays (no bar returned from Alpaca).
    Idempotent: skips if snapshot already exists for today.
    """
    from trumptrade.core.config import get_settings

    today = date.today()
    logger.info("benchmark_snapshot_job: starting for %s", today)

    # Idempotency: if bot portfolio already has today's snapshot, skip all
    if await _already_snapshotted("bot", today):
        logger.info(
            "benchmark_snapshot_job: snapshots already exist for %s — skipping", today
        )
        return

    settings = get_settings()
    trading_mode = await _read_setting("trading_mode", "paper")
    is_paper = trading_mode != "live"
    max_pos_pct_str = await _read_setting("max_position_size_pct", "2.0")
    max_pos_pct = float(max_pos_pct_str)

    loop = asyncio.get_running_loop()

    # ── Fetch SPY and QQQ closing prices ─────────────────────────────────────
    try:
        spy_close = await loop.run_in_executor(
            None,
            _fetch_close_sync,
            settings.alpaca_api_key,
            settings.alpaca_secret_key,
            "SPY",
            today,
        )
    except Exception as exc:
        logger.error("benchmark_snapshot_job: SPY fetch failed: %s", exc)
        return

    if spy_close is None:
        logger.info(
            "benchmark_snapshot_job: no SPY bar for %s (holiday?) — skipping", today
        )
        return

    try:
        qqq_close = await loop.run_in_executor(
            None,
            _fetch_close_sync,
            settings.alpaca_api_key,
            settings.alpaca_secret_key,
            "QQQ",
            today,
        )
    except Exception as exc:
        logger.error("benchmark_snapshot_job: QQQ fetch failed: %s", exc)
        return

    if qqq_close is None:
        logger.info(
            "benchmark_snapshot_job: no QQQ bar for %s (holiday?) — skipping", today
        )
        return

    # ── Fetch bot NAV ─────────────────────────────────────────────────────────
    try:
        bot_equity = await loop.run_in_executor(
            None,
            _fetch_bot_equity_sync,
            settings.alpaca_api_key,
            settings.alpaca_secret_key,
            is_paper,
        )
    except Exception as exc:
        logger.error("benchmark_snapshot_job: bot equity fetch failed: %s", exc)
        return

    # ── Compute index portfolio NAVs ──────────────────────────────────────────
    spy_last = await _get_last_snapshot("spy")
    qqq_last = await _get_last_snapshot("qqq")

    spy_nav, spy_cash, spy_positions_json = _compute_index_nav(spy_close, spy_last, "SPY")
    qqq_nav, qqq_cash, qqq_positions_json = _compute_index_nav(qqq_close, qqq_last, "QQQ")

    # ── Simulate random trade ─────────────────────────────────────────────────
    # Build a prices dict with what we have so far
    today_prices: dict[str, float] = {"SPY": spy_close, "QQQ": qqq_close}

    # Fetch prices for watchlist tickers not already in today_prices
    async with AsyncSessionLocal() as session:
        wl_result = await session.execute(select(Watchlist.symbol))
        watchlist_symbols = [row[0] for row in wl_result.all()]

    for sym in watchlist_symbols:
        if sym not in today_prices:
            try:
                price = await loop.run_in_executor(
                    None,
                    _fetch_close_sync,
                    settings.alpaca_api_key,
                    settings.alpaca_secret_key,
                    sym,
                    today,
                )
                if price is not None:
                    today_prices[sym] = price
            except Exception as exc:
                logger.warning(
                    "benchmark_snapshot_job: failed to fetch price for %s: %s", sym, exc
                )

    random_nav, random_cash, random_positions_json = await _simulate_random_trade(
        today_prices, max_pos_pct
    )

    # ── Write all 4 snapshots ─────────────────────────────────────────────────
    async with AsyncSessionLocal() as session:
        session.add(ShadowPortfolioSnapshot(
            portfolio_name="bot",
            snapshot_date=today,
            nav_value=bot_equity,
            cash=0.0,
            positions_json=json.dumps({}),
        ))
        session.add(ShadowPortfolioSnapshot(
            portfolio_name="spy",
            snapshot_date=today,
            nav_value=spy_nav,
            cash=spy_cash,
            positions_json=spy_positions_json,
        ))
        session.add(ShadowPortfolioSnapshot(
            portfolio_name="qqq",
            snapshot_date=today,
            nav_value=qqq_nav,
            cash=qqq_cash,
            positions_json=qqq_positions_json,
        ))
        session.add(ShadowPortfolioSnapshot(
            portfolio_name="random",
            snapshot_date=today,
            nav_value=random_nav,
            cash=random_cash,
            positions_json=random_positions_json,
        ))
        await session.commit()

    logger.info(
        "benchmark_snapshot_job: wrote snapshots for %s — bot=%.2f spy=%.2f qqq=%.2f random=%.2f",
        today,
        bot_equity,
        spy_nav,
        qqq_nav,
        random_nav,
    )
