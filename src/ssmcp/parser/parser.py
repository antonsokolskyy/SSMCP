"""Main parser module that orchestrates the parsing pipeline."""

import asyncio
import logging

from fastmcp import Context

from ssmcp.config import Settings
from ssmcp.exceptions import SSMCPError
from ssmcp.logger import logger
from ssmcp.parser.extractor import Extractor
from ssmcp.parser.filter import Filter
from ssmcp.parser.markdown_generator import MarkdownGenerator
from ssmcp.timing import timeit


class Parser:
    """Coordinates HTML extraction, filtering, and Markdown conversion.

    Pipeline: URL -> HTML extraction -> Content filtering -> Markdown conversion.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize the parser with settings.

        Args:
            settings: Application settings containing all configuration.

        """
        self._settings = settings
        self._extractor = Extractor(settings)
        self._filter = Filter(settings)
        self._markdown_generator = MarkdownGenerator(settings)

    async def start(self) -> None:
        """Initialize the extractor's browser pool."""
        await self._extractor.start()

    async def close(self) -> None:
        """Close the extractor's browser pool."""
        await self._extractor.close()

    @timeit("Pages parsing", logging.DEBUG)
    async def parse_pages(self, urls: list[str], ctx: Context) -> dict[str, str]:
        """Parse multiple webpages concurrently.

        Args:
            urls: List of URLs to parse.
            ctx: FastMCP context for progress reporting.

        Returns:
            Dictionary mapping URLs to their Markdown content.

        """
        total_urls = len(urls)
        completed_count = 0
        await ctx.report_progress(0, total_urls, f"Starting parse of {total_urls} page(s)")

        async def _tracked_process(url: str) -> tuple[str, str]:
            nonlocal completed_count
            content = await self._process_single_url(url)
            completed_count += 1
            status_msg = f"Completed {completed_count}/{total_urls}: {url}"
            await ctx.report_progress(completed_count, total_urls, status_msg)
            return (url, content)

        tasks = [_tracked_process(url) for url in urls]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        # Build dict, skipping expected SSMCP errors but re-raising unexpected ones
        # e.g. skipping failed URLs for resilience
        result_dict: dict[str, str] = {}
        for item in results_list:
            if isinstance(item, SSMCPError):
                logger.error("Failed to parse URL: %s", item)
                continue
            if isinstance(item, BaseException):
                raise item
            url, content = item
            result_dict[url] = content

        return result_dict

    async def _process_single_url(self, url: str) -> str:
        """Process a single URL through the pipeline.

        Args:
            url: URL to process.

        Returns:
            String containing Markdown content.

        """
        return await self._run_pipeline(url)

    async def _run_pipeline(self, url: str) -> str:
        """Run the extraction -> filtering -> markdown pipeline for a URL.

        Args:
            url: URL to process through the pipeline.

        Returns:
            String containing Markdown content.

        """
        # 1. Extract HTML from the page
        extraction_result = await self._extractor.extract_html(url)

        raw_html = extraction_result.raw_html
        selected_html = extraction_result.selected_html

        # 2. Try to find main content using CSS selectors
        logger.debug("[FILTERING STARTED] for %s", url)
        filtered_html = await asyncio.to_thread(self._filter.apply_all, raw_html)

        # 3. Choose which HTML to convert:
        #    - If filter matched, re-extract the filtered fragment for cleaning
        #    - Otherwise, use the pre-selected HTML from step 1
        html_to_convert = selected_html
        if filtered_html is not None:
            re_extraction_result = await self._extractor.extract_html(filtered_html)
            html_to_convert = re_extraction_result.selected_html

        # 4. Convert to Markdown
        logger.debug("[MARKDOWN GENERATION STARTED] for %s", url)
        return await asyncio.to_thread(self._markdown_generator.convert, html_to_convert)
