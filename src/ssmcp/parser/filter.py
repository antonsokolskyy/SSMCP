"""HTML filtering module."""

from ssmcp.config import Settings
from ssmcp.parser.filters.css_selector import CssSelectorFilter
from ssmcp.parser.filters.residual_junk import ResidualJunkFilter
from ssmcp.parser.protocols import ContentFilter


class Filter:
    """Applies content filters to extract main content from HTML.

    Applies all filters sequentially, with output of each filter
    becoming input to the next filter in the chain.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize the filter with settings.

        Args:
            settings: Application settings containing filter configuration.

        """
        self._settings = settings
        self._filters = self._initialize_filters()

    def _initialize_filters(self) -> list[ContentFilter]:
        """Initialize content filters in processing order.

        Returns:
            List of ContentFilter instances to apply.

        """
        return [
            CssSelectorFilter(self._settings),
            ResidualJunkFilter(self._settings),
        ]

    def apply_all(self, html: str) -> str | None:
        """Apply all filters sequentially.

        Each filter transforms the HTML. If a filter returns a result,
        that result is passed to the next filter. If a filter returns
        None, the next filter receives the same HTML the previous
        filter received (acting as a fallback).

        Args:
            html: HTML content to filter.

        Returns:
            String containing filtered HTML after all filters applied,
            or None if all filters returned None.

        """
        current_html = html
        any_success = False

        for content_filter in self._filters:
            result = content_filter.apply(current_html)
            if result is not None:
                # Filter succeeded, use its output for next filter
                current_html = result
                any_success = True
            # If result is None, keep current_html unchanged for next filter

        return current_html if any_success else None
