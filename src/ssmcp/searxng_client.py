"""SearXNG client for performing web searches."""

from typing import Any

import httpx

from ssmcp.exceptions import SearXNGError
from ssmcp.logger import logger


class SearXNGClient:
    """HTTP client for SearXNG search API.

    Uses a persistent httpx client to reuse connections across requests.
    """

    def __init__(self, search_url: str, timeout: float) -> None:
        """Initialize the SearXNG client.

        Args:
            search_url: SearXNG search endpoint URL.
            timeout: Request timeout in seconds.

        """
        self._search_url = search_url
        self._timeout = timeout
        self._client = httpx.AsyncClient(timeout=self._timeout)

    async def search(self, query: str) -> list[dict[str, Any]]:
        """Query the search engine and return structured results.

        Args:
            query: Search query string.

        Returns:
            List of result dictionaries with 'title', 'url', and 'snippet'.

        """
        params = {"q": query, "format": "json"}

        try:
            logger.debug("[SEARCH STARTED] for query: %s", query)
            resp = await self._client.get(self._search_url, params=params)
            resp.raise_for_status()

        except httpx.HTTPStatusError as e:
            raise SearXNGError(f"Service returned error: {e}") from e

        except httpx.RequestError as e:
            raise SearXNGError(f"Service did not respond: {e}") from e

        try:
            data = resp.json()
        except ValueError as e:
            raise SearXNGError(f"Invalid JSON response: {e}") from e

        results: list[dict[str, Any]] = data.get("results", [])
        logger.debug("Found %d results", len(results))
        return results

    async def close(self) -> None:
        """Close the HTTP client and release resources."""
        logger.debug("Closing SearXNG client")
        await self._client.aclose()
