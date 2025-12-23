"""Integration tests for youtube_get_subtitles MCP tool.

These tests require:
1. The MCP server running (make server)

Run: pytest tests/integration/test_youtube_subtitles.py
"""

from typing import Any

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError


class TestYouTubeSubtitlesTool:
    """Test youtube_get_subtitles MCP tool."""

    async def test_get_subtitles_with_english(self, mcp_client: Client[Any]) -> None:
        """Test downloading subtitles from a YouTube video."""
        result = await mcp_client.call_tool(
            "youtube_get_subtitles",
            {"url": "https://www.youtube.com/watch?v=jNQXAC9IVRw"},
        )

        # The structured_content is wrapped in {'result': ...}
        structured = result.structured_content
        assert isinstance(structured, dict)
        assert "result" in structured

        subtitles = structured["result"]
        assert isinstance(subtitles, str)
        # Should have timestamp format
        assert "[" in subtitles and "]" in subtitles

    async def test_get_subtitles_invalid_url(self, mcp_client: Client[Any]) -> None:
        """Test that invalid URL raises ToolError."""
        with pytest.raises(ToolError):
            await mcp_client.call_tool(
                "youtube_get_subtitles",
                {"url": "https://www.example.com/not-a-video"},
            )

    async def test_get_subtitles_empty_url(self, mcp_client: Client[Any]) -> None:
        """Test that empty URL raises ToolError."""
        with pytest.raises(ToolError):
            await mcp_client.call_tool(
                "youtube_get_subtitles",
                {"url": ""},
            )
