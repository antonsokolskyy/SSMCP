"""Unit tests for SearXNG client."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from ssmcp.exceptions import SearXNGError
from ssmcp.searxng_client import SearXNGClient

# Test constants
EXPECTED_RESULTS_COUNT = 2
TEST_TIMEOUT = 10.0
SEARCH_URL = "http://test.com/search"


class TestSearXNGClient:
    """Test SearXNG client functionality."""

    @pytest.fixture
    def client(self) -> SearXNGClient:
        """Create a SearXNG client for testing."""
        return SearXNGClient(search_url=SEARCH_URL, timeout=TEST_TIMEOUT)

    async def test_search_unexpected_exception_not_wrapped(self, client: SearXNGClient) -> None:
        """Test that unexpected exceptions are raised as-is (not wrapped).

        Note: The SearXNG client only wraps httpx exceptions (HTTPStatusError, RequestError).
        Other exceptions bubble up unchanged.
        """
        with (
            patch.object(
                client._client,
                "get",
                side_effect=RuntimeError("Unexpected error"),
            ),
            pytest.raises(RuntimeError, match="Unexpected error"),
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

    async def test_search_http_status_error(self, client: SearXNGClient) -> None:
        """Test that HTTP status errors raise SearXNGError."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch.object(
            client._client,
            "get",
            side_effect=httpx.HTTPStatusError(
                "Server error",
                request=MagicMock(),
                response=mock_response,
            ),
        ), pytest.raises(SearXNGError, match="Service returned error"):
            await client.search("query")

    async def test_search_request_error(self, client: SearXNGClient) -> None:
        """Test that request errors (connection issues) raise SearXNGError."""
        with patch.object(
            client._client,
            "get",
            side_effect=httpx.RequestError("Connection refused", request=MagicMock()),
        ), pytest.raises(SearXNGError, match="Service did not respond"):
            await client.search("query")

    async def test_search_invalid_json_response(self, client: SearXNGClient) -> None:
        """Test that invalid JSON response raises SearXNGError."""
        mock_response = AsyncMock()
        mock_response.json = MagicMock(side_effect=ValueError("Invalid JSON"))
        mock_response.raise_for_status = MagicMock()

        with (
            patch.object(client._client, "get", return_value=mock_response),
            pytest.raises(SearXNGError, match="Invalid JSON response"),
        ):
            await client.search("query")

    async def test_close_client(self, client: SearXNGClient) -> None:
        """Test that close properly closes the HTTP client."""
        with patch.object(client._client, "aclose", new_callable=AsyncMock) as mock_close:
            await client.close()
            mock_close.assert_called_once()
