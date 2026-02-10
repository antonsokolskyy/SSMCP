"""Pytest configuration for integration tests.

These tests require the server and external services to be running.
Run: make up
Then: make test
"""

from collections.abc import AsyncGenerator
from typing import Any

import pytest
from fastmcp import Client

from ssmcp.config import settings


@pytest.fixture
async def mcp_client() -> AsyncGenerator[Client[Any]]:
    """Provide an MCP client connected to the server."""
    async with Client(
        f"http://{settings.host}:{settings.port}/mcp",
        timeout=60.0,
    ) as client:
        yield client
