"""Unit tests for Filter module."""

from unittest.mock import MagicMock

import pytest

from ssmcp.parser.filter import Filter
from ssmcp.parser.filters.css_selector import CssSelectorFilter
from ssmcp.parser.filters.residual_junk import ResidualJunkFilter

EXPECTED_FILTER_COUNT = 2


@pytest.fixture
def mock_settings() -> MagicMock:
    """Create mock settings for testing."""
    settings = MagicMock()
    settings.css_selector_priority_list = "article, main, #content"
    settings.css_selector_min_words = 50
    settings.junk_filter_enabled = True
    settings.junk_filter_letter_ratio_threshold = 0.3
    return settings


class TestFilter:
    """Test Filter class functionality."""

    def test_initialize_filters_creates_both_filters(
        self, mock_settings: MagicMock
    ) -> None:
        """Test that Filter initializes with both CSS selector and residual junk filters."""
        content_filter = Filter(mock_settings)

        filters = content_filter._filters
        assert len(filters) == EXPECTED_FILTER_COUNT

        assert isinstance(filters[0], CssSelectorFilter)
        assert isinstance(filters[1], ResidualJunkFilter)

    def test_apply_all_returns_first_match(self, mock_settings: MagicMock) -> None:
        """Test that apply_all returns the first filter that matches."""
        content_filter = Filter(mock_settings)

        html_with_article = """
        <html>
        <body>
            <article>
                <p>""" + " ".join(["word"] * 60) + """</p>
            </article>
        </body>
        </html>
        """

        result = content_filter.apply_all(html_with_article)

        assert result is not None
        assert "<article>" in result or "<article" in result

    def test_apply_all_returns_cleaned_html_when_css_filter_fails(
        self, mock_settings: MagicMock
    ) -> None:
        """Test that apply_all returns junk-cleaned HTML when CSS selector fails."""
        content_filter = Filter(mock_settings)

        html_with_junk = """
        <html>
        <body>
            <div class="wrapper">
                <p>Content here</p>
                <span>42</span>
                <div>Follow</div>
            </div>
        </body>
        </html>
        """

        result = content_filter.apply_all(html_with_junk)

        # CSS selector fails (no article/main), but residual junk filter
        # still cleans the HTML and returns it
        assert result is not None
        assert "Content here" in result
        # Junk elements should be removed
        assert "42" not in result
        assert "Follow" not in result

    def test_apply_all_with_empty_html(self, mock_settings: MagicMock) -> None:
        """Test that apply_all handles empty HTML gracefully."""
        content_filter = Filter(mock_settings)

        result = content_filter.apply_all("")

        assert result is None

    def test_apply_all_applies_all_filters_sequentially(self, mock_settings: MagicMock) -> None:
        """Test that all filters are applied sequentially, passing output to next."""
        content_filter = Filter(mock_settings)

        # Create mock filters that transform the HTML
        mock_filter_1 = MagicMock()
        mock_filter_1.apply.return_value = "<html>After filter 1</html>"

        mock_filter_2 = MagicMock()
        mock_filter_2.apply.return_value = "<html>After filter 2</html>"

        mock_filter_3 = MagicMock()
        mock_filter_3.apply.return_value = "<html>After filter 3</html>"

        # Replace filters with mocks
        content_filter._filters = [mock_filter_1, mock_filter_2, mock_filter_3]

        result = content_filter.apply_all("<html>original</html>")

        # Should return result from last filter
        assert result == "<html>After filter 3</html>"

        # Verify all filters were called in order with correct inputs
        mock_filter_1.apply.assert_called_once_with("<html>original</html>")
        mock_filter_2.apply.assert_called_once_with("<html>After filter 1</html>")
        mock_filter_3.apply.assert_called_once_with("<html>After filter 2</html>")

    def test_apply_all_continues_when_filter_returns_none(
        self, mock_settings: MagicMock
    ) -> None:
        """Test that apply_all continues with same HTML when filter returns None."""
        content_filter = Filter(mock_settings)

        mock_filter_1 = MagicMock()
        mock_filter_1.apply.return_value = None  # First filter fails

        mock_filter_2 = MagicMock()
        mock_filter_2.apply.return_value = "<html>After filter 2</html>"

        content_filter._filters = [mock_filter_1, mock_filter_2]

        result = content_filter.apply_all("<html>original</html>")

        # Should return result from filter 2 since it succeeded
        assert result == "<html>After filter 2</html>"

        # First filter called with original HTML
        mock_filter_1.apply.assert_called_once_with("<html>original</html>")
        # Second filter called with same HTML (since first returned None)
        mock_filter_2.apply.assert_called_once_with("<html>original</html>")

    def test_apply_all_returns_none_when_all_filters_fail(
        self, mock_settings: MagicMock
    ) -> None:
        """Test that apply_all returns None when all filters return None."""
        content_filter = Filter(mock_settings)

        mock_filter_1 = MagicMock()
        mock_filter_1.apply.return_value = None

        mock_filter_2 = MagicMock()
        mock_filter_2.apply.return_value = None

        content_filter._filters = [mock_filter_1, mock_filter_2]

        result = content_filter.apply_all("<html>test</html>")

        # Should return None since all filters failed
        assert result is None

        # Both filters should have been called with same HTML
        mock_filter_1.apply.assert_called_once_with("<html>test</html>")
        mock_filter_2.apply.assert_called_once_with("<html>test</html>")

    def test_filter_with_complex_html(self, mock_settings: MagicMock) -> None:
        """Test filter with realistic complex HTML."""
        content_filter = Filter(mock_settings)

        complex_html = """
        <html>
        <head><title>Test Page</title></head>
        <body>
            <header>
                <nav>Navigation</nav>
            </header>
            <main>
                <article>
                    <h1>Main Article</h1>
                    <p>""" + " ".join(["content"] * 60) + """</p>
                </article>
            </main>
            <aside>
                <div id="sidebar">Sidebar content</div>
            </aside>
            <footer>Copyright 2024</footer>
        </body>
        </html>
        """

        result = content_filter.apply_all(complex_html)

        # Should match article (first in priority list)
        assert result is not None
        assert "<article>" in result or "<article" in result
        assert "Main Article" in result

    def test_filter_respects_css_selector_settings(
        self, mock_settings: MagicMock
    ) -> None:
        """Test that filter uses CSS selector settings from configuration."""
        # Custom settings with different selectors
        mock_settings.css_selector_priority_list = "#main-content, .content-area"
        mock_settings.css_selector_min_words = 30

        content_filter = Filter(mock_settings)

        html_with_custom_selector = """
        <html>
        <body>
            <div id="main-content">
                <p>""" + " ".join(["word"] * 40) + """</p>
            </div>
        </body>
        </html>
        """

        result = content_filter.apply_all(html_with_custom_selector)

        assert result is not None
        assert 'id="main-content"' in result
