"""Integration tests for web_search MCP tool.

These tests require:
1. The MCP server running (make server)
2. External services accessible (SearXNG)

Run: pytest tests/integration/test_web_search.py
"""

from typing import Any

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError


class TestWebSearchTool:
    """Test web_search MCP tool."""

    async def test_search_with_valid_query(self, mcp_client: Client[Any]) -> None:
        """Test web_search returns results for a valid query."""
        result = await mcp_client.call_tool(
            "web_search",
            {"query": "Python programming"},
        )

        # The structured_content is wrapped in {'result': ...}
        structured = result.structured_content
        assert isinstance(structured, dict)
        assert "result" in structured

        data = structured["result"]
        assert isinstance(data, list)
        assert len(data) > 0

        # Verify each result has required fields
        for item in data:
            assert "url" in item
            assert "content" in item
            assert isinstance(item["url"], str)
            assert isinstance(item["content"], str)

    async def test_search_with_empty_query(self, mcp_client: Client[Any]) -> None:
        """Test web_search raises ToolError for empty query."""
        with pytest.raises(ToolError):
            await mcp_client.call_tool(
                "web_search",
                {"query": ""},
            )
