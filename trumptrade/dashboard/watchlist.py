"""Watchlist CRUD endpoints — GET/POST/DELETE /watchlist (SETT-01, D-11)."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from trumptrade.core.db import AsyncSessionLocal
from trumptrade.core.models import Watchlist

logger = logging.getLogger(__name__)

router = APIRouter()


class WatchlistAdd(BaseModel):
    symbol: str = Field(pattern=r"^[A-Z]{1,5}$")  # uppercase alpha 1-5 chars; SQL-injection safe


@router.get("/watchlist")
async def get_watchlist() -> list[dict]:
    """Return all watchlist symbols ordered alphabetically."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Watchlist).order_by(Watchlist.symbol.asc())
        )
        items = result.scalars().all()
    return [{"symbol": item.symbol, "added_at": item.added_at.isoformat()} for item in items]


@router.post("/watchlist", status_code=201)
async def add_watchlist(body: WatchlistAdd) -> dict:
    """Add a ticker to the watchlist. Returns 409 if already present."""
    try:
        async with AsyncSessionLocal() as session:
            session.add(Watchlist(symbol=body.symbol))
            await session.commit()
        logger.info("watchlist: added %s", body.symbol)
        return {"symbol": body.symbol, "added": True}
    except IntegrityError:
        raise HTTPException(status_code=409, detail=f"Symbol already in watchlist: {body.symbol}")
    except Exception as exc:
        logger.error("watchlist add error: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to add symbol")


@router.delete("/watchlist/{symbol}", status_code=200)
async def remove_watchlist(symbol: str) -> dict:
    """Remove a ticker from the watchlist. Returns 404 if not present."""
    symbol = symbol.upper()
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Watchlist).where(Watchlist.symbol == symbol)
        )
        item = result.scalar_one_or_none()
        if item is None:
            raise HTTPException(status_code=404, detail=f"Symbol not in watchlist: {symbol}")
        await session.execute(delete(Watchlist).where(Watchlist.symbol == symbol))
        await session.commit()
    logger.info("watchlist: removed %s", symbol)
    return {"symbol": symbol, "removed": True}
