"""CSS selector filter for content extraction."""


from bs4 import BeautifulSoup

from ssmcp.config import Settings
from ssmcp.logger import logger


class CssSelectorFilter:
    """Extracts main content using CSS selectors.

    Tries selectors in priority order and returns the first element
    that meets the minimum word count threshold.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize the CSS selector filter.

        Args:
            settings: Application settings containing CSS selector configuration.

        """
        self._settings = settings

    def apply(self, html: str) -> str | None:
        """Find and extract the main content element.

        Tries selectors in order (e.g., article, main, #content) and returns
        the first match with enough words.

        Args:
            html: HTML content to parse.

        Returns:
            Extracted HTML element as string, or None if no match.

        """
        soup = BeautifulSoup(html, "html.parser")

        selectors = self._parse_selector_list()

        for selector in selectors:
            element = soup.select_one(selector)
            if not element:
                continue

            # Check word count to avoid selecting empty or small elements
            text = element.get_text(strip=True)
            word_count = len(text.split())

            if word_count >= self._settings.css_selector_min_words:
                logger.debug("CSS selector '%s' matched with %d words", selector, word_count)
                return str(element)

        logger.debug("No CSS selector matched among %d candidates", len(selectors))
        return None

    def _parse_selector_list(self) -> list[str]:
        """Parse the CSS selector priority list from settings string.

        Returns:
            List of CSS selector strings in priority order.

        """
        selector_str = self._settings.css_selector_priority_list
        return [s.strip() for s in selector_str.split(",") if s.strip()]
