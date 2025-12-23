"""Unit tests for Extractor module."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ssmcp.exceptions import Crawl4AIError, ExtractorError
from ssmcp.parser.extractor import ExtractionResult, Extractor


@pytest.fixture
def mock_settings() -> MagicMock:
    """Create mock settings for testing."""
    settings = MagicMock()
    settings.crawl4ai_browser_pool_size = 2
    settings.crawl4ai_viewport_width = 1920
    settings.crawl4ai_viewport_height = 1080
    settings.crawl4ai_wait_until = "networkidle"
    settings.crawl4ai_page_timeout = 30000
    settings.crawl4ai_delay_before_return_html = 0.5
    settings.crawl4ai_scroll_delay = 0.2
    settings.crawl4ai_max_scroll_steps = 5
    settings.crawl4ai_word_count_threshold = 50
    settings.crawl4ai_excluded_tags = "script,style,nav,footer"
    settings.crawl4ai_exclude_external_links = True
    settings.crawl4ai_table_score_threshold = 5
    settings.crawl4ai_cache_mode = "bypass"
    settings.extraction_html_type = "fit_html"
    return settings


class TestExtractor:
    """Test Extractor class functionality."""

    @pytest.mark.asyncio
    async def test_start_initializes_browser_pool(
        self, mock_settings: MagicMock
    ) -> None:
        """Test that start() initializes the browser pool."""
        extractor = Extractor(mock_settings)

        with patch("ssmcp.parser.extractor.AsyncWebCrawler") as mock_crawler_class:
            mock_crawler = AsyncMock()
            mock_crawler_class.return_value = mock_crawler

            await extractor.start()

            # Should create 2 crawlers (pool size)
            pool_size = mock_settings.crawl4ai_browser_pool_size
            assert mock_crawler_class.call_count == pool_size
            assert mock_crawler.start.call_count == pool_size
            assert len(extractor._crawlers) == pool_size
            assert extractor._crawler_queue.qsize() == pool_size

    @pytest.mark.asyncio
    async def test_close_cleans_up_browser_pool(
        self, mock_settings: MagicMock
    ) -> None:
        """Test that close() properly cleans up all browsers."""
        extractor = Extractor(mock_settings)

        with patch("ssmcp.parser.extractor.AsyncWebCrawler") as mock_crawler_class:
            mock_crawler = AsyncMock()
            mock_crawler_class.return_value = mock_crawler

            await extractor.start()
            await extractor.close()

            pool_size = mock_settings.crawl4ai_browser_pool_size
            assert mock_crawler.close.call_count == pool_size
            assert len(extractor._crawlers) == 0
            assert extractor._crawler_queue.qsize() == 0

    @pytest.mark.asyncio
    async def test_extract_html_url_mode(self, mock_settings: MagicMock) -> None:
        """Test extracting HTML from a URL."""
        extractor = Extractor(mock_settings)

        with patch("ssmcp.parser.extractor.AsyncWebCrawler") as mock_crawler_class:
            # Setup mock crawler
            mock_crawler = AsyncMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.html = "<html><body>Raw content</body></html>"
            mock_result.fit_html = "<body>Fit content</body>"
            mock_result.cleaned_html = "<body>Cleaned content</body>"
            mock_crawler.arun.return_value = mock_result
            mock_crawler_class.return_value = mock_crawler

            await extractor.start()

            result = await extractor.extract_html("https://example.com")

            assert isinstance(result, ExtractionResult)
            assert result.raw_html == "<html><body>Raw content</body></html>"
            assert result.selected_html == "<body>Fit content</body>"

            # Verify crawler was called with URL
            mock_crawler.arun.assert_called_once()
            call_kwargs = mock_crawler.arun.call_args
            assert call_kwargs.kwargs["url"] == "https://example.com"

    @pytest.mark.asyncio
    async def test_extract_html_raw_mode(self, mock_settings: MagicMock) -> None:
        """Test extracting/cleaning raw HTML string."""
        extractor = Extractor(mock_settings)

        with patch("ssmcp.parser.extractor.AsyncWebCrawler") as mock_crawler_class:
            mock_crawler = AsyncMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.html = "<html><body>Content</body></html>"
            mock_result.fit_html = "<body>Processed</body>"
            mock_result.cleaned_html = "<body>Cleaned</body>"
            mock_crawler.arun.return_value = mock_result
            mock_crawler_class.return_value = mock_crawler

            await extractor.start()

            html_input = "<html><body>Test</body></html>"
            await extractor.extract_html(html_input)

            # Should be called with 'raw:' prefix
            call_kwargs = mock_crawler.arun.call_args
            assert call_kwargs.kwargs["url"] == f"raw:{html_input}"

    @pytest.mark.asyncio
    async def test_extract_html_uses_fit_html_by_default(
        self, mock_settings: MagicMock
    ) -> None:
        """Test that fit_html is used when extraction_html_type is 'fit_html'."""
        mock_settings.extraction_html_type = "fit_html"
        extractor = Extractor(mock_settings)

        with patch("ssmcp.parser.extractor.AsyncWebCrawler") as mock_crawler_class:
            mock_crawler = AsyncMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.html = "<html>raw</html>"
            mock_result.fit_html = "<body>fit content</body>"
            mock_result.cleaned_html = "<body>cleaned content</body>"
            mock_crawler.arun.return_value = mock_result
            mock_crawler_class.return_value = mock_crawler

            await extractor.start()

            result = await extractor.extract_html("https://example.com")

            assert result.selected_html == "<body>fit content</body>"

    @pytest.mark.asyncio
    async def test_extract_html_uses_cleaned_html_when_configured(
        self, mock_settings: MagicMock
    ) -> None:
        """Test that cleaned_html is used when configured."""
        mock_settings.extraction_html_type = "cleaned_html"
        extractor = Extractor(mock_settings)

        with patch("ssmcp.parser.extractor.AsyncWebCrawler") as mock_crawler_class:
            mock_crawler = AsyncMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.html = "<html>raw</html>"
            mock_result.fit_html = "<body>fit content</body>"
            mock_result.cleaned_html = "<body>cleaned content</body>"
            mock_crawler.arun.return_value = mock_result
            mock_crawler_class.return_value = mock_crawler

            await extractor.start()

            result = await extractor.extract_html("https://example.com")

            assert result.selected_html == "<body>cleaned content</body>"

    @pytest.mark.asyncio
    async def test_extract_html_crawl4ai_failure(
        self, mock_settings: MagicMock
    ) -> None:
        """Test handling when Crawl4AI reports failure."""
        extractor = Extractor(mock_settings)

        with patch("ssmcp.parser.extractor.AsyncWebCrawler") as mock_crawler_class:
            mock_crawler = AsyncMock()
            mock_result = MagicMock()
            mock_result.success = False
            mock_result.error_message = "Page load timeout"
            mock_crawler.arun.return_value = mock_result
            mock_crawler_class.return_value = mock_crawler

            await extractor.start()

            with pytest.raises(Crawl4AIError, match="Page load timeout"):
                await extractor.extract_html("https://example.com")

    @pytest.mark.asyncio
    async def test_extract_html_no_content_extracted(
        self, mock_settings: MagicMock
    ) -> None:
        """Test error when no HTML content is extracted."""
        extractor = Extractor(mock_settings)

        with patch("ssmcp.parser.extractor.AsyncWebCrawler") as mock_crawler_class:
            mock_crawler = AsyncMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.html = ""
            mock_result.fit_html = ""
            mock_result.cleaned_html = ""
            mock_crawler.arun.return_value = mock_result
            mock_crawler_class.return_value = mock_crawler

            await extractor.start()

            with pytest.raises(ExtractorError, match="No HTML content extracted"):
                await extractor.extract_html("https://example.com")

    @pytest.mark.asyncio
    async def test_browser_pool_queue_management(
        self, mock_settings: MagicMock
    ) -> None:
        """Test that crawlers are properly returned to the queue."""
        mock_settings.crawl4ai_browser_pool_size = 1
        extractor = Extractor(mock_settings)

        with patch("ssmcp.parser.extractor.AsyncWebCrawler") as mock_crawler_class:
            mock_crawler = AsyncMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.html = "<html>content</html>"
            mock_result.fit_html = "<body>content</body>"
            mock_crawler.arun.return_value = mock_result
            mock_crawler_class.return_value = mock_crawler

            await extractor.start()

            # Queue should have 1 crawler
            assert extractor._crawler_queue.qsize() == 1

            # Extract HTML (should take and return crawler)
            await extractor.extract_html("https://example.com")

            # Queue should still have 1 crawler
            assert extractor._crawler_queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_crawler_returned_even_on_error(
        self, mock_settings: MagicMock
    ) -> None:
        """Test that crawler is returned to queue even when extraction fails."""
        mock_settings.crawl4ai_browser_pool_size = 1
        extractor = Extractor(mock_settings)

        with patch("ssmcp.parser.extractor.AsyncWebCrawler") as mock_crawler_class:
            mock_crawler = AsyncMock()
            mock_result = MagicMock()
            mock_result.success = False
            mock_result.error_message = "Error"
            mock_crawler.arun.return_value = mock_result
            mock_crawler_class.return_value = mock_crawler

            await extractor.start()

            assert extractor._crawler_queue.qsize() == 1

            with pytest.raises(Crawl4AIError):
                await extractor.extract_html("https://example.com")

            # Crawler should still be returned to queue
            assert extractor._crawler_queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_crawler_config_uses_settings(
        self, mock_settings: MagicMock
    ) -> None:
        """Test that crawler configuration uses values from settings."""
        extractor = Extractor(mock_settings)

        config = extractor._get_crawler_config()

        assert config.wait_until == mock_settings.crawl4ai_wait_until
        assert config.page_timeout == mock_settings.crawl4ai_page_timeout
        assert config.delay_before_return_html == mock_settings.crawl4ai_delay_before_return_html
        assert config.scroll_delay == mock_settings.crawl4ai_scroll_delay
        assert config.max_scroll_steps == mock_settings.crawl4ai_max_scroll_steps
        assert config.word_count_threshold == mock_settings.crawl4ai_word_count_threshold
        assert config.excluded_tags == ["script", "style", "nav", "footer"]
        assert config.exclude_external_links is True
        assert config.table_score_threshold == mock_settings.crawl4ai_table_score_threshold
        assert config.cache_mode == mock_settings.crawl4ai_cache_mode

    @pytest.mark.asyncio
    async def test_extraction_result_fallback_to_empty_strings(
        self, mock_settings: MagicMock
    ) -> None:
        """Test that extraction result handles None values gracefully."""
        extractor = Extractor(mock_settings)

        with patch("ssmcp.parser.extractor.AsyncWebCrawler") as mock_crawler_class:
            mock_crawler = AsyncMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.html = "<html>content</html>"
            mock_result.fit_html = None  # None instead of empty string
            mock_result.cleaned_html = None
            mock_crawler.arun.return_value = mock_result
            mock_crawler_class.return_value = mock_crawler

            await extractor.start()

            result = await extractor.extract_html("https://example.com")

            # Should convert None to empty string
            assert result.raw_html == "<html>content</html>"
            assert result.selected_html == ""

    @pytest.mark.asyncio
    async def test_parallel_url_extraction(self, mock_settings: MagicMock) -> None:
        """Test that multiple URLs are processed in parallel using the browser pool."""
        pool_size = 3
        num_urls = 5
        mock_settings.crawl4ai_browser_pool_size = pool_size
        extractor = Extractor(mock_settings)

        # Track which crawlers are currently in use
        active_crawlers = set()
        max_concurrent = 0
        lock = asyncio.Lock()

        with patch("ssmcp.parser.extractor.AsyncWebCrawler") as mock_crawler_class:
            # Create unique mock crawlers for each pool instance
            created_crawlers = []

            def create_crawler(*args: Any, **kwargs: Any) -> AsyncMock:
                mock_crawler = AsyncMock()

                async def mock_arun(**kw: Any) -> MagicMock:
                    """Mock arun that simulates work and tracks concurrency."""
                    crawler_id = id(mock_crawler)

                    async with lock:
                        active_crawlers.add(crawler_id)
                        nonlocal max_concurrent
                        max_concurrent = max(max_concurrent, len(active_crawlers))

                    # Simulate some async work
                    await asyncio.sleep(0.1)

                    async with lock:
                        active_crawlers.discard(crawler_id)

                    # Return successful result
                    result = MagicMock()
                    result.success = True
                    result.html = f"<html>content from {kw.get('url', 'unknown')}</html>"
                    result.fit_html = "<body>fit content</body>"
                    result.cleaned_html = "<body>cleaned content</body>"
                    return result

                mock_crawler.arun.side_effect = mock_arun
                created_crawlers.append(mock_crawler)
                return mock_crawler

            mock_crawler_class.side_effect = create_crawler

            await extractor.start()

            # Extract multiple URLs concurrently
            urls = [
                "https://example1.com",
                "https://example2.com",
                "https://example3.com",
                "https://example4.com",
                "https://example5.com",
            ]

            results = await asyncio.gather(
                *[extractor.extract_html(url) for url in urls]
            )

            # Verify all extractions succeeded
            assert len(results) == num_urls
            for result in results:
                assert isinstance(result, ExtractionResult)
                assert result.raw_html.startswith("<html>content from")
                assert result.selected_html == "<body>fit content</body>"

            # Verify parallel execution occurred
            # With pool size 3 and 5 URLs, we should have had at least 3 concurrent
            assert max_concurrent >= pool_size, (
                f"Expected at least {pool_size} concurrent extractions, but got {max_concurrent}. "
                "URLs should be processed in parallel using the browser pool."
            )

            # Verify all crawlers are back in the queue
            assert extractor._crawler_queue.qsize() == pool_size
