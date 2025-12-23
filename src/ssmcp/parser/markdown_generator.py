"""Markdown generation module using Crawl4ai."""


from crawl4ai import DefaultMarkdownGenerator, PruningContentFilter

from ssmcp.config import Settings
from ssmcp.exceptions import MarkdownGeneratorError


class MarkdownGenerator:
    """Converts HTML to Markdown using Crawl4AI."""

    def __init__(self, settings: Settings) -> None:
        """Initialize the markdown generator with settings.

        Args:
            settings: Application settings containing markdown generation configuration.

        """
        self._settings = settings

    def convert(self, html: str) -> str:
        """Convert HTML to Markdown.

        Uses PruningContentFilter to remove low-content sections before conversion.

        Args:
            html: HTML content to convert to Markdown.

        Returns:
            String containing Markdown content.

        Raises:
            MarkdownGeneratorError: If MD generation failed.

        """
        content_filter = PruningContentFilter(
            threshold=self._settings.crawl4ai_pruning_threshold,
            threshold_type=self._settings.crawl4ai_threshold_type,
            min_word_threshold=self._settings.crawl4ai_min_word_threshold,
        )

        markdown_generator = DefaultMarkdownGenerator(
            content_filter=content_filter,
            options={
                "ignore_images": self._settings.crawl4ai_ignore_images,
                "ignore_links": self._settings.crawl4ai_ignore_links,
                "skip_internal_links": self._settings.crawl4ai_skip_internal_links,
                "escape_html": self._settings.crawl4ai_escape_html,
                "body_width": self._settings.crawl4ai_body_width,
                "include_sup_sub": self._settings.crawl4ai_include_sup_sub,
            },
        )

        result = markdown_generator.generate_markdown(
            input_html=html,
            content_filter=content_filter,
            citations=False,
        )

        # Use pruned markdown, fall back to raw if pruning removed too much
        output = result.fit_markdown or result.raw_markdown
        if not output:
            raise MarkdownGeneratorError("Markdown generation produced no content")

        return str(output)
