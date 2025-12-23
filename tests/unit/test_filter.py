"""Unit tests for Filter module."""

from unittest.mock import MagicMock

import pytest

from ssmcp.parser.filter import Filter
from ssmcp.parser.filters.css_selector import CssSelectorFilter


@pytest.fixture
def mock_settings() -> MagicMock:
    """Create mock settings for testing."""
    settings = MagicMock()
    settings.css_selector_priority_list = "article, main, #content"
    settings.css_selector_min_words = 50
    return settings


class TestFilter:
    """Test Filter class functionality."""

    def test_initialize_filters_creates_css_selector_filter(
        self, mock_settings: MagicMock
    ) -> None:
        """Test that Filter initializes with CssSelectorFilter."""
        content_filter = Filter(mock_settings)

        filters = content_filter._filters
        assert len(filters) == 1
        assert isinstance(filters[0], CssSelectorFilter)

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

    def test_apply_all_returns_none_when_no_match(
        self, mock_settings: MagicMock
    ) -> None:
        """Test that apply_all returns None when no filter matches."""
        content_filter = Filter(mock_settings)

        html_no_match = """
        <html>
        <body>
            <div class="wrapper">
                <p>Short content</p>
            </div>
        </body>
        </html>
        """

        result = content_filter.apply_all(html_no_match)

        assert result is None

    def test_apply_all_with_empty_html(self, mock_settings: MagicMock) -> None:
        """Test that apply_all handles empty HTML gracefully."""
        content_filter = Filter(mock_settings)

        result = content_filter.apply_all("")

        assert result is None

    def test_apply_all_tries_filters_in_order(self, mock_settings: MagicMock) -> None:
        """Test that filters are tried in order and first match is returned."""
        content_filter = Filter(mock_settings)

        # Create a mock filter that will match
        mock_filter_1 = MagicMock()
        mock_filter_1.apply.return_value = None  # No match

        mock_filter_2 = MagicMock()
        mock_filter_2.apply.return_value = "<html>Matched by filter 2</html>"

        mock_filter_3 = MagicMock()
        mock_filter_3.apply.return_value = "<html>Matched by filter 3</html>"

        # Replace filters with mocks
        content_filter._filters = [mock_filter_1, mock_filter_2, mock_filter_3]

        result = content_filter.apply_all("<html>test</html>")

        # Should return result from filter 2 (first match)
        assert result == "<html>Matched by filter 2</html>"

        # Verify all filters were tried in order
        mock_filter_1.apply.assert_called_once()
        mock_filter_2.apply.assert_called_once()
        # Filter 3 should not be called since filter 2 matched
        mock_filter_3.apply.assert_not_called()

    def test_apply_all_tries_all_filters_when_none_match(
        self, mock_settings: MagicMock
    ) -> None:
        """Test that all filters are tried when none match."""
        content_filter = Filter(mock_settings)

        mock_filter_1 = MagicMock()
        mock_filter_1.apply.return_value = None

        mock_filter_2 = MagicMock()
        mock_filter_2.apply.return_value = None

        mock_filter_3 = MagicMock()
        mock_filter_3.apply.return_value = None

        content_filter._filters = [mock_filter_1, mock_filter_2, mock_filter_3]

        result = content_filter.apply_all("<html>test</html>")

        assert result is None

        # All filters should have been tried
        mock_filter_1.apply.assert_called_once()
        mock_filter_2.apply.assert_called_once()
        mock_filter_3.apply.assert_called_once()

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
