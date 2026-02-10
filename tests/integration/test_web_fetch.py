"""Integration tests for web_fetch MCP tool.

These tests require:
1. The MCP server running (make up)

Run: make test
"""

from typing import Any

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError


class TestWebFetchTool:
    """Test web_fetch MCP tool."""

    async def test_fetch_valid_url(self, mcp_client: Client[Any]) -> None:
        """Test web_fetch returns content for a valid URL."""
        result = await mcp_client.call_tool(
            "web_fetch",
            {"url": "https://example.com"},
        )

        # The structured_content is wrapped in {'result': ...}
        structured = result.structured_content
        assert isinstance(structured, dict)
        assert "result" in structured

        data = structured["result"]
        assert isinstance(data, str)
        # Example.com should have "example" in the content
        assert "example" in data.lower()

    async def test_fetch_invalid_url(self, mcp_client: Client[Any]) -> None:
        """Test web_fetch raises ToolError for invalid URL."""
        with pytest.raises(ToolError):
            await mcp_client.call_tool(
                "web_fetch",
                {"url": "https://this-domain-does-not-exist-12345.com"},
            )

    async def test_fetch_empty_url(self, mcp_client: Client[Any]) -> None:
        """Test web_fetch raises ToolError for empty URL."""
        with pytest.raises(ToolError):
            await mcp_client.call_tool(
                "web_fetch",
                {"url": ""},
            )
