from __future__ import annotations

"""Analysis worker — APScheduler job that classifies unanalyzed posts (D-05).

Polls every 30 seconds for up to 5 posts where is_filtered=False and no Signal
row exists (LEFT JOIN anti-join, D-06). For each post:
  1. Fetch live watchlist tickers and app_settings (provider, model, threshold)
  2. Dispatch to the active LLM adapter via get_adapter()
  3. Strip tickers not on watchlist (D-08)
  4. Apply keyword rule overlay (D-09 to D-12)
  5. Apply confidence gate (D-13, D-14)
  6. Insert Signal row with full audit fields (D-15, ANLYS-04)
"""

import json
import logging
from typing import Optional

from sqlalchemy import select

from trumptrade.analysis.base import SignalResult
from trumptrade.analysis.dispatcher import get_adapter
from trumptrade.core.db import AsyncSessionLocal
from trumptrade.core.models import AppSettings, KeywordRule, Post, Signal, Watchlist

logger = logging.getLogger(__name__)

# Static system prompt (D-07: wording at Claude's discretion per CONTEXT.md)
_SYSTEM_PROMPT = (
    "You are a trading signal classifier for a personal automated trading bot. "
    "Your task is to analyze a Trump social media post and determine its likely "
    "impact on financial markets. "
    "Classify the overall market sentiment as BULLISH (positive for markets/specific sectors), "
    "BEARISH (negative for markets/specific sectors), or NEUTRAL (no clear market impact). "
    "Provide a confidence score between 0.0 (very uncertain) and 1.0 (very certain). "
    "Identify ONLY tickers from the provided watchlist that are materially affected by "
    "the post content. Return an empty list if no watchlist ticker is clearly relevant. "
    "Focus on direct mentions, sector impacts, policy implications, and trade actions."
)


# ── DB helpers ────────────────────────────────────────────────────────────────

async def _get_app_setting(key: str, default: str) -> str:
    """Read a single app_settings value; return default if not found (Pitfall 6: per-cycle)."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AppSettings.value).where(AppSettings.key == key)
        )
        val = result.scalar_one_or_none()
        return val if val is not None else default


async def _fetch_unanalyzed_posts(limit: int = 5) -> list[Post]:
    """Fetch posts with is_filtered=False and no Signal row — oldest first (D-05, D-06).

    Uses LEFT JOIN anti-join (RESEARCH.md Pattern 4).
    .distinct() added defensively against duplicate join rows.
    """
    stmt = (
        select(Post)
        .outerjoin(Signal, Post.id == Signal.post_id)
        .where(Signal.id.is_(None))
        .where(Post.is_filtered.is_(False))
        .order_by(Post.created_at.asc())
        .limit(limit)
        .distinct()
    )
    async with AsyncSessionLocal() as session:
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def _fetch_watchlist_tickers() -> list[str]:
    """Return all watchlist symbols as a list of strings."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Watchlist.symbol))
        return list(result.scalars().all())


