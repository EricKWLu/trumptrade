from __future__ import annotations

"""Tests for trumptrade.ingestion.filters — pre-filter logic (INGEST-04, D-07, D-08)."""

import pytest

from trumptrade.ingestion.filters import apply_filters, FINANCIAL_KEYWORDS


class TestApplyFilters:
    """Tests for apply_filters(text) -> tuple[bool, str | None]."""

    def test_too_short_returns_filtered(self):
        """Content under 100 chars → (True, 'too_short')."""
        assert apply_filters("hi") == (True, "too_short")

    def test_too_short_at_boundary_99(self):
        """99-char string is still too short."""
        assert apply_filters("x" * 99) == (True, "too_short")

    def test_exact_100_chars_not_too_short(self):
        """100-char string passes the length check (other filters may still apply)."""
        result = apply_filters("x" * 100)
        assert result[1] != "too_short"

    def test_pure_repost_uppercase(self):
        """Content starting with 'RT @' (uppercase) → (True, 'pure_repost')."""
        text = "RT @ someone " + "x" * 100
        assert apply_filters(text) == (True, "pure_repost")

    def test_pure_repost_lowercase(self):
        """Content starting with 'rt @' (lowercase) → (True, 'pure_repost')."""
        text = "rt @ someone " + "x" * 100
        assert apply_filters(text) == (True, "pure_repost")

    def test_pure_repost_mixed_case(self):
        """Content starting with 'Rt @' (mixed) → (True, 'pure_repost')."""
        text = "Rt @ someone " + "x" * 100
        assert apply_filters(text) == (True, "pure_repost")

    def test_no_financial_keywords(self):
        """Long non-repost content with no financial keywords → (True, 'no_financial_keywords')."""
        text = "x" * 100 + " hello world nothing here random words only"
        assert apply_filters(text) == (True, "no_financial_keywords")

    def test_passes_with_financial_keyword_lowercase(self):
        """Long non-repost content with a financial keyword passes."""
        text = "x" * 100 + " the tariffs on china will affect the stock market significantly"
        assert apply_filters(text) == (False, None)

    def test_passes_with_financial_keyword_uppercase(self):
        """Keyword matching is case-insensitive — BITCOIN CRYPTO FED pass."""
        text = "x" * 100 + " BITCOIN and CRYPTO are going up with FED rates"
        assert apply_filters(text) == (False, None)

    def test_too_short_checked_before_pure_repost(self):
        """too_short filter wins over pure_repost when content is short."""
        text = "RT @ someone"  # short AND a repost
        result = apply_filters(text)
        assert result == (True, "too_short")

    def test_return_type_is_tuple(self):
        """Return value is always a tuple of length 2."""
        result = apply_filters("hi")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_passing_post_returns_none_reason(self):
        """When post passes all filters, reason is None."""
        text = "x" * 100 + " tariffs trade economy stock market"
        is_filtered, reason = apply_filters(text)
        assert is_filtered is False
        assert reason is None


class TestFinancialKeywords:
    """Tests for FINANCIAL_KEYWORDS constant."""

    def test_is_frozenset(self):
        """FINANCIAL_KEYWORDS must be a frozenset."""
        assert isinstance(FINANCIAL_KEYWORDS, frozenset)

    def test_contains_required_keywords(self):
        """Spot-check required D-08 keywords are present."""
        required = {
            "tariffs", "trade", "tax", "stock", "market", "economy", "economic",
            "deal", "sanction", "china", "invest", "dollar", "rate", "inflation",
            "bank", "energy", "oil", "gas", "crypto", "bitcoin", "fed", "reserve",
            "deficit", "debt", "budget", "jobs", "employment", "manufacturing",
            "import", "export",
        }
        missing = required - FINANCIAL_KEYWORDS
        assert not missing, f"Missing required keywords: {missing}"

    def test_all_lowercase(self):
        """All keywords in the frozenset are lowercase (matching is done by lowercasing input)."""
        for kw in FINANCIAL_KEYWORDS:
            assert kw == kw.lower(), f"Keyword '{kw}' is not lowercase"
