"""End-to-end pipeline test — inject a synthetic post, watch it flow through all 5 gates.

Run while the backend is running. The analysis worker will pick this up within 30 seconds.

Pre-flight checks:
  - bot_enabled must be true (kill switch off)
  - watchlist must contain AAPL (or change TICKER below)
  - US market should be open for the trade to actually submit
    (paper-api.alpaca.markets accepts orders only during regular hours)
"""
from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone

from sqlalchemy import select
from trumptrade.core.db import AsyncSessionLocal
from trumptrade.core.models import AppSettings, Post, Watchlist


TICKER = "AAPL"  # Must be on your watchlist
POST_TEXT = (
    "Apple stock is going to the MOON! American workers are building "
    "the BEST iPhones in the world. New manufacturing deals make AAPL "
    "the greatest investment in American history. Tariffs and trade "
    "policy are working PERFECTLY for our great American tech companies. "
    "BUY AMERICAN, BUY APPLE!"
)


async def preflight() -> bool:
    """Verify the bot can actually trade before injecting the test post."""
    async with AsyncSessionLocal() as s:
        # Bot enabled?
        r = await s.execute(select(AppSettings.value).where(AppSettings.key == "bot_enabled"))
        bot_enabled = r.scalar_one_or_none()
        print(f"  bot_enabled:        {bot_enabled}")
        if bot_enabled != "true":
            print("  ✗ Kill switch is on — toggle it off in Settings before running this test")
            return False

        # Trading mode
        r = await s.execute(select(AppSettings.value).where(AppSettings.key == "trading_mode"))
        mode = r.scalar_one_or_none()
        print(f"  trading_mode:       {mode}")

        # LLM provider
        r = await s.execute(select(AppSettings.value).where(AppSettings.key == "llm_provider"))
        provider = r.scalar_one_or_none()
        print(f"  llm_provider:       {provider}")

        # Watchlist
        r = await s.execute(select(Watchlist.symbol))
        watchlist = [row[0] for row in r.all()]
        print(f"  watchlist contains: {len(watchlist)} tickers")
        if TICKER not in watchlist:
            print(f"  ✗ {TICKER} not in watchlist — add it via the dashboard or change TICKER in this script")
            return False
        print(f"  ✓ {TICKER} is on the watchlist")

        # Confidence threshold
        r = await s.execute(select(AppSettings.value).where(AppSettings.key == "confidence_threshold"))
        threshold = r.scalar_one_or_none()
        print(f"  confidence threshold: {threshold} (LLM must score above this)")

    return True


async def inject_test_post() -> int:
    """Insert a fake Trump post that should pass all filters."""
    text = POST_TEXT
    content_hash = hashlib.sha256(text.encode()).hexdigest()
    posted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    fake_post_id = f"TEST-{int(posted_at.timestamp())}"

    raw_html = f"<p>{text}</p>"

    async with AsyncSessionLocal() as session:
        post = Post(
            platform="truth_social",
            platform_post_id=fake_post_id,
            content=raw_html,
            content_hash=content_hash,
            author="realDonaldTrump",
            posted_at=posted_at,
            is_filtered=False,           # Let analysis worker pick it up
            filter_reason=None,
        )
        session.add(post)
        await session.commit()
        await session.refresh(post)
        return post.id


async def main() -> None:
    print("=" * 60)
    print("Pre-flight check")
    print("=" * 60)
    if not await preflight():
        return

    print()
    print("=" * 60)
    print("Injecting synthetic post")
    print("=" * 60)
    post_id = await inject_test_post()
    print(f"  ✓ Inserted post id={post_id}")
    print(f"  ✓ Content: {POST_TEXT[:80]}...")
    print()
    print("=" * 60)
    print("What to watch in the backend logs")
    print("=" * 60)
    print("""
Within 30 seconds, you should see (in order):

  1. analysis_worker picks up post id={pid}
     INFO  trumptrade.analysis.worker  Analyzing post id={pid} ...

  2. LLM (Groq) returns a verdict
     INFO  trumptrade.analysis.groq_adapter  Groq analyzed post:
       sentiment=BULLISH confidence=0.85+ tickers=['AAPL']

  3. Signal queued for risk guard
     INFO  trumptrade.risk_guard  Queued trade: AAPL buy ...

  4. Risk guard runs checks (market hours / daily cap / position size)
     If market open: INFO  Risk guard approved: AAPL buy
     If market closed: WARNING blocked: market closed (this is fine, it
     means the pipeline worked, just the trade can't physically execute)

  5. Alpaca executor submits bracket order (if approved)
     INFO  Alpaca order submitted: id=... symbol=AAPL qty=...

The new trade will appear in the Trades page on the dashboard.
""".replace("{pid}", str(post_id)))


if __name__ == "__main__":
    asyncio.run(main())
