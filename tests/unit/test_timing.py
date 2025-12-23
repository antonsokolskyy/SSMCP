"""Unit tests for timing utilities."""

import asyncio
import logging
import time
from typing import Any
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
    def test_timer_basic_usage(self, mock_logger: MagicMock) -> None:
        """Test basic timer context manager usage."""
        with timer("Test operation"):
            time.sleep(0.01)  # Small delay to ensure measurable time

        # Verify logger was called
        mock_logger.log.assert_called_once()
        args = mock_logger.log.call_args[0]

        # Check log level (default is INFO)
        assert args[0] == logging.INFO

        # Check message format string
        assert args[1] == "%s took %.4f seconds"

        # Check that time was measured (should be > 0)
        assert args[2] == "Test operation"
        assert isinstance(args[3], float)
        assert args[3] >= MIN_EXECUTION_TIME  # At least 10ms

    @patch("ssmcp.timing.logger")
    def test_timer_default_name(self, mock_logger: MagicMock) -> None:
        """Test timer with default operation name."""
        with timer():
            pass

        mock_logger.log.assert_called_once()
        args = mock_logger.log.call_args[0]
        assert args[2] == "Operation"

    @patch("ssmcp.timing.logger")
    def test_timer_custom_log_level(self, mock_logger: MagicMock) -> None:
        """Test timer with custom log level."""
        with timer("Debug operation", log_level=logging.DEBUG):
            pass

        mock_logger.log.assert_called_once()
        args = mock_logger.log.call_args[0]
        assert args[0] == logging.DEBUG

    @patch("ssmcp.timing.logger")
    def test_timer_with_exception(self, mock_logger: MagicMock) -> None:
        """Test timer still logs even when exception is raised."""
        with pytest.raises(ValueError, match="Test error"), timer("Error operation"):
            raise ValueError("Test error")

        # Verify logger was still called (in finally block)
        mock_logger.log.assert_called_once()
        args = mock_logger.log.call_args[0]
        assert args[2] == "Error operation"

    @patch("ssmcp.timing.logger")
    def test_timer_measures_time_accurately(self, mock_logger: MagicMock) -> None:
        """Test that timer measures time with reasonable accuracy."""
        sleep_duration = 0.05  # 50ms

        with timer("Timed operation"):
            time.sleep(sleep_duration)

        mock_logger.log.assert_called_once()
        args = mock_logger.log.call_args[0]
        measured_time = args[3]

        # Time should be approximately sleep_duration (with some tolerance)
        assert measured_time >= sleep_duration
        assert measured_time < sleep_duration + 0.02  # Allow 20ms tolerance


