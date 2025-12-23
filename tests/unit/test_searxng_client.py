"""Unit tests for SearXNG client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ssmcp.searxng_client import SearXNGClient

# Expected number of results in test data
EXPECTED_RESULTS_COUNT = 2


class TestSearXNGClient:
    """Test SearXNG client functionality."""

    @pytest.fixture
    def client(self) -> SearXNGClient:
        """Create a SearXNG client for testing."""
        return SearXNGClient(search_url="http://test.com/search", timeout=10.0)

    async def test_search_handles_exception(self, client: SearXNGClient) -> None:
        """Test that search raises SearXNGError on connection errors."""
        with (
            patch.object(client._client, "get", side_effect=Exception("Connection error")),
            pytest.raises(Exception, match="Connection error"),
        ):
            await client.search("exception")

    async def test_search_success(self, client: SearXNGClient) -> None:
        """Test successful search returns list of results."""
        mock_results = [
            {"title": "Example 1", "url": "http://example.com", "content": "Content 1"},
            {"title": "Example 2", "url": "http://example2.com", "content": "Content 2"},
        ]

        mock_response = AsyncMock()
        mock_response.json = MagicMock(return_value={"results": mock_results})
        mock_response.raise_for_status = MagicMock()

        with patch.object(client._client, "get", return_value=mock_response):
            results = await client.search("test query")

        assert isinstance(results, list)
        assert len(results) == EXPECTED_RESULTS_COUNT
        assert results[0]["title"] == "Example 1"
        assert results[1]["url"] == "http://example2.com"

    async def test_search_empty_results(self, client: SearXNGClient) -> None:
        """Test search with no results returns empty list."""
        mock_response = AsyncMock()
        mock_response.json = MagicMock(return_value={"results": []})
        mock_response.raise_for_status = MagicMock()

        with patch.object(client._client, "get", return_value=mock_response):
            results = await client.search("no results query")

        assert results == []

    async def test_search_missing_results_key(self, client: SearXNGClient) -> None:
        """Test search handles missing results key by returning empty list."""
        mock_response = AsyncMock()
        mock_response.json = MagicMock(return_value={})
        mock_response.raise_for_status = MagicMock()

        with patch.object(client._client, "get", return_value=mock_response):
            results = await client.search("query")

        assert results == []
