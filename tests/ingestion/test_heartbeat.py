from __future__ import annotations

"""Tests for trumptrade.ingestion.heartbeat — silence alert during market hours (INGEST-01)."""

import asyncio
import inspect
import logging
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from trumptrade.ingestion.heartbeat import check_heartbeat, _is_market_hours


class TestIsMarketHours:
    """Tests for _is_market_hours(start_hour, end_hour) -> bool."""

    def test_returns_bool(self):
        """_is_market_hours always returns a bool."""
        result = _is_market_hours(9, 17)
        assert isinstance(result, bool)

    def test_boundary_inclusive_start(self):
        """Hour equal to start_hour is in-hours (inclusive lower bound)."""
        with patch("trumptrade.ingestion.heartbeat.datetime") as mock_dt:
            # Mock now() to return 9:00 ET
            import pytz
            eastern = pytz.timezone("US/Eastern")
            mock_now = MagicMock()
            mock_now.astimezone.return_value = MagicMock(hour=9)
            mock_dt.now.return_value = mock_now
            assert _is_market_hours(9, 17) is True

    def test_boundary_exclusive_end(self):
        """Hour equal to end_hour is out-of-hours (exclusive upper bound)."""
        with patch("trumptrade.ingestion.heartbeat.datetime") as mock_dt:
            mock_now = MagicMock()
            mock_now.astimezone.return_value = MagicMock(hour=17)
            mock_dt.now.return_value = mock_now
            assert _is_market_hours(9, 17) is False

    def test_inside_window(self):
        """Hour 12 (noon) is inside [9, 17) window."""
        with patch("trumptrade.ingestion.heartbeat.datetime") as mock_dt:
            mock_now = MagicMock()
            mock_now.astimezone.return_value = MagicMock(hour=12)
            mock_dt.now.return_value = mock_now
            assert _is_market_hours(9, 17) is True

    def test_outside_window_early(self):
        """Hour 7 (7am) is before the 9am start."""
        with patch("trumptrade.ingestion.heartbeat.datetime") as mock_dt:
            mock_now = MagicMock()
            mock_now.astimezone.return_value = MagicMock(hour=7)
            mock_dt.now.return_value = mock_now
            assert _is_market_hours(9, 17) is False

    def test_outside_window_evening(self):
        """Hour 20 (8pm) is after the 5pm end."""
        with patch("trumptrade.ingestion.heartbeat.datetime") as mock_dt:
            mock_now = MagicMock()
            mock_now.astimezone.return_value = MagicMock(hour=20)
            mock_dt.now.return_value = mock_now
            assert _is_market_hours(9, 17) is False


class TestCheckHeartbeat:
    """Tests for check_heartbeat() coroutine."""

    def test_is_async_coroutine(self):
        """check_heartbeat must be an async coroutine function."""
        assert asyncio.iscoroutinefunction(check_heartbeat)

    def test_takes_no_arguments(self):
        """check_heartbeat takes zero parameters."""
        sig = inspect.signature(check_heartbeat)
        assert len(sig.parameters) == 0

    @pytest.mark.asyncio
    async def test_logs_warning_when_zero_posts_in_market_hours(self, caplog):
        """When in market hours and zero posts: logs WARNING with exact message."""
        with patch("trumptrade.ingestion.heartbeat._is_market_hours", return_value=True), \
             patch("trumptrade.ingestion.heartbeat.AsyncSessionLocal") as mock_session_cls:
            # Set up context manager mock
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            # First session: return None for both heartbeat settings
            settings_result = MagicMock()
            settings_result.scalar_one_or_none.return_value = None

            # Second session: return count = 0
            count_result = MagicMock()
            count_result.scalar.return_value = 0

            mock_session.execute = AsyncMock(side_effect=[
                settings_result, settings_result,  # start_hour, end_hour
                count_result,                       # post count
            ])

            with caplog.at_level(logging.WARNING, logger="trumptrade.ingestion.heartbeat"):
                await check_heartbeat()

        assert "HEARTBEAT: no Truth Social posts in last 30 minutes" in caplog.text

    @pytest.mark.asyncio
    async def test_no_warning_when_posts_exist(self, caplog):
        """When in market hours but posts exist: no warning logged."""
        with patch("trumptrade.ingestion.heartbeat._is_market_hours", return_value=True), \
             patch("trumptrade.ingestion.heartbeat.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            settings_result = MagicMock()
            settings_result.scalar_one_or_none.return_value = None

            count_result = MagicMock()
            count_result.scalar.return_value = 5  # 5 recent posts

            mock_session.execute = AsyncMock(side_effect=[
                settings_result, settings_result,
                count_result,
            ])

            with caplog.at_level(logging.WARNING, logger="trumptrade.ingestion.heartbeat"):
                await check_heartbeat()

        assert "HEARTBEAT" not in caplog.text

    @pytest.mark.asyncio
    async def test_skips_silently_outside_market_hours(self, caplog):
        """When outside market hours: returns immediately, no DB query, no log."""
        with patch("trumptrade.ingestion.heartbeat._is_market_hours", return_value=False), \
             patch("trumptrade.ingestion.heartbeat.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            # Settings queries still happen (before market hours check), but no count query
            settings_result = MagicMock()
            settings_result.scalar_one_or_none.return_value = None
            mock_session.execute = AsyncMock(side_effect=[
                settings_result, settings_result,  # start/end hour reads
            ])

            with caplog.at_level(logging.WARNING, logger="trumptrade.ingestion.heartbeat"):
                await check_heartbeat()

        # No HEARTBEAT warning should appear
        assert "HEARTBEAT" not in caplog.text
        # execute was called exactly twice (for the two settings reads), not for the count
        assert mock_session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_uses_configurable_hours_from_app_settings(self, caplog):
        """Reads heartbeat_start_hour and heartbeat_end_hour from app_settings."""
        with patch("trumptrade.ingestion.heartbeat._is_market_hours") as mock_market_hours, \
             patch("trumptrade.ingestion.heartbeat.AsyncSessionLocal") as mock_session_cls:
            mock_market_hours.return_value = False

            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            # Return custom hours from settings: 8 and 18
            start_result = MagicMock()
            start_result.scalar_one_or_none.return_value = "8"
            end_result = MagicMock()
            end_result.scalar_one_or_none.return_value = "18"

            mock_session.execute = AsyncMock(side_effect=[start_result, end_result])

            await check_heartbeat()

            # Verify _is_market_hours was called with custom hours (8, 18)
            mock_market_hours.assert_called_once_with(8, 18)

    def test_uses_logger_warning_not_warn(self):
        """heartbeat.py uses logger.warning() not deprecated logger.warn()."""
        import inspect as _inspect
        import trumptrade.ingestion.heartbeat as hb_module
        src = _inspect.getsource(hb_module)
        assert "logger.warning(" in src
        assert "logger.warn(" not in src

    def test_exact_warning_message(self):
        """The exact WARNING message from D-09 is present in the source."""
        import inspect as _inspect
        import trumptrade.ingestion.heartbeat as hb_module
        src = _inspect.getsource(hb_module)
        assert "HEARTBEAT: no Truth Social posts in last 30 minutes" in src
