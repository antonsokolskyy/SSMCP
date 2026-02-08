"""Unit tests for timing utilities."""

import asyncio
import logging
import time
from unittest.mock import MagicMock, patch

import pytest

from ssmcp.timing import timeit, timer

# Test constants
MIN_EXECUTION_TIME = 0.01  # Minimum expected execution time in seconds (10ms)
EXPECTED_SUM_RESULT = 5  # Expected result of 2 + 3
EXPECTED_MULTIPLY_RESULT = 12  # Expected result of 3 * 4


class TestTimer:
    """Test timer context manager."""

    @patch("ssmcp.timing.logger")
    def test_timer_measures_execution(self, mock_logger: MagicMock) -> None:
        """Test that timer context manager measures and logs execution time."""
        with timer("Test operation", log_level=logging.INFO):
            time.sleep(MIN_EXECUTION_TIME)

        mock_logger.log.assert_called_once()
        args = mock_logger.log.call_args[0]
        assert args[0] == logging.INFO
        assert "Test operation" in args[2]
        assert isinstance(args[3], float)
        assert args[3] >= MIN_EXECUTION_TIME


class TestTimeit:
    """Test timeit decorator."""

    @patch("ssmcp.timing.logger")
    def test_timeit_sync_function(self, mock_logger: MagicMock) -> None:
        """Test timeit decorator with synchronous function."""
        @timeit("Sync operation")
        def sync_function(x: int, y: int) -> int:
            time.sleep(MIN_EXECUTION_TIME)
            return x + y

        result = sync_function(2, 3)

        assert result == EXPECTED_SUM_RESULT
        mock_logger.log.assert_called_once()
        args = mock_logger.log.call_args[0]
        assert args[0] == logging.INFO
        assert "Sync operation" in args[2]
        assert isinstance(args[3], float)

    @patch("ssmcp.timing.logger")
    async def test_timeit_async_function(self, mock_logger: MagicMock) -> None:
        """Test timeit decorator with asynchronous function."""
        @timeit("Async operation")
        async def async_function(x: int, y: int) -> int:
            await asyncio.sleep(MIN_EXECUTION_TIME)
            return x * y

        result = await async_function(3, 4)

        assert result == EXPECTED_MULTIPLY_RESULT
        mock_logger.log.assert_called_once()
        args = mock_logger.log.call_args[0]
        assert "Async operation" in args[2]

    @patch("ssmcp.timing.logger")
    def test_timeit_logs_on_exception(self, mock_logger: MagicMock) -> None:
        """Test that timeit still logs even when function raises exception."""
        @timeit("Failing operation")
        def failing_function() -> None:
            raise RuntimeError("Test failure")

        with pytest.raises(RuntimeError, match="Test failure"):
            failing_function()

        mock_logger.log.assert_called_once()
        args = mock_logger.log.call_args[0]
        assert "Failing operation" in args[2]
