"""Unit tests for MarkdownGenerator module."""

from unittest.mock import MagicMock, patch

import pytest

from ssmcp.exceptions import MarkdownGeneratorError
from ssmcp.parser.markdown_generator import MarkdownGenerator


@pytest.fixture
def mock_settings() -> MagicMock:
    """Create mock settings for testing."""
    settings = MagicMock()
    settings.crawl4ai_pruning_threshold = 0.30
    settings.crawl4ai_threshold_type = "dynamic"
    settings.crawl4ai_min_word_threshold = 1
    settings.crawl4ai_ignore_images = True
    settings.crawl4ai_ignore_links = True
    settings.crawl4ai_skip_internal_links = True
    settings.crawl4ai_escape_html = True
    settings.crawl4ai_body_width = 0
    settings.crawl4ai_include_sup_sub = True
    return settings


@pytest.fixture
def sample_html() -> str:
    """Sample HTML for testing."""
    return """
    <html>
    <body>
        <article>
            <h1>Test Article Title</h1>
            <p>This is a test paragraph with some content.</p>
            <p>Another paragraph with more detailed information.</p>
            <ul>
                <li>Item 1</li>
                <li>Item 2</li>
                <li>Item 3</li>
            </ul>
        </article>
    </body>
    </html>
    """


class TestMarkdownGenerator:
    """Test MarkdownGenerator class functionality."""

    def test_convert_success(self, mock_settings: MagicMock, sample_html: str) -> None:
        """Test successful HTML to Markdown conversion."""
        generator = MarkdownGenerator(mock_settings)

        # Mock the Crawl4AI components
        mock_result = MagicMock()
        mock_result.fit_markdown = "# Test Article Title\n\nThis is converted markdown."
        mock_result.raw_markdown = "# Raw markdown content"

        with patch(
            "ssmcp.parser.markdown_generator.DefaultMarkdownGenerator"
        ) as mock_md_gen_class:
            mock_md_gen = MagicMock()
            mock_md_gen.generate_markdown.return_value = mock_result
            mock_md_gen_class.return_value = mock_md_gen

            result = generator.convert(sample_html)

            assert isinstance(result, str)
            assert "# Test Article Title" in result
            mock_md_gen.generate_markdown.assert_called_once()

    def test_convert_uses_fit_markdown_preferentially(
        self, mock_settings: MagicMock, sample_html: str
    ) -> None:
        """Test that fit_markdown is preferred over raw_markdown."""
        generator = MarkdownGenerator(mock_settings)

        mock_result = MagicMock()
        mock_result.fit_markdown = "# Fit Markdown Content"
        mock_result.raw_markdown = "# Raw Markdown Content"

        with patch(
            "ssmcp.parser.markdown_generator.DefaultMarkdownGenerator"
        ) as mock_md_gen_class:
            mock_md_gen = MagicMock()
            mock_md_gen.generate_markdown.return_value = mock_result
            mock_md_gen_class.return_value = mock_md_gen

            result = generator.convert(sample_html)

            assert result == "# Fit Markdown Content"

    def test_convert_falls_back_to_raw_markdown(
        self, mock_settings: MagicMock, sample_html: str
    ) -> None:
        """Test fallback to raw_markdown when fit_markdown is empty."""
        generator = MarkdownGenerator(mock_settings)

        mock_result = MagicMock()
        mock_result.fit_markdown = ""
        mock_result.raw_markdown = "# Raw Markdown Fallback"

        with patch(
            "ssmcp.parser.markdown_generator.DefaultMarkdownGenerator"
        ) as mock_md_gen_class:
            mock_md_gen = MagicMock()
            mock_md_gen.generate_markdown.return_value = mock_result
            mock_md_gen_class.return_value = mock_md_gen

            result = generator.convert(sample_html)

            assert result == "# Raw Markdown Fallback"

    def test_convert_empty_html_fails(self, mock_settings: MagicMock) -> None:
        """Test that empty HTML raises MarkdownGeneratorError."""
        generator = MarkdownGenerator(mock_settings)

        mock_result = MagicMock()
        mock_result.fit_markdown = ""
        mock_result.raw_markdown = ""

        with patch(
            "ssmcp.parser.markdown_generator.DefaultMarkdownGenerator"
        ) as mock_md_gen_class:
            mock_md_gen = MagicMock()
            mock_md_gen.generate_markdown.return_value = mock_result
            mock_md_gen_class.return_value = mock_md_gen

            with pytest.raises(MarkdownGeneratorError, match="no content"):
                generator.convert("")

    def test_convert_whitespace_html_fails(self, mock_settings: MagicMock) -> None:
        """Test that whitespace-only HTML raises MarkdownGeneratorError."""
        generator = MarkdownGenerator(mock_settings)

        mock_result = MagicMock()
        mock_result.fit_markdown = ""
        mock_result.raw_markdown = ""

        with patch(
            "ssmcp.parser.markdown_generator.DefaultMarkdownGenerator"
        ) as mock_md_gen_class:
            mock_md_gen = MagicMock()
            mock_md_gen.generate_markdown.return_value = mock_result
            mock_md_gen_class.return_value = mock_md_gen

            with pytest.raises(MarkdownGeneratorError, match="no content"):
                generator.convert("   \n\t  ")

    def test_convert_no_content_produced_fails(
        self, mock_settings: MagicMock, sample_html: str
    ) -> None:
        """Test failure when no markdown content is produced."""
        generator = MarkdownGenerator(mock_settings)

        mock_result = MagicMock()
        mock_result.fit_markdown = ""
        mock_result.raw_markdown = ""

        with patch(
            "ssmcp.parser.markdown_generator.DefaultMarkdownGenerator"
        ) as mock_md_gen_class:
            mock_md_gen = MagicMock()
            mock_md_gen.generate_markdown.return_value = mock_result
            mock_md_gen_class.return_value = mock_md_gen

            with pytest.raises(MarkdownGeneratorError, match="no content"):
                generator.convert(sample_html)

    def test_convert_handles_exception(
        self, mock_settings: MagicMock, sample_html: str
    ) -> None:
        """Test that exceptions during conversion are propagated."""
        generator = MarkdownGenerator(mock_settings)

        with patch(
            "ssmcp.parser.markdown_generator.DefaultMarkdownGenerator"
        ) as mock_md_gen_class:
            mock_md_gen_class.side_effect = Exception("Conversion error")

            with pytest.raises(Exception, match="Conversion error"):
                generator.convert(sample_html)

    def test_convert_uses_pruning_filter(self, mock_settings: MagicMock) -> None:
        """Test that PruningContentFilter is configured correctly."""
        generator = MarkdownGenerator(mock_settings)

        with (
            patch(
                "ssmcp.parser.markdown_generator.PruningContentFilter"
            ) as mock_filter_class,
            patch(
                "ssmcp.parser.markdown_generator.DefaultMarkdownGenerator"
            ) as mock_md_gen_class,
        ):
            mock_result = MagicMock()
            mock_result.fit_markdown = "# Content"
            mock_result.raw_markdown = ""

            mock_md_gen = MagicMock()
            mock_md_gen.generate_markdown.return_value = mock_result
            mock_md_gen_class.return_value = mock_md_gen

            generator.convert("<html><body>test</body></html>")

            mock_filter_class.assert_called_once_with(
                threshold=mock_settings.crawl4ai_pruning_threshold,
                threshold_type=mock_settings.crawl4ai_threshold_type,
                min_word_threshold=mock_settings.crawl4ai_min_word_threshold,
            )

    def test_convert_generator_options(self, mock_settings: MagicMock) -> None:
        """Test that markdown generator is configured with correct options."""
        generator = MarkdownGenerator(mock_settings)

        with (
            patch("ssmcp.parser.markdown_generator.PruningContentFilter"),
            patch(
                "ssmcp.parser.markdown_generator.DefaultMarkdownGenerator"
            ) as mock_md_gen_class,
        ):
            mock_result = MagicMock()
            mock_result.fit_markdown = "# Content"
            mock_result.raw_markdown = ""

            mock_md_gen = MagicMock()
            mock_md_gen.generate_markdown.return_value = mock_result
            mock_md_gen_class.return_value = mock_md_gen

            generator.convert("<html><body>test</body></html>")

            # Verify DefaultMarkdownGenerator was called with expected options
            call_kwargs = mock_md_gen_class.call_args[1]
            assert "options" in call_kwargs
            options = call_kwargs["options"]
            assert options["ignore_images"] == mock_settings.crawl4ai_ignore_images
            assert options["ignore_links"] == mock_settings.crawl4ai_ignore_links
            assert options["skip_internal_links"] == mock_settings.crawl4ai_skip_internal_links
            assert options["escape_html"] == mock_settings.crawl4ai_escape_html
            assert options["body_width"] == mock_settings.crawl4ai_body_width
            assert options["include_sup_sub"] == mock_settings.crawl4ai_include_sup_sub
