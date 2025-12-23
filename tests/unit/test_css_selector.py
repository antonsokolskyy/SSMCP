"""Unit tests for CSS selector filter functionality."""

from typing import Any

import pytest
from bs4 import BeautifulSoup

from ssmcp.parser.filters.css_selector import CssSelectorFilter


@pytest.fixture
def mock_settings() -> Any:
    """Create mock settings for testing."""
    class MockSettings:
        css_selector_priority_list = (
            'article, main, [role="main"], .article, .article-content, '
            '#content, #main, .content'
        )
        css_selector_min_words = 50

    return MockSettings()


@pytest.fixture
def stackoverflow_like_html() -> str:
    """HTML similar to Stack Overflow with #content div."""
    return """
    <html>
    <head><title>Test Page</title></head>
    <body>
        <header>
            <nav>Navigation Menu</nav>
        </header>
        <div id="content" class="snippet-hidden">
            <div class="question">
                <h1>How to fix RVM is not a function error?</h1>
                <p>I'm trying to use RVM but getting an error that says "RVM is not a function".
                   This happens when I try to run rvm use 2.0.0. The error message tells me that
                   selecting rubies with rvm use will not work. I've installed RVM using the
                   official installation script but still facing this issue. How can I resolve this?
                   I need to switch between different Ruby versions for my projects.</p>
                <div class="answer">
                    <p>The issue occurs because RVM needs to be loaded as a shell function, not just
                       a regular command. You need to add the RVM loading script to your shell
                       configuration file. For bash, add this line to your ~/.bashrc or
                       ~/.bash_profile: source "$HOME/.rvm/scripts/rvm". After adding this, restart
                       your terminal or source the file again. This will properly load RVM as a
                       function and allow you to use commands like rvm use to switch Ruby
                       versions.</p>
                </div>
            </div>
        </div>
        <footer>Copyright 2024</footer>
    </body>
    </html>
    """


@pytest.fixture
def article_tag_html() -> str:
    """HTML with semantic article tag."""
    return """
    <html>
    <body>
        <nav>Site Navigation</nav>
        <article>
            <h1>Understanding Python Decorators</h1>
            <p>Python decorators are a powerful feature that allows you to modify the behavior
               of functions or classes. They are commonly used for logging, authentication,
               caching, and more. A decorator is essentially a function that takes another
               function as an argument and returns a new function. This pattern provides a
               clean and reusable way to extend functionality without modifying the original
               code. Decorators use the @ symbol for a cleaner syntax.</p>
            <p>For example, you can create a simple timing decorator that measures how long
               a function takes to execute. This is useful for performance optimization and
               identifying bottlenecks in your code. The decorator wraps the original function
               and adds timing logic before and after execution.</p>
        </article>
        <aside>Related articles</aside>
    </body>
    </html>
    """


@pytest.fixture
def role_main_html() -> str:
    """HTML with role="main" attribute."""
    return """
    <html>
    <body>
        <header>Header content</header>
        <div role="main">
            <h1>Machine Learning Basics</h1>
            <p>Machine learning is a subset of artificial intelligence that focuses on building
               systems that can learn from data. Instead of being explicitly programmed, these
               systems improve their performance through experience. There are three main types
               of machine learning: supervised learning, unsupervised learning, and reinforcement
               learning. Each type has different use cases and approaches.</p>
            <p>Supervised learning involves training a model on labeled data, where the correct
               answers are already known. This is used for tasks like classification and regression.
               Unsupervised learning finds patterns in unlabeled data, useful for clustering and
               dimensionality reduction. Reinforcement learning trains agents through rewards and
               penalties, commonly used in robotics and game playing.</p>
        </div>
        <footer>Footer content</footer>
    </body>
    </html>
    """