class TestTimeit:
    """Test timeit decorator."""

    @patch("ssmcp.timing.logger")
    def test_timeit_sync_function(self, mock_logger: MagicMock) -> None:
        """Test timeit decorator with synchronous function."""
        @timeit()
        def sync_function(x: int, y: int) -> int:
            time.sleep(0.01)
            return x + y

        result = sync_function(2, 3)

        # Verify function works correctly
        assert result == EXPECTED_SUM_RESULT

        # Verify logging
        mock_logger.log.assert_called_once()
        args = mock_logger.log.call_args[0]
        assert args[0] == logging.INFO
        assert "sync_function" in args[2]  # Function name in operation name
        assert isinstance(args[3], float)
        assert args[3] >= MIN_EXECUTION_TIME

    @patch("ssmcp.timing.logger")
    async def test_timeit_async_function(self, mock_logger: MagicMock) -> None:
        """Test timeit decorator with asynchronous function."""
        @timeit()
        async def async_function(x: int, y: int) -> int:
            await asyncio.sleep(0.01)
            return x * y

        result = await async_function(3, 4)

        # Verify function works correctly
        assert result == EXPECTED_MULTIPLY_RESULT

        # Verify logging
        mock_logger.log.assert_called_once()
        args = mock_logger.log.call_args[0]
        assert args[0] == logging.INFO
        assert "async_function" in args[2]
        assert isinstance(args[3], float)
        assert args[3] >= MIN_EXECUTION_TIME

    @patch("ssmcp.timing.logger")
    def test_timeit_custom_name(self, mock_logger: MagicMock) -> None:
        """Test timeit decorator with custom operation name."""
        @timeit(name="Custom operation")
        def some_function() -> str:
            return "result"

        result = some_function()

        assert result == "result"
        mock_logger.log.assert_called_once()
        args = mock_logger.log.call_args[0]
        assert args[2] == "Custom operation"

    @patch("ssmcp.timing.logger")
    def test_timeit_custom_log_level(self, mock_logger: MagicMock) -> None:
        """Test timeit decorator with custom log level."""
        @timeit(log_level=logging.WARNING)
        def warning_function() -> None:
            pass

        warning_function()

        mock_logger.log.assert_called_once()
        args = mock_logger.log.call_args[0]
        assert args[0] == logging.WARNING

    @patch("ssmcp.timing.logger")
    def test_timeit_default_name_includes_module(self, mock_logger: MagicMock) -> None:
        """Test that default operation name includes module and function name."""
        @timeit()
        def my_function() -> None:
            pass

        my_function()

        mock_logger.log.assert_called_once()
        args = mock_logger.log.call_args[0]
        operation_name = args[2]

        # Should include module name
        assert "__main__" in operation_name or "test_timing" in operation_name
        assert "my_function" in operation_name

    @patch("ssmcp.timing.logger")
    def test_timeit_preserves_function_metadata(self, mock_logger: MagicMock) -> None:
        """Test that timeit preserves function metadata via @wraps."""
        @timeit()
        def documented_function(x: int) -> int:
            """This is a docstring."""
            return x * 2

        # Check that function metadata is preserved
        assert documented_function.__name__ == "documented_function"
        assert documented_function.__doc__ == "This is a docstring."

    @patch("ssmcp.timing.logger")
    def test_timeit_sync_with_exception(self, mock_logger: MagicMock) -> None:
        """Test timeit decorator still logs when sync function raises exception."""
        @timeit(name="Failing sync function")
        def failing_function() -> None:
            raise RuntimeError("Sync failure")

        with pytest.raises(RuntimeError, match="Sync failure"):
            failing_function()

        # Verify logging occurred despite exception
        mock_logger.log.assert_called_once()
        args = mock_logger.log.call_args[0]
        assert args[2] == "Failing sync function"

    @patch("ssmcp.timing.logger")
    async def test_timeit_async_with_exception(self, mock_logger: MagicMock) -> None:
        """Test timeit decorator still logs when async function raises exception."""
        @timeit(name="Failing async function")
        async def failing_async_function() -> None:
            raise RuntimeError("Async failure")

        with pytest.raises(RuntimeError, match="Async failure"):
            await failing_async_function()

        # Verify logging occurred despite exception
        mock_logger.log.assert_called_once()
        args = mock_logger.log.call_args[0]
        assert args[2] == "Failing async function"

    @patch("ssmcp.timing.logger")
    def test_timeit_sync_with_args_and_kwargs(self, mock_logger: MagicMock) -> None:
        """Test timeit decorator preserves function arguments."""
        @timeit()
        def complex_function(a: int, b: int, c: int = 10, d: str = "default") -> dict[str, Any]:
            return {"a": a, "b": b, "c": c, "d": d}

        result = complex_function(1, 2, c=20, d="custom")

        assert result == {"a": 1, "b": 2, "c": 20, "d": "custom"}
        mock_logger.log.assert_called_once()

    @patch("ssmcp.timing.logger")
    async def test_timeit_async_with_args_and_kwargs(
        self, mock_logger: MagicMock
    ) -> None:
        """Test timeit decorator preserves async function arguments."""
        @timeit()
        async def async_complex_function(
            a: str, b: int, c: bool = True
        ) -> dict[str, Any]:
            await asyncio.sleep(0.001)
            return {"a": a, "b": b, "c": c}

        result = await async_complex_function("test", 42, c=False)

        assert result == {"a": "test", "b": 42, "c": False}
        mock_logger.log.assert_called_once()

    @patch("ssmcp.timing.logger")
    def test_timeit_measures_time_accurately_sync(
        self, mock_logger: MagicMock
    ) -> None:
        """Test that timeit measures sync function time accurately."""
        sleep_duration = 0.05

        @timeit()
        def timed_function() -> None:
            time.sleep(sleep_duration)

        timed_function()

        mock_logger.log.assert_called_once()
        args = mock_logger.log.call_args[0]
        measured_time = args[3]

        # Time should be approximately sleep_duration
        assert measured_time >= sleep_duration
        assert measured_time < sleep_duration + 0.02

    @patch("ssmcp.timing.logger")
    async def test_timeit_measures_time_accurately_async(
        self, mock_logger: MagicMock
    ) -> None:
        """Test that timeit measures async function time accurately."""
        sleep_duration = 0.05

        @timeit()
        async def async_timed_function() -> None:
            await asyncio.sleep(sleep_duration)

        await async_timed_function()

        mock_logger.log.assert_called_once()
        args = mock_logger.log.call_args[0]
        measured_time = args[3]

        # Time should be approximately sleep_duration
        assert measured_time >= sleep_duration
        assert measured_time < sleep_duration + 0.02

    @patch("ssmcp.timing.logger")
    def test_timeit_combined_name_and_log_level(self, mock_logger: MagicMock) -> None:
        """Test timeit decorator with both custom name and log level."""
        @timeit(name="Important operation", log_level=logging.ERROR)
        def important_function() -> str:
            return "done"

        result = important_function()

        assert result == "done"
        mock_logger.log.assert_called_once()
        args = mock_logger.log.call_args[0]
        assert args[0] == logging.ERROR
        assert args[2] == "Important operation"
