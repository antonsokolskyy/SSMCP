"""Application configuration using Pydantic Settings.

Environment variables are automatically mapped to Settings fields.
"""

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Required settings will cause validation errors if missing,
    ensuring the application fails early with clear error messages.
    """

    # --- Connectivity & Infrastructure ---
    ssmcp_debug: bool = False

    # --- SearXNG ---
    searxng_search_url: str
    searxng_max_results: int = 5
    searxng_timeout: float = 5.0

    # --- Crawl4AI Browser ---
    crawl4ai_viewport_width: int = 1280
    crawl4ai_viewport_height: int = 900
    crawl4ai_browser_pool_size: int = 5

    # --- Crawl4AI Crawler ---
    crawl4ai_wait_until: str = "domcontentloaded"
    crawl4ai_page_timeout: int = 10000
    crawl4ai_max_scroll_steps: int = 0
    crawl4ai_scroll_delay: float = 0.5
    crawl4ai_delay_before_return_html: float = 0.5
    crawl4ai_cache_mode: str = "enabled"

    # --- Crawl4AI Content Filtering ---
    crawl4ai_word_count_threshold: int = 1
    crawl4ai_min_word_threshold: int = 1
    crawl4ai_pruning_threshold: float = 0.30
    crawl4ai_threshold_type: str = "dynamic"
    crawl4ai_excluded_tags: str = (
        "nav,footer,header,aside,script,style,noscript,form,button,iframe,svg,meta"
    )
    crawl4ai_table_score_threshold: int = 1
    crawl4ai_exclude_external_links: bool = True

    # --- Crawl4AI Markdown Generation ---
    crawl4ai_ignore_links: bool = True
    crawl4ai_skip_internal_links: bool = True
    crawl4ai_ignore_images: bool = True
    crawl4ai_escape_html: bool = True
    crawl4ai_body_width: int = 0
    crawl4ai_include_sup_sub: bool = True

    # --- CSS Selector Strategy ---
    css_selector_priority_list: str = (
        'article, main, [role="main"], .article, .article-content, .page-content, '
        ".markdown, #article, #content, #main, #page, .content"
    )
    css_selector_min_words: int = 50

    # --- HTML Type Selection ---
    extraction_html_type: str = "fit_html"

    # --- Content Extraction & YouTube ---
    youtube_subtitle_language: str = "en"
    youtube_cookies_path: str = "/app/deploy/docker/ssmcp/cookies.txt"

    # --- Network Interface ---
    host: str = "0.0.0.0"
    port: int = 8000

    # --- Redis ---
    redis_url: str = ""
    redis_key_prefix: str = "ssmcp"
    redis_expiration_seconds: int = 3600

    # --- OAuth Authentication ---
    oauth_enabled: bool = False
    oauth_jwks_url: str = ""
    oauth_client_id: str = ""
    oauth_issuer: str = ""

    @model_validator(mode="after")
    def validate_oauth_config(self) -> "Settings":
        """Validate OAuth configuration when enabled.

        Raises:
            ValueError: If OAuth is enabled but required fields are missing

        """
        if self.oauth_enabled:
            if not self.oauth_jwks_url:
                msg = "OAUTH_JWKS_URL must be set when OAUTH_ENABLED=true"
                raise ValueError(msg)
            if not self.oauth_client_id:
                msg = "OAUTH_CLIENT_ID must be set when OAUTH_ENABLED=true"
                raise ValueError(msg)
            if not self.oauth_issuer:
                msg = "OAUTH_ISSUER must be set when OAUTH_ENABLED=true"
                raise ValueError(msg)
        return self

    # --- Tool Metadata ---
    # Tool descriptions are stored here so they can be updated via environment
    # variables without code changes.
    tool_web_search_desc: str = (
        "Perform a web search and return relevant results.\n\n"
        "Each search result contains:\n"
        "- url (str): The webpage URL\n"
        "- content (str): Page content in MD format"
    )
    tool_web_fetch_desc: str = (
        "Fetch content from a specified URL.\n\n"
        "Returns the page content in Markdown format."
    )
    tool_youtube_get_subtitles_desc: str = (
        "Get subtitles/captions from a YouTube video and return the text content."
    )

    # Tool argument descriptions
    arg_web_search_query_desc: str = "Search query or keywords to find relevant web content."
    arg_web_fetch_url_desc: str = "The URL to fetch content from"
    arg_youtube_get_subtitles_url_desc: str = "YouTube video URL to get subtitles from"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance.

    Uses lru_cache to ensure the .env file is only parsed once
    and all modules share the same settings instance.

    Returns:
        Settings instance with application configuration.

    Raises:
        ValidationError: If required environment variables are missing.

    """
    # Pydantic Settings populates required fields from environment variables
    # at runtime, so mypy incorrectly reports missing constructor arguments.
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