@pytest.fixture
def no_selector_match_html() -> str:
    """HTML where none of the priority selectors match."""
    return """
    <html>
    <body>
        <div class="page-wrapper">
            <div class="some-container">
                <h1>Short Content</h1>
                <p>This page has minimal content that doesn't match any priority selectors.</p>
            </div>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def low_word_count_html() -> str:
    """HTML where selector matches but word count is too low."""
    return """
    <html>
    <body>
        <div id="content">
            <h1>Title</h1>
            <p>Very short content here.</p>
        </div>
    </body>
    </html>
    """


class TestCssSelectorFilter:
    """Test suite for CSS selector filter."""

    def test_finds_content_id_selector(
        self, mock_settings: Any, stackoverflow_like_html: str
    ) -> None:
        """Test that #content selector is found and extracted."""
        filter_instance = CssSelectorFilter(mock_settings)
        result = filter_instance.apply(stackoverflow_like_html)

        assert result is not None
        assert 'id="content"' in result
        assert 'RVM is not a function' in result
        assert 'Navigation Menu' not in result  # Header should be excluded
        assert 'Copyright 2024' not in result  # Footer should be excluded

    def test_finds_article_tag(self, mock_settings: Any, article_tag_html: str) -> None:
        """Test that article tag is found (higher priority than #content)."""
        filter_instance = CssSelectorFilter(mock_settings)
        result = filter_instance.apply(article_tag_html)

        assert result is not None
        assert '<article>' in result or '<article' in result
        assert 'Python Decorators' in result
        assert 'Site Navigation' not in result
        assert 'Related articles' not in result

    def test_finds_role_main(self, mock_settings: Any, role_main_html: str) -> None:
        """Test that role="main" is found."""
        filter_instance = CssSelectorFilter(mock_settings)
        result = filter_instance.apply(role_main_html)

        assert result is not None
        assert 'role="main"' in result
        assert 'Machine Learning' in result
        assert 'Header content' not in result
        assert 'Footer content' not in result

    def test_no_selector_match_returns_none(
        self, mock_settings: Any, no_selector_match_html: str
    ) -> None:
        """Test that None is returned when no selector matches."""
        filter_instance = CssSelectorFilter(mock_settings)
        result = filter_instance.apply(no_selector_match_html)
        assert result is None

    def test_low_word_count_returns_none(
        self, mock_settings: Any, low_word_count_html: str
    ) -> None:
        """Test that None is returned when word count is insufficient."""
        filter_instance = CssSelectorFilter(mock_settings)
        result = filter_instance.apply(low_word_count_html)
        assert result is None

    def test_word_count_threshold_respected(
        self, mock_settings: Any, stackoverflow_like_html: str
    ) -> None:
        """Test that word count threshold is properly checked."""
        filter_instance = CssSelectorFilter(mock_settings)
        result = filter_instance.apply(stackoverflow_like_html)

        # Extract the text and verify word count
        assert result is not None
        soup = BeautifulSoup(result, 'html.parser')
        text = soup.get_text(strip=True)
        word_count = len(text.split())

        assert word_count >= mock_settings.css_selector_min_words

    def test_selector_priority_order(self, mock_settings: Any) -> None:
        """Test that selectors are tried in priority order."""
        # HTML with both article and #content
        html_with_both = """
        <html>
        <body>
            <article>
                <p>""" + " ".join(["word"] * 60) + """</p>
            </article>
            <div id="content">
                <p>""" + " ".join(["different"] * 60) + """</p>
            </div>
        </body>
        </html>
        """

        filter_instance = CssSelectorFilter(mock_settings)
        result = filter_instance.apply(html_with_both)

        # Should match article first (higher priority)
        assert result is not None
        assert '<article>' in result or '<article' in result
        assert 'word word word' in result  # From article
        assert 'different' not in result  # #content should not be selected

    def test_empty_html_returns_none(self, mock_settings: Any) -> None:
        """Test that None is returned for empty HTML."""
        filter_instance = CssSelectorFilter(mock_settings)
        result = filter_instance.apply("")
        assert result is None

    def test_parse_selector_list(self, mock_settings: Any) -> None:
        """Test that selector list is correctly parsed from settings."""
        filter_instance = CssSelectorFilter(mock_settings)
        selectors = filter_instance._parse_selector_list()

        expected_selector_count = 8  # Expected number of selectors in the priority list
        assert 'article' in selectors
        assert 'main' in selectors
        assert '[role="main"]' in selectors
        assert '#content' in selectors
        assert len(selectors) == expected_selector_count

    def test_custom_min_words_threshold(self, stackoverflow_like_html: str) -> None:
        """Test with custom minimum word threshold returns None when threshold not met."""
        custom_threshold = 200  # Very high threshold for testing
        class CustomSettings:
            css_selector_priority_list = '#content'
            css_selector_min_words = custom_threshold

        filter_instance = CssSelectorFilter(CustomSettings())  # type: ignore[arg-type]
        result = filter_instance.apply(stackoverflow_like_html)
        assert result is None

    def test_preserves_html_structure(
        self, mock_settings: Any, stackoverflow_like_html: str
    ) -> None:
        """Test that the matched HTML preserves its internal structure."""
        filter_instance = CssSelectorFilter(mock_settings)
        result = filter_instance.apply(stackoverflow_like_html)

        assert result is not None
        soup = BeautifulSoup(result, 'html.parser')

        # Should preserve nested structure
        assert soup.find('h1') is not None
        assert soup.find('div', class_='question') is not None
        assert soup.find('div', class_='answer') is not None

    def test_multiple_classes_on_content_div(self, mock_settings: Any) -> None:
        """Test that #content is found even with multiple classes."""
        html = """
        <html>
        <body>
            <div id="content" class="snippet-hidden main-content active">
                <p>""" + " ".join(["test"] * 60) + """</p>
            </div>
        </body>
        </html>
        """

        filter_instance = CssSelectorFilter(mock_settings)
        result = filter_instance.apply(html)

        assert result is not None
        assert 'id="content"' in result
        assert 'snippet-hidden' in result
