"""Protocol definitions for the parser package.

Contains structural typing protocols that define interfaces for
parser components, enabling better type checking and extensibility.
"""

from typing import Protocol


class ContentFilter(Protocol):
    """Protocol defining the interface for content filters.

    Content filters extract main content from HTML by applying
    various strategies (CSS selectors, heuristics, etc.).

    Implementations should:
    - Return the filtered HTML string if content was found
    - Return None if no suitable content was found
    """

    def apply(self, html: str) -> str | None:
        """Apply the filter to extract main content from HTML.

        Args:
            html: The raw HTML content to filter.

        Returns:
            The filtered HTML content, or None if no content was found.

        """
        ...
