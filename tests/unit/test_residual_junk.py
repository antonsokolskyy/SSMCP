"""Unit tests for ResidualJunkFilter module."""

from unittest.mock import MagicMock

import pytest

from ssmcp.parser.filters.residual_junk import ResidualJunkFilter


@pytest.fixture
def mock_settings() -> MagicMock:
    """Create mock settings for testing."""
    settings = MagicMock()
    settings.junk_filter_enabled = True
    settings.junk_filter_letter_ratio_threshold = 0.3
    return settings


class TestResidualJunkFilter:
    """Test ResidualJunkFilter functionality."""

    def test_removes_empty_elements(self, mock_settings: MagicMock) -> None:
        """Test that empty elements are removed."""
        junk_filter = ResidualJunkFilter(mock_settings)

        html_with_empty = """
        <article>
            <p>Good content</p>
            <span></span>
            <div>   </div>
        </article>
        """

        result = junk_filter.apply(html_with_empty)

        assert result is not None
        assert "Good content" in result
        assert "<span></span>" not in result
        assert "<div>   </div>" not in result

    def test_removes_single_word_elements(self, mock_settings: MagicMock) -> None:
        """Test that short single-word elements are removed."""
        junk_filter = ResidualJunkFilter(mock_settings)

        html_with_junk = """
        <article>
            <p>Good content here</p>
            <span>Follow</span>
            <div>42</div>
            <span>Like</span>
        </article>
        """

        result = junk_filter.apply(html_with_junk)

        assert result is not None
        assert "Good content here" in result
        assert "Follow" not in result
        assert "42" not in result
        assert "Like" not in result

    def test_keeps_multi_word_elements(self, mock_settings: MagicMock) -> None:
        """Test that multi-word elements are preserved."""
        junk_filter = ResidualJunkFilter(mock_settings)

        html_with_content = """
        <article>
            <p>This is good content with multiple words</p>
            <span>AI technology</span>
        </article>
        """

        result = junk_filter.apply(html_with_content)

        assert result is not None
        assert "This is good content with multiple words" in result
        assert "AI technology" in result

    def test_removes_tooltip_elements(self, mock_settings: MagicMock) -> None:
        """Test that elements with role=tooltip are removed."""
        junk_filter = ResidualJunkFilter(mock_settings)

        html_with_tooltip = """
        <article>
            <p>Good content</p>
            <span role="tooltip">Helpful info</span>
            <div role="tooltip">More help</div>
        </article>
        """

        result = junk_filter.apply(html_with_tooltip)

        assert result is not None
        assert "Good content" in result
        assert "Helpful info" not in result
        assert "More help" not in result

    def test_protects_code_blocks(self, mock_settings: MagicMock) -> None:
        """Test that code blocks are not modified."""
        junk_filter = ResidualJunkFilter(mock_settings)

        html_with_code = """
        <article>
            <p>Here is some code:</p>
            <code>x = 5</code>
            <pre>y = 10</pre>
        </article>
        """

        result = junk_filter.apply(html_with_code)

        assert result is not None
        assert "<code>x = 5</code>" in result
        assert "<pre>y = 10</pre>" in result

    def test_protects_nested_code_content(self, mock_settings: MagicMock) -> None:
        """Test that elements inside code blocks are protected."""
        junk_filter = ResidualJunkFilter(mock_settings)

        html_with_nested = """
        <article>
            <p>Some content here</p>
            <pre>
                <span>42</span>
                <div>x</div>
            </pre>
        </article>
        """

        result = junk_filter.apply(html_with_nested)

        assert result is not None
        # Content outside pre is preserved
        assert "Some content here" in result
        # Content inside pre should be preserved (even single words)
        assert "<span>42</span>" in result or "42" in result

    def test_keeps_single_word_headings(self, mock_settings: MagicMock) -> None:
        """Test that headings are never removed, even if single-word."""
        junk_filter = ResidualJunkFilter(mock_settings)

        html_with_heading = """
        <article>
            <h1>Title</h1>
            <h2>AI</h2>
            <p>Content here</p>
        </article>
        """

        result = junk_filter.apply(html_with_heading)

        assert result is not None
        # Headings are protected and kept
        assert "<h1>Title</h1>" in result
        assert "<h2>AI</h2>" in result
        # Multi-word content is preserved
        assert "Content here" in result

    def test_keeps_multi_word_headings(self, mock_settings: MagicMock) -> None:
        """Test that multi-word headings are preserved."""
        junk_filter = ResidualJunkFilter(mock_settings)

        html_with_heading = """
        <article>
            <h1>Article Title</h1>
            <p>Content here</p>
        </article>
        """

        result = junk_filter.apply(html_with_heading)

        assert result is not None
        # Multi-word heading is preserved
        assert "Article Title" in result
        assert "Content here" in result

    def test_removes_special_char_only_elements(self, mock_settings: MagicMock) -> None:
        """Test that elements with only special chars are removed."""
        junk_filter = ResidualJunkFilter(mock_settings)

        html_with_special = """
        <article>
            <p>Content here</p>
            <span>→</span>
            <div>•</div>
            <span>—</span>
        </article>
        """

        result = junk_filter.apply(html_with_special)

        assert result is not None
        assert "Content here" in result
        assert "→" not in result
        assert "•" not in result
        assert "—" not in result

    def test_removes_any_single_word(self, mock_settings: MagicMock) -> None:
        """Test that any single word without spaces is removed."""
        junk_filter = ResidualJunkFilter(mock_settings)

        html = """
        <article>
            <p>Content here with multiple words</p>
            <span>Short</span>
            <span>LongerWord</span>
            <span>x</span>
        </article>
        """

        result = junk_filter.apply(html)

        assert result is not None
        assert "Content here with multiple words" in result
        # All single words should be removed (no length limit)
        assert "Short" not in result
        assert "LongerWord" not in result
        assert "x" not in result

    def test_disabled_filter_returns_unchanged(self, mock_settings: MagicMock) -> None:
        """Test that disabled filter returns HTML unchanged."""
        mock_settings.junk_filter_enabled = False
        junk_filter = ResidualJunkFilter(mock_settings)

        html = """
        <article>
            <p>Content</p>
            <span>42</span>
        </article>
        """

        result = junk_filter.apply(html)

        assert result == html

    def test_empty_html_returns_none(self, mock_settings: MagicMock) -> None:
        """Test that empty HTML returns None."""
        junk_filter = ResidualJunkFilter(mock_settings)

        result = junk_filter.apply("")

        assert result is None

    def test_all_junk_removed_returns_none(self, mock_settings: MagicMock) -> None:
        """Test that HTML with only junk returns None."""
        junk_filter = ResidualJunkFilter(mock_settings)

        html = """
        <article>
            <span>42</span>
            <div>Follow</div>
        </article>
        """

        result = junk_filter.apply(html)

        assert result is None

    def test_complex_nested_structure(self, mock_settings: MagicMock) -> None:
        """Test handling of complex nested structures."""
        junk_filter = ResidualJunkFilter(mock_settings)

        html = """
        <article>
            <h1>Article Title</h1>
            <p>This is the main content with multiple words.</p>
            <div>
                <span>42</span>
                <span>likes</span>
            </div>
            <blockquote>
                <p>Quote with x = 5 code reference</p>
            </blockquote>
            <pre>
                <code>print("hello")</code>
            </pre>
        </article>
        """

        result = junk_filter.apply(html)

        assert result is not None
        assert "Article Title" in result  # Multi-word heading kept
        assert "This is the main content with multiple words." in result
        assert "42" not in result  # Single word, removed
        assert "likes" not in result  # Single word, removed
        # blockquote is not protected anymore, but p inside has multiple words
        assert "Quote with x = 5 code reference" in result
        assert "print" in result or "hello" in result  # In protected pre/code

    def test_removes_parent_with_only_single_word_children(self, mock_settings: MagicMock) -> None:
        """Test that parent elements with only single-word children are removed."""
        junk_filter = ResidualJunkFilter(mock_settings)

        html = """
        <article>
            <p>Content here</p>
            <div>
                <span>42</span>
                <span>likes</span>
            </div>
        </article>
        """

        result = junk_filter.apply(html)

        assert result is not None
        assert "Content here" in result
        # The div containing only single-word children is removed
        assert "42" not in result
        assert "likes" not in result

    def test_removes_duplicate_text(self, mock_settings: MagicMock) -> None:
        """Test that duplicate text elements are removed (keep first)."""
        junk_filter = ResidualJunkFilter(mock_settings)

        html = """
        <article>
            <p>First occurrence</p>
            <p>First occurrence</p>
            <p>Unique text here</p>
        </article>
        """

        result = junk_filter.apply(html)

        assert result is not None
        # First occurrence kept
        assert "First occurrence" in result
        # Second occurrence removed
        # Count occurrences - should be only 1
        assert result.count("First occurrence") == 1
        # Unique text kept
        assert "Unique text here" in result

    def test_removes_low_letter_ratio_text(self, mock_settings: MagicMock) -> None:
        """Test that elements with too few letters are removed."""
        junk_filter = ResidualJunkFilter(mock_settings)

        html = """
        <article>
            <p>Good content here</p>
            <p>123 456 789</p>
            <p>!!! @@@ ###</p>
            <p>Text with some 123 numbers</p>
        </article>
        """

        result = junk_filter.apply(html)

        assert result is not None
        assert "Good content here" in result
        # Low letter ratio elements removed
        assert "123 456 789" not in result  # 0% letters
        assert "!!! @@@ ###" not in result  # 0% letters
        # This has enough letters (above 30% threshold)
        assert "Text with some 123 numbers" in result

    def test_letter_ratio_threshold_setting(self, mock_settings: MagicMock) -> None:
        """Test that letter ratio threshold setting works."""
        # Set stricter threshold (60% letters required)
        mock_settings.junk_filter_letter_ratio_threshold = 0.6
        junk_filter = ResidualJunkFilter(mock_settings)

        html = """
        <article>
            <p>Good content here</p>
            <p>123 456 789 numbers</p>
        </article>
        """

        result = junk_filter.apply(html)

        assert result is not None
        assert "Good content here" in result
        # With 60% threshold, "123 456 789 numbers" (~46% letters) is removed
        assert "123 456 789 numbers" not in result
