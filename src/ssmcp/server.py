"""MCP server for web search with SearXNG and content extraction with Crawl4AI."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_http_request

from ssmcp.config import settings
from ssmcp.exceptions import SSMCPError
from ssmcp.logger import logger, setup_logging
from ssmcp.middleware.redis_middleware import RedisLoggingMiddleware
from ssmcp.oauth import OAuthTokenVerifier
from ssmcp.parser.parser import Parser
from ssmcp.searxng_client import SearXNGClient
from ssmcp.timing import timeit
from ssmcp.youtube_client import YouTubeClient

# Initialize logging as soon as possible
setup_logging()


class TypedFastMCP(FastMCP):
    """Typed FastMCP subclass with server state attribute.

    This allows proper type checking for the state attribute
    instead of using type: ignore comments.
    """

    state: "ServerState | None"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize TypedFastMCP with state set to None."""
        super().__init__(*args, **kwargs)
        self.state = None
        self.oauth_verifier = OAuthTokenVerifier() if settings.oauth_enabled else None


class ServerState:
    """Encapsulates the server dependencies and state.

    Provides a clean way to manage client lifecycles and provides them
    as dependencies to tools.
    """

    def __init__(self) -> None:
        """Initialize the server state."""
        self.searxng_client = SearXNGClient(
            search_url=settings.searxng_search_url,
            timeout=settings.searxng_timeout,
        )
        self.parser = Parser(settings)
        self.youtube_client = YouTubeClient(
            language=settings.youtube_subtitle_language,
            cookies_path=settings.youtube_cookies_path,
        )

    async def start(self) -> None:
        """Startup logic for client resources."""
        logger.info("Starting SSMCP server resources...")
        await self.parser.start()

    async def stop(self) -> None:
        """Cleanup logic for client resources."""
        logger.info("Stopping SSMCP server resources...")
        await self.parser.close()
        await self.searxng_client.close()

    async def search_and_enrich(self, query: str, ctx: Context) -> list[dict[str, Any]]:
        """Perform search and enrich results with page content.

        Args:
            query: Search query string.
            ctx: FastMCP context for progress reporting.

        Returns:
            List of enriched search results.

        """
        search_results = await self.searxng_client.search(query)
        logger.debug("Processing first %d results...", settings.searxng_max_results)
        urls_to_fetch = [r["url"] for r in search_results[:settings.searxng_max_results]]

        content_map = await self.parser.parse_pages(urls_to_fetch, ctx)
        return [{"url": url, "content": content} for url, content in content_map.items()]


@asynccontextmanager
async def lifespan(app: TypedFastMCP) -> AsyncIterator[dict[str, Any]]:
    """Manage application lifespan: initialize and cleanup HTTP clients."""
    state = ServerState()
    await state.start()

    # Attach state to the typed mcp object
    app.state = state

    # Initialize middleware if present
    for middleware in app.middleware:
        if hasattr(middleware, "startup"):
            await middleware.startup()

    try:
        yield {"state": state}
    finally:
        # Cleanup middleware if present
        for middleware in app.middleware:
            if hasattr(middleware, "shutdown"):
                await middleware.shutdown()

        await state.stop()


# Helper functions
def log_tool_call(tool_name: str, details: str, user_email: str | None) -> None:
    """Log a tool call with optional user email.

    Args:
        tool_name: Name of the tool being called
        details: Details about the tool call (e.g., query, URL)
        user_email: User email if OAuth is enabled and authenticated

    """
    if user_email:
        logger.info("[TOOL CALLED][%s] %s: %s", user_email, tool_name, details)
    else:
        logger.info("[TOOL CALLED] %s: %s", tool_name, details)


async def get_user_email() -> str | None:
    """Get user email from OAuth token if enabled.

    Returns:
        User email if OAuth is enabled and token is valid, None if OAuth is disabled

    Raises:
        ToolError: If OAuth is enabled but authentication fails
        TokenValidationError: If token format or signature is invalid
        TokenExpiredError: If token has expired
        AudienceMismatchError: If aud claim doesn't match client ID
        SubjectClaimMissingError: If sub claim is missing
        InvalidJWKSURLError: If JWKS endpoint cannot be reached

    """
    if not settings.oauth_enabled or not mcp.oauth_verifier:
        return None

    # When OAuth is enabled, authentication is required
    request = get_http_request()
    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        msg = "OAuth is enabled but Authorization header is missing or invalid"
        raise ToolError(msg)

    token = auth_header[len("Bearer "):]

    # verify_token validates the JWT and raises specific OAuth exceptions on failure
    result = await mcp.oauth_verifier.verify_token(token)
    return str(result["sub"])


def get_state() -> ServerState:
    """Get the server state from the context."""
    if mcp.state is None:
        raise RuntimeError("Server state not initialized")
    return mcp.state


def get_parser(state: ServerState) -> Parser:
    """Get the parser client from server state."""
    return state.parser


def get_youtube_client(state: ServerState) -> YouTubeClient:
    """Get the YouTube client from server state."""
    return state.youtube_client


# Add Redis middleware if enabled
mcp = TypedFastMCP("ssmcp", lifespan=lifespan)
if settings.redis_url:
    mcp.add_middleware(RedisLoggingMiddleware(redis_url=settings.redis_url))


@mcp.tool(
    title="web_search",
    description=settings.tool_web_search_desc,
)
@timeit("web_search tool")
async def web_search(
    query: Annotated[str, settings.arg_web_search_query_desc],
    ctx: Context,
) -> list[dict[str, Any]]:
    """Perform a web search and return relevant results with enriched content."""
    user_email = await get_user_email()
    log_tool_call("web_search", f"query: {query}", user_email)
    state = get_state()
    try:
        results = await state.search_and_enrich(query, ctx)
    except SSMCPError as e:
        raise ToolError(f"{type(e).__name__}: {e}") from e
    return results


@mcp.tool(
    title="web_fetch",
    description=settings.tool_web_fetch_desc,
)
@timeit("web_fetch tool")
async def web_fetch(
    url: Annotated[str, settings.arg_web_fetch_url_desc],
    ctx: Context,
) -> str:
    """Fetch content from a specified URL and convert to Markdown."""
    user_email = await get_user_email()
    log_tool_call("web_fetch", f"URL: {url}", user_email)
    parser = get_parser(get_state())
    try:
        result = await parser.parse_pages([url], ctx)
    except SSMCPError as e:
        raise ToolError(f"{type(e).__name__}: {e}") from e
    return result[url]


@mcp.tool(
    title="youtube_get_subtitles",
    description=settings.tool_youtube_get_subtitles_desc,
)
@timeit("youtube_get_subtitles tool")
async def youtube_get_subtitles(
    url: Annotated[str, settings.arg_youtube_get_subtitles_url_desc],
) -> str:
    """Get subtitles from a YouTube video and return the text content."""
    user_email = await get_user_email()
    log_tool_call("youtube_get_subtitles", f"URL: {url}", user_email)
    youtube = get_youtube_client(get_state())
    try:
        result = await youtube.get_subtitles(url)
    except SSMCPError as e:
        raise ToolError(f"{type(e).__name__}: {e}") from e
    return result


def main() -> None:
    """Run the MCP server."""
    mcp.run(transport="streamable-http", host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
