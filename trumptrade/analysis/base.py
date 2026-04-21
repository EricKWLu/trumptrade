from __future__ import annotations

"""Base adapter interface and shared Pydantic models for LLM analysis (D-02, D-04)."""

import abc
from typing import Literal

from pydantic import BaseModel


class SignalResult(BaseModel):
    """Structured LLM output validated by Pydantic (D-04).

    Ticker stripping (D-08) happens in the worker AFTER parse because the live
    watchlist is runtime data, not available at class-definition time.
    """

    sentiment: Literal["BULLISH", "BEARISH", "NEUTRAL"]
    confidence: float
    affected_tickers: list[str]


class BaseAdapter(abc.ABC):
    """Common interface for all LLM provider adapters (D-02)."""

    @abc.abstractmethod
    async def analyze(
        self,
        post_text: str,
        watchlist_tickers: list[str],
        system_prompt: str,
    ) -> SignalResult:
        """Analyze a post and return a structured signal.

        Raises:
            ValueError: If the LLM response cannot be parsed into SignalResult.
            RuntimeError: If the provider API key is missing.
        """


__all__ = ["BaseAdapter", "SignalResult"]
