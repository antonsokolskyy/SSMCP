"""Pytest configuration for integration tests.

These tests require the server and external services to be running.
Run: make server (in one terminal)
Then: pytest tests/integration (in another terminal)
"""

from collections.abc import AsyncGenerator
from typing import Any

import pytest
from fastmcp import Client

from ssmcp.config import settings


@pytest.fixture
async def mcp_client() -> AsyncGenerator[Client[Any]]:
    """Provide an MCP client connected to the server."""
    async with Client(f"http://{settings.host}:{settings.port}/mcp") as client:
        yield client
