from __future__ import annotations

"""Pre-filter logic for ingested posts — runs before LLM analysis (INGEST-04)."""

FINANCIAL_KEYWORDS: frozenset[str] = frozenset({
    "tariffs", "trade", "tax", "stock", "market", "economy", "economic",
    "deal", "sanction", "china", "invest", "dollar", "rate", "inflation",
    "bank", "energy", "oil", "gas", "crypto", "bitcoin", "fed", "reserve",
    "deficit", "debt", "budget", "jobs", "employment", "manufacturing",
    "import", "export", "strait", "war"
})


def apply_filters(text: str) -> tuple[bool, str | None]:
    """Classify a post for pre-filtering before LLM analysis.

    Returns (is_filtered, filter_reason). filter_reason is None when post passes.
    Checks are applied in order; first match wins.

    Per D-07:
      1. len(text) < 100 → too_short
      2. starts with "RT @" (case-insensitive) → pure_repost
      3. no financial keyword in text → no_financial_keywords
    """
    if len(text) < 100:
        return True, "too_short"
    if text.upper().startswith("RT @"):
        return True, "pure_repost"
    words = set(text.lower().split())
    if not words & FINANCIAL_KEYWORDS:
        return True, "no_financial_keywords"
    return False, None


__all__ = ["apply_filters", "FINANCIAL_KEYWORDS"]
