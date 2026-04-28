"""Dashboard REST endpoints — GET /posts, GET /trades, GET /portfolio, GET /alerts (Phase 6).

DASH-01: /posts — paginated post feed, newest-first
DASH-02: /trades — orders with joined signal+post+fill audit chain
DASH-03: /portfolio — live Alpaca positions + account via run_in_executor
DASH-04: /alerts — in-memory alert polling; append_alert() called by other modules
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from trumptrade.core.db import AsyncSessionLocal
from trumptrade.core.models import AppSettings, Fill, Order, Post, Signal

logger = logging.getLogger(__name__)

router = APIRouter()

# ── In-memory alert store (DASH-04, D-10) ────────────────────────────────────
# Module-level list — survives for the process lifetime.
# Other modules call append_alert() to surface errors into the alert panel.
_alerts: list[dict] = []


def append_alert(source: str, message: str) -> None:
    """Surface an error into the persistent alert panel. Called by risk_guard, ingestion."""
    _alerts.append({
        "source": source,
        "message": message,
        "ts": datetime.utcnow().isoformat(),
    })
    logger.warning("alert appended: source=%s message=%s", source, message)


def clear_alerts() -> None:
    """Clear all resolved alerts."""
    _alerts.clear()


# ── DB helper ─────────────────────────────────────────────────────────────────

async def _read_setting(key: str, default: str) -> str:
    """Read a single app_settings value (matches risk_guard/router.py pattern exactly)."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AppSettings.value).where(AppSettings.key == key)
        )
        val = result.scalar_one_or_none()
        return val if val is not None else default


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/posts")
async def get_posts(
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    """Return posts newest-first with signal data joined. Used by FeedPage initial load (DASH-01)."""
    stmt = (
        select(Post, Signal)
        .outerjoin(Signal, Signal.post_id == Post.id)
        .order_by(Post.posted_at.desc())
        .limit(limit)
        .offset(offset)
    )
    async with AsyncSessionLocal() as session:
        result = await session.execute(stmt)
        rows = result.all()
    out = []
    for post, signal in rows:
        out.append({
            "id": post.id,
            "platform": post.platform,
            "content": post.content,
            "posted_at": post.posted_at.isoformat() + "Z",
            "created_at": post.created_at.isoformat() + "Z",
            "is_filtered": post.is_filtered,
            "filter_reason": post.filter_reason,
            "signal": {
                "sentiment": signal.sentiment,
                "confidence": signal.confidence,
                "affected_tickers": json.loads(signal.affected_tickers) if signal.affected_tickers else [],
                "final_action": signal.final_action,
                "reason_code": signal.reason_code,
            } if signal else None,
        })
    return out


@router.get("/trades")
async def get_trades() -> list[dict]:
    """Return orders joined with signal+post+fill for full audit chain (DASH-02, D-07, D-08).

    Uses LEFT OUTER JOINs — returns all orders even if signal/post/fill is missing.
    llm_prompt and llm_response are included (D-08: intentional for debugging).
    """
    stmt = (
        select(Order, Signal, Post, Fill)
        .outerjoin(Signal, Order.signal_id == Signal.id)
        .outerjoin(Post, Signal.post_id == Post.id)
        .outerjoin(Fill, Fill.order_id == Order.id)
        .order_by(Order.submitted_at.desc())
        .limit(200)
    )
    async with AsyncSessionLocal() as session:
        result = await session.execute(stmt)
        rows = result.all()

    out = []
    for order, signal, post, fill in rows:
        row: dict = {
            "id": order.id,
            "symbol": order.symbol,
            "side": order.side,
            "qty": order.qty,
            "status": order.status,
            "order_type": order.order_type,
            "submitted_at": order.submitted_at.isoformat(),
            "filled_at": order.filled_at.isoformat() if order.filled_at else None,
            "fill_price": order.fill_price,
            "trading_mode": order.trading_mode,
            "alpaca_order_id": order.alpaca_order_id,
            "signal": None,
            "post": None,
            "fill": None,
        }
        if signal:
            row["signal"] = {
                "id": signal.id,
                "sentiment": signal.sentiment,
                "confidence": signal.confidence,
                "affected_tickers": json.loads(signal.affected_tickers) if signal.affected_tickers else [],
                "final_action": signal.final_action,
                "reason_code": signal.reason_code,
                "keyword_matches": json.loads(signal.keyword_matches) if signal.keyword_matches else [],
                "llm_prompt": signal.llm_prompt,      # D-08: exposed for audit
                "llm_response": signal.llm_response,  # D-08: exposed for audit
            }
        if post:
            row["post"] = {
                "id": post.id,
                "platform": post.platform,
                "content": post.content,
                "posted_at": post.posted_at.isoformat() + "Z",
                "is_filtered": post.is_filtered,
            }
        if fill:
            row["fill"] = {
                "id": fill.id,
                "qty": fill.qty,
                "price": fill.price,
                "filled_at": fill.filled_at.isoformat(),
            }
        out.append(row)
    return out


@router.get("/alerts")
async def get_alerts() -> list[dict]:
    """Return active alerts (DASH-04). Polled every 10s by frontend AlertPanel."""
    return list(_alerts)


@router.get("/portfolio")
async def get_portfolio() -> dict:
    """Return live Alpaca positions + account summary (DASH-03, D-03).

    CRITICAL: alpaca-py TradingClient is synchronous — MUST use run_in_executor.
    Calling client.get_account() directly in async context blocks the event loop.
    TradingClient instantiated per-request (not module-level) — trading_mode re-read each call.
    """
    # Local imports — avoid startup overhead and keep module-level imports minimal
    from alpaca.trading.client import TradingClient
    from trumptrade.core.config import get_settings

    settings = get_settings()
    trading_mode = await _read_setting("trading_mode", "paper")
    is_paper = (trading_mode != "live")

    client = TradingClient(
        api_key=settings.alpaca_api_key,
        secret_key=settings.alpaca_secret_key,
        paper=is_paper,
    )

    try:
        loop = asyncio.get_running_loop()
        account = await loop.run_in_executor(None, client.get_account)
        positions = await loop.run_in_executor(None, client.get_all_positions)
    except Exception as exc:
        logger.error("get_portfolio: Alpaca API error: %s", exc)
        raise HTTPException(status_code=502, detail=f"Alpaca API unavailable: {exc}")

    pl_today = float(account.equity) - float(account.last_equity)

    return {
        "equity": float(account.equity),
        "last_equity": float(account.last_equity),
        "pl_today": pl_today,
        "buying_power": float(account.buying_power),
        "trading_mode": trading_mode,
        "positions": [
            {
                "symbol": p.symbol,
                "qty": float(p.qty),
                "market_value": float(p.market_value),
                "avg_entry_price": float(p.avg_entry_price),
                "unrealized_pl": float(p.unrealized_pl),
                "unrealized_plpc": float(p.unrealized_plpc),
            }
            for p in positions
        ],
    }


__all__ = ["router", "append_alert", "clear_alerts"]
