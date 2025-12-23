"""Timing utilities for measuring code execution time."""

import asyncio
import logging
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from functools import wraps
from typing import ParamSpec, TypeVar, cast

from ssmcp.logger import logger

__all__ = ["timeit", "timer"]

P = ParamSpec("P")
R = TypeVar("R")


@contextmanager
def timer(name: str = "Operation", log_level: int = logging.INFO) -> Generator[None]:
    """Context manager for timing code blocks.

    Args:
        name: Name of the operation being timed
        log_level: Logging level to use (default: INFO)

    Example:
        >>> with timer("Database query"):
        ...     result = execute_query()

        >>> with timer("API call", logging.DEBUG):
        ...     data = fetch_data()

    """
    start_time = time.perf_counter()
    try:
        yield
    finally:
        elapsed_time = time.perf_counter() - start_time
        logger.log(log_level, "%s took %.4f seconds", name, elapsed_time)


def timeit(
    name: str | None = None, log_level: int = logging.INFO
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Time function execution (supports both sync and async).

    Args:
        name: Custom name for the operation (default: uses function name)
        log_level: Logging level to use (default: INFO)

    Example:
        >>> @timeit()
        ... def process_data():
        ...     # your code here
        ...     pass

        >>> @timeit("Custom operation name")
        ... async def fetch_and_process():
        ...     # async code here
        ...     pass

        >>> @timeit(log_level=logging.DEBUG)
        ... def internal_helper():
        ...     # your code here
        ...     pass

        >>> # Works with MCP tools:
        >>> @mcp.tool()
        >>> @timeit()
        >>> async def web_search(query: str):
        ...     # your code here
        ...     pass

    """
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        # Check if function is async
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                operation_name = name or f"{func.__module__}.{func.__name__}"
                start_time = time.perf_counter()
                try:
                    result = await func(*args, **kwargs)
                    return cast("R", result)
                finally:
                    elapsed_time = time.perf_counter() - start_time
                    logger.log(log_level, "%s took %.4f seconds", operation_name, elapsed_time)
            return async_wrapper  # type: ignore[return-value]
        else:
            @wraps(func)
            def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                operation_name = name or f"{func.__module__}.{func.__name__}"
                start_time = time.perf_counter()
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    elapsed_time = time.perf_counter() - start_time
                    logger.log(log_level, "%s took %.4f seconds", operation_name, elapsed_time)
            return sync_wrapper
    return decorator
