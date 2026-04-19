"""SQLAlchemy 2.x ORM models for TrumpTrade — all 8 tables (D-05)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


# ── Table 1: watchlist ──────────────────────────────────────────────────────
# SETT-01: bot only ever trades tickers on this list

class Watchlist(Base):
    __tablename__ = "watchlist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


# ── Table 2: app_settings ───────────────────────────────────────────────────
# D-09: runtime-editable settings; key-value store; seeded in migration (D-10)

class AppSettings(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


# ── Table 3: posts ──────────────────────────────────────────────────────────

class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # truth_social | twitter
    platform_post_id: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # unique per platform — unique constraint added below
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False
    )  # SHA-256 hex; cross-platform dedup gate
    author: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    posted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    is_filtered: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    filter_reason: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("platform", "platform_post_id", name="uq_posts_platform_post_id"),
    )


# ── Table 4: signals ────────────────────────────────────────────────────────

class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(Integer, nullable=False)  # FK to posts.id
    sentiment: Mapped[str] = mapped_column(
        String(10), nullable=False
    )  # BULLISH | BEARISH | NEUTRAL
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    affected_tickers: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # JSON array of ticker strings
    llm_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    llm_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    keyword_matches: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # JSON array
    final_action: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    reason_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


# ── Table 5: orders ─────────────────────────────────────────────────────────
# D-07: separate orders (submitted) and fills (confirmed) tables

class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    signal_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )  # nullable: allows manual/test orders
    alpaca_order_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(10), nullable=False)
    side: Mapped[str] = mapped_column(String(4), nullable=False)  # buy | sell
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    order_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="bracket"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="submitted"
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    filled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    fill_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    trading_mode: Mapped[str] = mapped_column(
        String(5), nullable=False, default="paper"
    )  # paper | live


# ── Table 6: fills ──────────────────────────────────────────────────────────

class Fill(Base):
    __tablename__ = "fills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(Integer, nullable=False)  # FK to orders.id
    alpaca_fill_id: Mapped[str] = mapped_column(String(64), nullable=False)
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    filled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


# ── Table 7: shadow_portfolio_snapshots ─────────────────────────────────────
# D-06: one row per portfolio per day; NAV math for SPY/QQQ/random benchmarks

class ShadowPortfolioSnapshot(Base):
    __tablename__ = "shadow_portfolio_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portfolio_name: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # SPY | QQQ | random
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    nav_value: Mapped[float] = mapped_column(Float, nullable=False)
    cash: Mapped[float] = mapped_column(Float, nullable=False)
    positions_json: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # JSON object: {ticker: {qty, avg_price}}
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


# ── Table 8: keyword_rules ──────────────────────────────────────────────────

class KeywordRule(Base):
    __tablename__ = "keyword_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    keyword: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(
        String(10), nullable=False
    )  # buy | sell | ignore
    target_tickers: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # JSON array or null
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