async def _fetch_active_rules() -> list[KeywordRule]:
    """Return all active keyword rules ordered by priority DESC then keyword ASC (D-10)."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(KeywordRule)
            .where(KeywordRule.is_active.is_(True))
            .order_by(KeywordRule.priority.desc(), KeywordRule.keyword.asc())
        )
        return list(result.scalars().all())


# ── Pure business logic (no DB I/O — easily unit-testable) ───────────────────

def _strip_unknown_tickers(
    tickers: list[str], watchlist: list[str]
) -> list[str]:
    """Remove tickers not on the live watchlist (D-08)."""
    watchlist_set = {t.upper() for t in watchlist}
    return [t for t in tickers if t.upper() in watchlist_set]


def _apply_keyword_overlay(
    content: str,
    rules: list[KeywordRule],
    signal: SignalResult,
) -> tuple[str, Optional[str], list[str], list[str]]:
    """Apply keyword rule overlay after LLM analysis (D-09 to D-12).

    Returns (final_action, reason_code, affected_tickers, keyword_matches).

    Matching: case-insensitive substring (D-09).
    Priority: highest wins; alphabetical on tie (D-10).
    Rules already sorted by (priority DESC, keyword ASC) from DB query.
    """
    matched: list[KeywordRule] = [
        r for r in rules if r.keyword.lower() in content.lower()
    ]
    # Record ALL matched keywords for audit, even if overridden (D-12)
    keyword_matches: list[str] = [r.keyword for r in matched]

    if not matched:
        # No rule — derive action directly from LLM sentiment
        if signal.sentiment == "BULLISH":
            action = "BUY"
        elif signal.sentiment == "BEARISH":
            action = "SELL"
        else:
            action = "SKIP"
        return action, None, signal.affected_tickers, keyword_matches

    # Highest priority rule wins (already sorted: index 0 is the winner)
    winner = matched[0]

    if winner.action == "ignore":
        # D-11: ignore → SKIP, KEYWORD_IGNORE; tickers unchanged
        return "SKIP", "KEYWORD_IGNORE", signal.affected_tickers, keyword_matches

    # D-11: buy/sell → override sentiment
    action = "BUY" if winner.action == "buy" else "SELL"
    signal.sentiment = "BULLISH" if winner.action == "buy" else "BEARISH"

    # D-11: replace tickers only if target_tickers is set
    if winner.target_tickers:
        try:
            tickers = json.loads(winner.target_tickers)
        except (json.JSONDecodeError, TypeError):
            logger.warning(
                "KeywordRule id=%s has invalid target_tickers JSON, using LLM tickers",
                winner.id,
            )
            tickers = signal.affected_tickers
    else:
        tickers = signal.affected_tickers

    return action, None, tickers, keyword_matches


def _apply_confidence_gate(
    final_action: str,
    reason_code: Optional[str],
    confidence: float,
    threshold: float,
) -> tuple[str, Optional[str]]:
    """Gate on confidence threshold (D-13, D-14).

    Only applied if not already SKIP from keyword overlay.
    Returns updated (final_action, reason_code).
    """
    if final_action == "SKIP":
        return final_action, reason_code  # already skipped — preserve existing reason
    if confidence < threshold:
        return "SKIP", "BELOW_THRESHOLD"
    return final_action, reason_code


# ── Main worker coroutine ─────────────────────────────────────────────────────

async def analysis_worker() -> None:
    """APScheduler job — classify unanalyzed posts and write Signal rows (D-05).

    Called every 30 seconds. Processes up to 5 posts per tick (D-05).
    Reads llm_provider, llm_model, confidence_threshold from app_settings
    each invocation so provider switches take effect immediately (D-01, Pitfall 6).

    On LLM parse failure: log ERROR, skip post, retry on next tick (D-04).
    """
    posts = await _fetch_unanalyzed_posts(limit=5)
    if not posts:
        return  # Nothing to analyze — exit early

    # Read config fresh per cycle (D-01, Pitfall 6)
    provider = await _get_app_setting("llm_provider", "anthropic")
    model = await _get_app_setting("llm_model", "claude-haiku-4-5-20251001")
    threshold_str = await _get_app_setting("confidence_threshold", "0.7")
    try:
        threshold = float(threshold_str)
    except ValueError:
        logger.warning(
            "Invalid confidence_threshold=%r in app_settings, using 0.7", threshold_str
        )
        threshold = 0.7

    watchlist = await _fetch_watchlist_tickers()
    rules = await _fetch_active_rules()

    try:
        adapter = get_adapter(provider, model)
    except ValueError as exc:
        logger.error("analysis_worker: invalid provider config: %s", exc)
        return

    inserted = 0
    skipped_error = 0

    for post in posts:
        # Build prompt strings for audit (D-15)
        tickers_csv = ", ".join(watchlist) if watchlist else "(none)"
        user_msg = (
            f"Post content:\n{post.content}\n\n"
            f"Current watchlist tickers: {tickers_csv}"
        )
        llm_prompt = f"[SYSTEM]\n{_SYSTEM_PROMPT}\n\n[USER]\n{user_msg}"

        try:
            signal_result: SignalResult = await adapter.analyze(
                post_text=post.content,
                watchlist_tickers=watchlist,
                system_prompt=_SYSTEM_PROMPT,
            )
        except Exception as exc:
            logger.error(
                "analysis_worker: LLM analysis failed for post_id=%d: %s — skipping",
                post.id,
                exc,
            )
            skipped_error += 1
            continue

        # Store raw response for audit (D-15)
        llm_response = signal_result.model_dump_json()

        # Strip tickers not on watchlist (D-08)
        signal_result.affected_tickers = _strip_unknown_tickers(
            signal_result.affected_tickers, watchlist
        )

        # Keyword overlay (D-09 to D-12)
        final_action, reason_code, final_tickers, keyword_matches = _apply_keyword_overlay(
            content=post.content,
            rules=rules,
            signal=signal_result,
        )

        # Confidence gate (D-13, D-14)
        final_action, reason_code = _apply_confidence_gate(
            final_action=final_action,
            reason_code=reason_code,
            confidence=signal_result.confidence,
            threshold=threshold,
        )

        # Insert Signal row with full audit (D-15, ANLYS-04)
        signal = Signal(
            post_id=post.id,
            sentiment=signal_result.sentiment,
            confidence=signal_result.confidence,
            affected_tickers=json.dumps(final_tickers),
            llm_prompt=llm_prompt,
            llm_response=llm_response,
            keyword_matches=json.dumps(keyword_matches),
            final_action=final_action,
            reason_code=reason_code,
        )

        async with AsyncSessionLocal() as session:
            session.add(signal)
            await session.commit()

        inserted += 1
        logger.info(
            "analysis_worker: post_id=%d → action=%s sentiment=%s confidence=%.2f "
            "tickers=%s reason=%s",
            post.id,
            final_action,
            signal_result.sentiment,
            signal_result.confidence,
            final_tickers,
            reason_code,
        )

    logger.info(
        "analysis_worker tick complete: analyzed=%d skipped_error=%d",
        inserted,
        skipped_error,
    )


__all__ = ["analysis_worker"]
