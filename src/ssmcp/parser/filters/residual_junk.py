"""Residual junk filter for removing UI artifacts from extracted content."""

import re
from typing import TYPE_CHECKING, ClassVar

from bs4 import BeautifulSoup

from ssmcp.config import Settings
from ssmcp.logger import logger

if TYPE_CHECKING:
    from bs4.element import Tag


class ResidualJunkFilter:
    """Removes residual UI junk from content after CSS selection."""

    # Tags that should never be removed themselves
    PROTECTED_TAGS: ClassVar[set[str]] = {
        "code", "pre", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6"
    }
    # Tags where children are also protected
    PROTECTED_CONTAINER_TAGS: ClassVar[set[str]] = {"code", "pre", "blockquote"}

    def __init__(self, settings: Settings) -> None:
        """Initialize the residual junk filter."""
        self._enabled = settings.junk_filter_enabled
        self._letter_ratio_threshold = settings.junk_filter_letter_ratio_threshold

    def apply(self, html: str) -> str | None:
        """Remove residual junk elements from HTML content."""
        if not self._enabled:
            return html

        soup = BeautifulSoup(html, "html.parser")
        removed_count = 0
        seen_texts: set[str] = set()

        for element in soup.find_all():
            # Skip non-tag elements
            if not hasattr(element, "name"):
                continue

            # Skip if already removed
            if element.parent is None:
                continue

            # Skip protected tags - never remove these
            if element.name in self.PROTECTED_TAGS:
                continue

            # Skip if inside protected containers
            if self._is_inside_protected_containers(element):
                continue

            # Check removal conditions
            if self._should_remove(element, seen_texts):
                element.decompose()
                removed_count += 1

        if removed_count > 0:
            logger.debug("ResidualJunkFilter removed %d junk elements", removed_count)

        text_content = soup.get_text(strip=True)
        return str(soup) if text_content else None

    def _is_inside_protected_containers(self, element: "Tag") -> bool:
        """Check if element is inside protected containers."""
        return any(parent.name in self.PROTECTED_CONTAINER_TAGS for parent in element.parents)

    def _should_remove(self, element: "Tag", seen_texts: set[str]) -> bool:
        """Determine if element should be removed."""
        # Remove elements with role="tooltip"
        if element.get("role") == "tooltip":
            return True

        text = element.get_text(strip=True)

        # Remove if no spaces in text (single word/junk)
        if " " not in text:
            return True

        # Remove if too few letters compared to other characters
        if self._has_low_letter_ratio(text, self._letter_ratio_threshold):
            return True

        # Remove duplicate text from leaf nodes only (avoid parent/child conflicts)
        # A leaf node has no children with text
        is_leaf = not any(
            child.get_text(strip=True) for child in element.find_all(recursive=False)
        )
        if is_leaf:
            if text in seen_texts:
                return True
            seen_texts.add(text)

        return False

    def _has_low_letter_ratio(self, text: str, threshold: float) -> bool:
        """Check if text has too few letters compared to other characters.

        Args:
            text: Text to check.
            threshold: Minimum ratio of letters to total characters (default 0.5).

        Returns:
            True if letter ratio is below threshold.

        """
        # Remove whitespace for calculation
        clean_text = text.replace(" ", "").replace("\t", "").replace("\n", "")
        if not clean_text:
            return False

        # Count letters (a-z, A-Z)
        letters = len(re.findall(r"[a-zA-Z]", clean_text))
        total = len(clean_text)

        return letters / total < threshold
