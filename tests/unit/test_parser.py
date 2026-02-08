"""Unit tests for Parser module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ssmcp.exceptions import SSMCPError
from ssmcp.parser.extractor import ExtractionResult
from ssmcp.parser.parser import Parser


@pytest.fixture
def mock_settings() -> MagicMock:
    """Create mock settings for testing."""
    settings = MagicMock()
    settings.css_selector_priority_list = "article, main, #content"
    settings.css_selector_min_words = 50
    settings.junk_filter_enabled = True
    settings.junk_filter_letter_ratio_threshold = 0.3
    return settings


@pytest.fixture
def mock_context() -> AsyncMock:
    """Create a mock FastMCP Context for testing."""
    ctx = AsyncMock()
    ctx.report_progress = AsyncMock()
    return ctx


class TestParser:
    """Test Parser class functionality."""

    async def test_parse_pages_single_url_success(
        self, mock_settings: MagicMock, mock_context: AsyncMock
    ) -> None:
        """Test parsing a single URL successfully."""
        parser = Parser(mock_settings)

        # Mock the pipeline components
        with (
            patch.object(parser, "_run_pipeline") as mock_pipeline,
        ):
            mock_pipeline.return_value = "# Converted Markdown Content"

            result = await parser.parse_pages(["https://example.com"], mock_context)

            assert "https://example.com" in result
            assert result["https://example.com"] == "# Converted Markdown Content"
            mock_context.report_progress.assert_called()

    async def test_parse_pages_multiple_urls(
        self, mock_settings: MagicMock, mock_context: AsyncMock
    ) -> None:
        """Test parsing multiple URLs concurrently."""
        parser = Parser(mock_settings)

        urls = [
            "https://example1.com",
            "https://example2.com",
            "https://example3.com",
        ]

        with patch.object(parser, "_run_pipeline") as mock_pipeline:
            # Return different content for each URL
            async def side_effect(url: str) -> str:
                return f"# Content from {url}"

            mock_pipeline.side_effect = side_effect

            result = await parser.parse_pages(urls, mock_context)

            expected_count = 3
            assert len(result) == expected_count
            for url in urls:
                assert url in result
                assert f"# Content from {url}" == result[url]

    async def test_parse_pages_handles_pipeline_failure(
        self, mock_settings: MagicMock, mock_context: AsyncMock
    ) -> None:
        """Test that pipeline failures are skipped (SSMCPError exceptions)."""
        parser = Parser(mock_settings)

        with patch.object(parser, "_run_pipeline") as mock_pipeline:
            mock_pipeline.side_effect = SSMCPError("Extraction failed")

            result = await parser.parse_pages(["https://failing.com"], mock_context)

            # parse_pages itself doesn't fail, but skips failed URLs
            assert "https://failing.com" not in result

    async def test_parse_pages_handles_exception(
        self, mock_settings: MagicMock, mock_context: AsyncMock
    ) -> None:
        """Test that non-SSMCP exceptions are re-raised."""
        parser = Parser(mock_settings)

        with patch.object(parser, "_run_pipeline") as mock_pipeline:
            mock_pipeline.side_effect = ValueError("Unexpected error")

            with pytest.raises(ValueError, match="Unexpected error"):
                await parser.parse_pages(["https://error.com"], mock_context)

    async def test_parse_pages_progress_reporting(
        self, mock_settings: MagicMock, mock_context: AsyncMock
    ) -> None:
        """Test that progress is properly reported with correct values."""
        parser = Parser(mock_settings)

        with patch.object(parser, "_run_pipeline") as mock_pipeline:
            mock_pipeline.return_value = "# Content"

            await parser.parse_pages(["https://example.com"], mock_context)

            # Verify progress calls with actual arguments
            calls = mock_context.report_progress.call_args_list
            expected_calls = 2
            assert len(calls) == expected_calls

            # Initial progress: (0, 1, "Starting parse of 1 page(s)")
            assert calls[0][0][0] == 0  # progress
            assert calls[0][0][1] == 1  # total
            assert calls[0][0][2] == "Starting parse of 1 page(s)"

            # Completion: (1, 1, "Completed 1/1: https://example.com")
            assert calls[1][0][0] == 1  # progress
            assert calls[1][0][1] == 1  # total
            assert "Completed 1/1: https://example.com" in calls[1][0][2]

    async def test_parse_pages_progress_reporting_multiple_urls(
        self, mock_settings: MagicMock, mock_context: AsyncMock
    ) -> None:
        """Test that progress is properly reported for multiple URLs."""
        parser = Parser(mock_settings)

        urls = [
            "https://example1.com",
            "https://example2.com",
            "https://example3.com",
        ]
        total_urls = len(urls)

        with patch.object(parser, "_run_pipeline") as mock_pipeline:
            mock_pipeline.return_value = "# Content"

            await parser.parse_pages(urls, mock_context)

            # Verify progress calls
            calls = mock_context.report_progress.call_args_list
            # Should have: 1 initial + 3 completions = 4 calls
            expected_calls = total_urls + 1
            assert len(calls) == expected_calls

            # Initial progress
            assert calls[0][0][0] == 0
            assert calls[0][0][1] == total_urls
            assert f"Starting parse of {total_urls} page(s)" in calls[0][0][2]

            # Each completion should increment progress
            for i in range(1, total_urls + 1):
                assert calls[i][0][0] == i  # progress: 1, 2, 3
                assert calls[i][0][1] == total_urls  # total: always 3
                assert f"Completed {i}/{total_urls}:" in calls[i][0][2]

    async def test_run_pipeline_with_filter_match(
        self, mock_settings: MagicMock
    ) -> None:
        """Test the full pipeline when CSS filter matches content."""
        parser = Parser(mock_settings)

        raw_html = "<html><article>" + " ".join(["word"] * 60) + "</article></html>"
        selected_html = "<article>" + " ".join(["word"] * 60) + "</article>"

        with (
            patch.object(parser._extractor, "extract_html") as mock_extract,
            patch.object(parser._filter, "apply_all") as mock_filter,
            patch.object(parser._markdown_generator, "convert") as mock_convert,
        ):
            # First extraction
            mock_extract.return_value = ExtractionResult(
                raw_html=raw_html, cleaned_html=selected_html
            )
            # Filter matches
            mock_filter.return_value = "<article>filtered content</article>"
            # Markdown conversion
            mock_convert.return_value = "# Markdown Output"

            result = await parser._run_pipeline("https://example.com")

            assert result == "# Markdown Output"
            # Should call extract twice (once for URL, once for filtered content)
            expected_extract_calls = 2
            assert mock_extract.call_count == expected_extract_calls

    async def test_run_pipeline_without_filter_match(
        self, mock_settings: MagicMock
    ) -> None:
        """Test pipeline fallback when no CSS filter matches."""
        parser = Parser(mock_settings)

        with (
            patch.object(parser._extractor, "extract_html") as mock_extract,
            patch.object(parser._filter, "apply_all") as mock_filter,
            patch.object(parser._markdown_generator, "convert") as mock_convert,
        ):
            mock_extract.return_value = ExtractionResult(
                raw_html="<html>...</html>", cleaned_html="<body>content</body>"
            )
            mock_filter.return_value = None
            mock_convert.return_value = "# Fallback Markdown"

            result = await parser._run_pipeline("https://example.com")

            assert result == "# Fallback Markdown"
            # Should only extract once (no re-extraction for filter)
            mock_extract.assert_called_once()
            # Should convert the cleaned_html
            mock_convert.assert_called_once_with("<body>content</body>")

    async def test_run_pipeline_extraction_failure(
        self, mock_settings: MagicMock
    ) -> None:
        """Test pipeline when initial extraction fails."""
        parser = Parser(mock_settings)

        with patch.object(parser._extractor, "extract_html") as mock_extract:
            mock_extract.side_effect = SSMCPError("Failed to fetch URL")

            with pytest.raises(SSMCPError, match="Failed to fetch URL"):
                await parser._run_pipeline("https://example.com")

    async def test_parse_pages_empty_list(
        self, mock_settings: MagicMock, mock_context: AsyncMock
    ) -> None:
        """Test parsing an empty URL list."""
        parser = Parser(mock_settings)

        result = await parser.parse_pages([], mock_context)

        assert result == {}


class TestParserCssSelectorFlow:
    """Integration-style tests for Parser pipeline with CSS selector filtering."""

    @pytest.fixture
    def flow_mock_settings(self) -> MagicMock:
        """Create mock settings for flow testing."""
        settings = MagicMock()
        settings.css_selector_priority_list = (
            'article, main, [role="main"], .article, .article-content, '
            '#content, #main, .content'
        )
        settings.css_selector_min_words = 50
        settings.crawl4ai_pruning_threshold = 0.0
        settings.crawl4ai_threshold_type = "dynamic"
        settings.crawl4ai_min_word_threshold = 1
        settings.crawl4ai_ignore_images = True
        settings.crawl4ai_ignore_links = True
        settings.crawl4ai_skip_internal_links = True
        settings.crawl4ai_escape_html = True
        settings.crawl4ai_body_width = 0
        settings.crawl4ai_include_sup_sub = True
        settings.junk_filter_enabled = True
        settings.junk_filter_letter_ratio_threshold = 0.3
        return settings

    @pytest.fixture
    def mock_ctx(self) -> AsyncMock:
        """Create a mock context for progress reporting."""
        ctx = AsyncMock()
        ctx.report_progress = AsyncMock()
        return ctx

    async def test_css_selector_matches_uses_raw_html(
        self, flow_mock_settings: MagicMock, mock_ctx: AsyncMock
    ) -> None:
        """Test that when CSS selector matches in raw HTML, filtered content is used."""
        parser = Parser(flow_mock_settings)

        raw_html_with_content = f"""
        <html>
        <head><title>Stack Overflow Question</title></head>
        <body>
            <header><nav>Navigation</nav></header>
            <div id="content">
                <div class="question">
                    <h1>How to use Python decorators?</h1>
                    <p>{" ".join(["word"] * 60)}</p>
                    <p>I want to use them in my web applications.</p>
                </div>
            </div>
            <footer>Copyright</footer>
        </body>
        </html>
        """

        cleaned_html_without_content = f"""
        <html>
        <head><title>Stack Overflow Question</title></head>
        <body>
            <div class="question">
                <h1>How to use Python decorators?</h1>
                <p>{" ".join(["word"] * 60)}</p>
                <p>I want to use them in my web applications.</p>
            </div>
        </body>
        </html>
        """

        call_count = 0

        async def mock_extract(url_or_html: str) -> ExtractionResult:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ExtractionResult(
                    raw_html=raw_html_with_content,
                    cleaned_html=cleaned_html_without_content,
                )
            else:
                cleaned_html = (
                    '<div id="content"><div class="question">'
                    "<h1>How to use Python decorators?</h1>"
                    "<p>I'm learning about Python decorators...</p>"
                    "</div></div>"
                )
                return ExtractionResult(raw_html="", cleaned_html=cleaned_html)

        with patch.object(parser._extractor, "extract_html", side_effect=mock_extract):
            result = await parser.parse_pages(["http://example.com"], mock_ctx)

        markdown = result["http://example.com"]
        assert markdown is not None
        assert "Python decorators" in markdown
        assert "learning about Python decorators" in markdown

    async def test_no_css_selector_match_uses_cleaned_html(
        self, flow_mock_settings: MagicMock, mock_ctx: AsyncMock
    ) -> None:
        """Test that when no CSS selector matches, cleaned HTML is used as fallback."""
        parser = Parser(flow_mock_settings)

        raw_html_no_selectors = """
        <html>
        <body>
            <script>var ads = {};</script>
            <div class="wrapper">
                <div class="container">
                    <h1>Short Content</h1>
                    <p>This page has minimal content.</p>
                </div>
            </div>
            <script>tracking();</script>
        </body>
        </html>
        """

        cleaned_html_no_selectors = """
        <html>
        <body>
            <div class="wrapper">
                <div class="container">
                    <h1>Short Content</h1>
                    <p>This page has minimal content.</p>
                </div>
            </div>
        </body>
        </html>
        """

        with patch.object(parser._extractor, "extract_html") as mock_ext:
            mock_ext.return_value = ExtractionResult(
                raw_html=raw_html_no_selectors, cleaned_html=cleaned_html_no_selectors
            )

            result = await parser.parse_pages(["http://example.com"], mock_ctx)

        markdown = result["http://example.com"]
        assert markdown is not None
        assert "Short Content" in markdown

    async def test_only_cleaned_html_available(
        self, flow_mock_settings: MagicMock, mock_ctx: AsyncMock
    ) -> None:
        """Test fallback when only cleaned HTML is available (raw is empty)."""
        parser = Parser(flow_mock_settings)

        cleaned_html = f"""
        <html>
        <head><title>Test</title></head>
        <body>
            <div class="question">
                <h1>How to use Python decorators?</h1>
                <p>{" ".join(["word"] * 60)}</p>
            </div>
        </body>
        </html>
        """

        with patch.object(parser._extractor, "extract_html") as mock_ext:
            mock_ext.return_value = ExtractionResult(
                raw_html="", cleaned_html=cleaned_html
            )
            result = await parser.parse_pages(["http://example.com"], mock_ctx)

        markdown = result["http://example.com"]
        assert markdown is not None
        assert "Python decorators" in markdown

    async def test_extraction_failure_skips_url(
        self, flow_mock_settings: MagicMock, mock_ctx: AsyncMock
    ) -> None:
        """Test that parsing fails gracefully when extraction fails."""
        parser = Parser(flow_mock_settings)

        with patch.object(parser._extractor, "extract_html") as mock_ext:
            mock_ext.side_effect = SSMCPError("Extraction failed")
            result = await parser.parse_pages(["http://example.com"], mock_ctx)

        assert "http://example.com" not in result

    async def test_multiple_urls_with_different_scenarios(
        self, flow_mock_settings: MagicMock, mock_ctx: AsyncMock
    ) -> None:
        """Test parsing multiple URLs with different HTML scenarios."""
        parser = Parser(flow_mock_settings)

        urls = ["http://stackoverflow.com", "http://blog.com", "http://unknown.com"]

        async def mock_extract(url_or_html: str) -> ExtractionResult:
            # Initial URL extractions (start with http)
            if url_or_html.startswith("http://"):
                if "stackoverflow" in url_or_html:
                    return ExtractionResult(
                        raw_html='<html><body><div id="content">'
                        + " ".join(["word"] * 60)
                        + "</div></body></html>",
                        cleaned_html="<html><body>" + " ".join(["word"] * 60) + "</body></html>",
                    )
                elif "blog" in url_or_html:
                    return ExtractionResult(
                        raw_html="<html><body><article>"
                        + " ".join(["post"] * 60)
                        + "</article></body></html>",
                        cleaned_html="<html><body><article>"
                        + " ".join(["post"] * 60)
                        + "</article></body></html>",
                    )
                else:
                    raise SSMCPError("Not found")
            else:
                # Re-extraction of filtered HTML fragments
                return ExtractionResult(
                    raw_html="",
                    cleaned_html="<html><body>filtered content</body></html>",
                )

        with patch.object(parser._extractor, "extract_html", side_effect=mock_extract):
            result = await parser.parse_pages(urls, mock_ctx)

        assert result["http://stackoverflow.com"] is not None
        assert result["http://blog.com"] is not None
        assert "http://unknown.com" not in result
