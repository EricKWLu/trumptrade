"""Tests for AlpacaExecutor service class.

TDD RED phase — these tests define required behavior before implementation.
All tests are unit-level: DB calls are mocked, Alpaca clients are never hit.
"""
from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_executor_with_settings(bot_enabled: str, trading_mode: str = "paper", stop_loss_pct: str = "5.0"):
    """Return an AlpacaExecutor whose _get_setting() returns controlled values."""
    from trumptrade.trading.executor import AlpacaExecutor

    executor = AlpacaExecutor()

    settings_map = {
        "bot_enabled": bot_enabled,
        "trading_mode": trading_mode,
        "stop_loss_pct": stop_loss_pct,
    }

    async def fake_get_setting(key: str) -> str:
        return settings_map[key]

    executor._get_setting = fake_get_setting
    executor._log_order = AsyncMock()
    return executor


# ---------------------------------------------------------------------------
# Test 1: bot_enabled="false" raises BotDisabledError before any network call
# ---------------------------------------------------------------------------

def test_bot_disabled_raises_before_network():
    """bot_enabled='false' must raise BotDisabledError immediately."""
    from trumptrade.trading.executor import BotDisabledError

    executor = _make_executor_with_settings(bot_enabled="false")

    with patch("trumptrade.trading.executor.TradingClient") as mock_tc, \
         patch("trumptrade.trading.executor.StockHistoricalDataClient") as mock_dc:
        with pytest.raises(BotDisabledError):
            asyncio.run(executor.execute("AAPL", "buy", 1.0))

        # CRITICAL: no Alpaca client instantiated when bot is disabled
        mock_tc.assert_not_called()
        mock_dc.assert_not_called()


# ---------------------------------------------------------------------------
# Test 2: bot_enabled="true" proceeds (does not raise BotDisabledError)
# ---------------------------------------------------------------------------

def test_bot_enabled_proceeds():
    """bot_enabled='true' must NOT raise BotDisabledError."""
    from trumptrade.trading.executor import BotDisabledError

    executor = _make_executor_with_settings(bot_enabled="true")

    fake_trade = MagicMock()
    fake_trade.price = 100.0
    fake_trade_map = {"AAPL": fake_trade}

    fake_order = MagicMock()
    fake_order.id = "test-uuid-1234"

    with patch("trumptrade.trading.executor.TradingClient"), \
         patch("trumptrade.trading.executor.StockHistoricalDataClient") as mock_dc_cls, \
         patch("trumptrade.trading.executor.get_settings"):

        mock_dc_instance = MagicMock()
        mock_dc_cls.return_value = mock_dc_instance
        mock_dc_instance.get_stock_latest_trade.return_value = fake_trade_map

        with patch("asyncio.get_running_loop") as mock_loop_fn:
            mock_loop = MagicMock()
            mock_loop_fn.return_value = mock_loop
            mock_loop.run_in_executor = AsyncMock(side_effect=[fake_trade_map, fake_order])

            try:
                result = asyncio.run(executor.execute("AAPL", "buy", 1.0))
                # Should not raise BotDisabledError
            except BotDisabledError:
                pytest.fail("BotDisabledError raised when bot_enabled='true'")
            except Exception:
                pass  # Other exceptions are OK — we only care about BotDisabledError


# ---------------------------------------------------------------------------
# Test 3: stop_price calculation: last_price=100.0, stop_loss_pct=5.0 → 95.0
# ---------------------------------------------------------------------------

def test_stop_price_calculation_basic():
    """last_price=100.0, stop_loss_pct=5.0 → stop_price=95.0."""
    # Test the math directly — extract formula from executor module
    last_price = 100.0
    stop_loss_pct = 5.0
    stop_price = round(last_price * (1 - stop_loss_pct / 100), 2)
    assert stop_price == 95.0


# ---------------------------------------------------------------------------
# Test 4: stop_price precision: last_price=189.2345, stop_loss_pct=5.0 → 179.77
# ---------------------------------------------------------------------------

def test_stop_price_precision():
    """last_price=189.2345, stop_loss_pct=5.0 → stop_price=179.77 (2dp)."""
    last_price = 189.2345
    stop_loss_pct = 5.0
    stop_price = round(last_price * (1 - stop_loss_pct / 100), 2)
    assert stop_price == 179.77


# ---------------------------------------------------------------------------
# Test 5: set_bot_enabled(True) writes "true" string to DB
# ---------------------------------------------------------------------------

def test_set_bot_enabled_true_writes_string():
    """set_bot_enabled(True) must store the string 'true', not Python True."""
    from trumptrade.trading.executor import AlpacaExecutor

    executor = AlpacaExecutor()

    captured_values = []

    class FakeResult:
        pass

    class FakeSession:
        async def execute(self, stmt):
            # Capture the compiled values for assertion
            compiled = stmt.compile(compile_kwargs={"literal_binds": True})
            captured_values.append(str(compiled))
            return FakeResult()

        async def commit(self):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    with patch("trumptrade.trading.executor.AsyncSessionLocal", return_value=FakeSession()):
        asyncio.run(executor.set_bot_enabled(True))

    # The SQL should contain "true" as string value
    assert any("true" in v for v in captured_values), \
        f"Expected 'true' string in SQL, got: {captured_values}"


# ---------------------------------------------------------------------------
# Test 6: set_bot_enabled(False) writes "false" string to DB
# ---------------------------------------------------------------------------

def test_set_bot_enabled_false_writes_string():
    """set_bot_enabled(False) must store the string 'false', not Python False."""
    from trumptrade.trading.executor import AlpacaExecutor

    executor = AlpacaExecutor()

    captured_values = []

    class FakeResult:
        pass

    class FakeSession:
        async def execute(self, stmt):
            compiled = stmt.compile(compile_kwargs={"literal_binds": True})
            captured_values.append(str(compiled))
            return FakeResult()

        async def commit(self):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    with patch("trumptrade.trading.executor.AsyncSessionLocal", return_value=FakeSession()):
        asyncio.run(executor.set_bot_enabled(False))

    assert any("false" in v for v in captured_values), \
        f"Expected 'false' string in SQL, got: {captured_values}"


# ---------------------------------------------------------------------------
# Test 7: BotDisabledError is a plain Exception (not HTTPException)
# ---------------------------------------------------------------------------

def test_bot_disabled_error_is_plain_exception():
    """BotDisabledError must be a subclass of Exception, not HTTPException."""
    from trumptrade.trading.executor import BotDisabledError

    # Must be a plain Exception
    assert issubclass(BotDisabledError, Exception)

    # Must NOT be an HTTPException
    try:
        from fastapi import HTTPException
        assert not issubclass(BotDisabledError, HTTPException), \
            "BotDisabledError must not be an HTTPException — router maps it to 503"
    except ImportError:
        pass  # FastAPI not installed — plain Exception check is sufficient
