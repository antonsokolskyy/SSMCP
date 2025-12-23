"""HTML extraction module using Crawl4ai."""

import asyncio
from typing import NamedTuple

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

from ssmcp.config import Settings
from ssmcp.exceptions import Crawl4AIError, ExtractorError
from ssmcp.logger import logger


class ExtractionResult(NamedTuple):
    """Result of HTML extraction."""

    raw_html: str
    selected_html: str


class Extractor:
    """HTML extractor using a pool of browser instances.

    Uses a queue to limit concurrent browser instances and reuse them across requests.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize the extractor with settings.

        Args:
            settings: Application settings containing Crawl4ai configuration.

        """
        self._settings = settings
        self._crawler_queue: asyncio.Queue[AsyncWebCrawler] = asyncio.Queue()
        self._crawlers: list[AsyncWebCrawler] = []

    async def start(self) -> None:
        """Initialize the browser pool.

        Uses Chromium with stealth mode to reduce bot detection.

        """
        pool_size = self._settings.crawl4ai_browser_pool_size
        logger.info("Initializing browser pool with %d instances...", pool_size)

        browser_config = BrowserConfig(
            browser_type="chromium",
            headless=True,
            viewport_width=self._settings.crawl4ai_viewport_width,
            viewport_height=self._settings.crawl4ai_viewport_height,
            enable_stealth=True,
            user_agent_mode="random",
            text_mode=False,
            light_mode=True,
            ignore_https_errors=True,
            verbose=False,
        )

        for _ in range(pool_size):
            crawler = AsyncWebCrawler(config=browser_config)
            await crawler.start()
            self._crawlers.append(crawler)
            self._crawler_queue.put_nowait(crawler)

        logger.debug("Browser pool initialized.")

    async def close(self) -> None:
        """Close all browsers in the pool."""
        logger.info("Closing browser pool...")
        for crawler in self._crawlers:
            await crawler.close()
        self._crawlers.clear()

        # Drain queue
        while not self._crawler_queue.empty():
            try:
                self._crawler_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        logger.debug("Browser pool closed.")

    async def extract_html(self, url_or_html: str) -> ExtractionResult:
        """Extract or clean HTML using a browser from the pool.

        Supports two modes:
        - URL: Navigates to the page and extracts HTML.
        - Raw HTML: Processes the string using Crawl4AI (prefix 'raw:').

        Args:
            url_or_html: URL to fetch or raw HTML string (prefixed with 'raw:').

        Returns:
            ExtractionResult(NamedTuple) with raw and selected HTML.

        Raises:
            ExtractorError: If extraction fails
            Crawl4AIError: If something went wrong inside Crawl4AI library

        """
        is_url = url_or_html.startswith(("http://", "https://"))

        crawler_config = self._get_crawler_config()

        # Get a crawler from the pool (blocks if none available)
        crawler = await self._crawler_queue.get()
        try:
            target = url_or_html if is_url else f"raw:{url_or_html}"
            mode = "URL" if is_url else "HTML"
            if is_url:
                logger.debug("[EXTRACTION STARTED] (mode=%s) URL: %s", mode, url_or_html)
            else:
                logger.debug("[EXTRACTION STARTED] (mode=%s)", mode)

            result = await crawler.arun(url=target, config=crawler_config)

            if not result.success:
                error_msg = getattr(result, "error_message", "Unknown Crawl4AI error")
                raise Crawl4AIError(error_msg)

            raw_html = result.html
            selected_html = (
                result.cleaned_html
                if self._settings.extraction_html_type == "cleaned_html"
                else result.fit_html
            )

            if not raw_html and not selected_html:
                raise ExtractorError("No HTML content extracted")

            return ExtractionResult(raw_html=raw_html or "", selected_html=selected_html or "")

        finally:
            # Always return the crawler to the pool
            self._crawler_queue.put_nowait(crawler)

    def _get_crawler_config(self) -> CrawlerRunConfig:
        """Build crawler configuration from settings.

        Returns:
            CrawlerRunConfig instance with settings from application config.

        """
        return CrawlerRunConfig(
            wait_until=self._settings.crawl4ai_wait_until,
            page_timeout=self._settings.crawl4ai_page_timeout,
            delay_before_return_html=self._settings.crawl4ai_delay_before_return_html,
            scan_full_page=True,
            scroll_delay=self._settings.crawl4ai_scroll_delay,
            max_scroll_steps=self._settings.crawl4ai_max_scroll_steps,
            word_count_threshold=self._settings.crawl4ai_word_count_threshold,
            excluded_tags=self._settings.crawl4ai_excluded_tags.split(","),
            exclude_external_links=self._settings.crawl4ai_exclude_external_links,
            exclude_social_media_links=True,
            exclude_external_images=True,
            table_score_threshold=self._settings.crawl4ai_table_score_threshold,
            cache_mode=self._settings.crawl4ai_cache_mode,
            stream=True,
            verbose=False,
        )
