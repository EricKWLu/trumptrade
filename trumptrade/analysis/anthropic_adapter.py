from __future__ import annotations

"""Anthropic Claude adapter using tool_use for forced structured output (D-04).

CRITICAL implementation notes (from RESEARCH.md):
- block.input is already a dict — do NOT call json.loads() on it (Pitfall 1)
- Use asyncio.get_running_loop() NOT get_event_loop() (Pitfall 3)
- Instantiate Anthropic() inside the sync wrapper to avoid cross-thread pool issues
- tool_choice={"type":"tool","name":"classify_post"} guarantees a tool_use block
"""

import asyncio
import logging
from functools import partial

import anthropic

from trumptrade.analysis.base import BaseAdapter, SignalResult
from trumptrade.core.config import get_settings

logger = logging.getLogger(__name__)

CLASSIFY_TOOL_DEF: dict = {
    "name": "classify_post",
    "description": (
        "Classify a Trump social media post for trading signal generation. "
        "Return the overall market sentiment, your confidence score between 0.0 and 1.0, "
        "and ONLY the tickers from the provided watchlist that are materially affected by "
        "this post. If no watchlist ticker is affected, return an empty list for "
        "affected_tickers. Do not invent tickers not present in the watchlist."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "sentiment": {
                "type": "string",
                "enum": ["BULLISH", "BEARISH", "NEUTRAL"],
                "description": "Overall market sentiment expressed by the post.",
            },
            "confidence": {
                "type": "number",
                "description": "Confidence score between 0.0 and 1.0.",
            },
            "affected_tickers": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Watchlist tickers materially affected. Empty list if none.",
            },
        },
        "required": ["sentiment", "confidence", "affected_tickers"],
    },
}


def _anthropic_call_sync(api_key: str, model: str, system: str, user_msg: str) -> dict:
    """Synchronous Anthropic API call — safe to call from run_in_executor.

    Returns block.input dict directly (already deserialized by SDK — do not json.loads).
    """
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=256,
        system=system,
        tools=[CLASSIFY_TOOL_DEF],
        tool_choice={"type": "tool", "name": "classify_post"},
        messages=[{"role": "user", "content": user_msg}],
    )
    for block in response.content:
        if block.type == "tool_use":
            return block.input  # dict, not JSON string (Pitfall 1)
    raise ValueError(
        f"Anthropic: no tool_use block in response (stop_reason={response.stop_reason})"
    )


class AnthropicAdapter(BaseAdapter):
    """Anthropic Claude adapter (D-02). Default provider (D-03)."""

    def __init__(self, model: str = "claude-haiku-4-5-20251001") -> None:
        self.model = model

    async def analyze(
        self,
        post_text: str,
        watchlist_tickers: list[str],
        system_prompt: str,
    ) -> SignalResult:
        """Classify post via Anthropic tool_use (D-04)."""
        api_key = get_settings().anthropic_api_key
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. "
                "Set it in .env or switch llm_provider to 'groq' in app_settings."
            )

        tickers_csv = ", ".join(watchlist_tickers) if watchlist_tickers else "(none)"
        user_msg = (
            f"Post content:\n{post_text}\n\n"
            f"Current watchlist tickers: {tickers_csv}"
        )

        loop = asyncio.get_running_loop()
        raw: dict = await loop.run_in_executor(
            None,
            partial(_anthropic_call_sync, api_key, self.model, system_prompt, user_msg),
        )

        try:
            result = SignalResult.model_validate(raw)
        except Exception as exc:
            raise ValueError(f"Anthropic: SignalResult parse failed: {exc}\nRaw: {raw}") from exc

        logger.debug(
            "Anthropic analyzed post: sentiment=%s confidence=%.2f tickers=%s",
            result.sentiment,
            result.confidence,
            result.affected_tickers,
        )
        return result


__all__ = ["AnthropicAdapter"]
