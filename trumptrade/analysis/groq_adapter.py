from __future__ import annotations

"""Groq adapter using JSON Object Mode for structured output (D-04).

CRITICAL implementation notes (from RESEARCH.md):
- response.choices[0].message.content IS a JSON string — MUST call json.loads() (Pitfall 2)
- Use asyncio.get_running_loop() NOT get_event_loop() (Pitfall 3)
- Instantiate Groq() inside the sync wrapper to avoid cross-thread pool issues
"""

import asyncio
import json
import logging
from functools import partial

from groq import Groq

from trumptrade.analysis.base import BaseAdapter, SignalResult
from trumptrade.core.config import get_settings

logger = logging.getLogger(__name__)

_GROQ_JSON_SCHEMA_INSTRUCTION = (
    "\n\nYou MUST respond with a valid JSON object containing exactly these fields:\n"
    '{"sentiment": "BULLISH"|"BEARISH"|"NEUTRAL", "confidence": <float 0.0-1.0>, '
    '"affected_tickers": [<ticker strings from watchlist only>]}\n'
    "Do not include any other text outside the JSON object."
)


def _groq_call_sync(api_key: str, model: str, system: str, user_msg: str) -> dict:
    """Synchronous Groq API call — safe to call from run_in_executor.

    Returns parsed dict from JSON string (Pitfall 2: must call json.loads).
    """
    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        max_tokens=256,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system + _GROQ_JSON_SCHEMA_INSTRUCTION},
            {"role": "user", "content": user_msg},
        ],
    )
    raw_str: str = response.choices[0].message.content  # JSON string (Pitfall 2)
    return json.loads(raw_str)


class GroqAdapter(BaseAdapter):
    """Groq llama-3.3-70b-versatile adapter (D-02). Free-tier fallback (D-03)."""

    def __init__(self, model: str = "llama-3.3-70b-versatile") -> None:
        self.model = model

    async def analyze(
        self,
        post_text: str,
        watchlist_tickers: list[str],
        system_prompt: str,
    ) -> SignalResult:
        """Classify post via Groq JSON Object Mode (D-04)."""
        api_key = get_settings().groq_api_key
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. "
                "Set it in .env or switch llm_provider to 'anthropic' in app_settings."
            )

        tickers_csv = ", ".join(watchlist_tickers) if watchlist_tickers else "(none)"
        user_msg = (
            f"Post content:\n{post_text}\n\n"
            f"Current watchlist tickers: {tickers_csv}"
        )

        loop = asyncio.get_running_loop()
        raw: dict = await loop.run_in_executor(
            None,
            partial(_groq_call_sync, api_key, self.model, system_prompt, user_msg),
        )

        try:
            result = SignalResult.model_validate(raw)
        except Exception as exc:
            raise ValueError(f"Groq: SignalResult parse failed: {exc}\nRaw: {raw}") from exc

        logger.debug(
            "Groq analyzed post: sentiment=%s confidence=%.2f tickers=%s",
            result.sentiment,
            result.confidence,
            result.affected_tickers,
        )
        return result


__all__ = ["GroqAdapter"]
