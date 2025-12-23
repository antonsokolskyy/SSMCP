"""HTML filtering module."""

from ssmcp.config import Settings
from ssmcp.parser.filters.css_selector import CssSelectorFilter
from ssmcp.parser.protocols import ContentFilter


class Filter:
    """Applies content filters to extract main content from HTML.

    Tries each filter in order and returns the first successful match.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize the filter with settings.

        Args:
            settings: Application settings containing filter configuration.

        """
        self._settings = settings
        self._filters = self._initialize_filters()

    def _initialize_filters(self) -> list[ContentFilter]:
        """Initialize content filters in priority order.

        Returns:
            List of ContentFilter instances to apply.

        """
        return [
            CssSelectorFilter(self._settings),
        ]

    def apply_all(self, html: str) -> str | None:
        """Apply filters sequentially until one matches.

        Args:
            html: HTML content to filter.

        Returns:
            String containing filtered HTML or None if no filter matched.

        """
        for content_filter in self._filters:
            result = content_filter.apply(html)
            if result:
                return result

        return None
