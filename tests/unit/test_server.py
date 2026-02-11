"""Unit tests for MCP server."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastmcp import Context
from fastmcp.exceptions import ToolError

from ssmcp.exceptions import ParserError, SearXNGError, YoutubeError
from ssmcp.server import (
    ServerState,
    TypedFastMCP,
    get_parser,
    get_state,
    get_user_id,
    get_youtube_client,
    lifespan,
    log_tool_call,
    web_fetch,
    web_search,
    youtube_get_subtitles,
)

# Constants for log message argument counts
LOG_ARGS_WITHOUT_USER = 3  # format_str, tool_name, details
LOG_ARGS_WITH_USER = 4  # format_str, user_id, tool_name, details

# Constants for test values
TEST_MAX_RESULTS = 2
TEST_PORT = 8000
TEST_TIMEOUT = 5.0


@pytest.fixture
def mock_settings() -> MagicMock:
    """Create mock settings for testing."""
    settings = MagicMock()
    settings.searxng_search_url = "http://test.com/search"
    settings.searxng_timeout = TEST_TIMEOUT
    settings.searxng_max_results = 5
    settings.youtube_subtitle_language = "en"
    settings.youtube_cookies_path = "/app/deploy/docker/ssmcp/cookies.txt"
    settings.oauth_enabled = False
    settings.oauth_jwks_url = ""
    settings.oauth_client_id = ""
    settings.oauth_issuer = ""
    settings.redis_url = ""
    settings.host = "127.0.0.1"
    settings.port = TEST_PORT
    # LLM Summarization settings - disabled by default for tests
    settings.llm_summarization_enabled = False
    settings.llm_api_key = ""
    settings.llm_api_url = ""
    settings.llm_model = ""
    settings.llm_summarization_prompt = "Test prompt"
    return settings


@pytest.fixture
def mock_context() -> AsyncMock:
    """Create a mock FastMCP Context."""
    ctx = AsyncMock(spec=Context)
    ctx.report_progress = AsyncMock()
    return ctx


class TestTypedFastMCP:
    """Test TypedFastMCP class."""

    def test_init_sets_state_to_none(self) -> None:
        """Test that TypedFastMCP initializes with state as None."""
        with patch("ssmcp.server.settings") as mock_settings:
            mock_settings.oauth_enabled = False
            mcp = TypedFastMCP("test")
            assert mcp.state is None
            assert mcp.oauth_verifier is None

    def test_init_with_oauth_enabled(self) -> None:
        """Test that TypedFastMCP initializes OAuth verifier when enabled."""
        with patch("ssmcp.server.settings") as mock_settings:
            mock_settings.oauth_enabled = True
            mock_settings.oauth_jwks_url = "https://auth.com/jwks"
            mcp = TypedFastMCP("test")
            assert mcp.state is None
            assert mcp.oauth_verifier is not None


class TestServerState:
    """Test ServerState class."""

    @pytest.mark.asyncio
    async def test_init_creates_clients(self, mock_settings: MagicMock) -> None:
        """Test that ServerState initializes all clients."""
        with patch("ssmcp.server.settings", mock_settings):
            state = ServerState()
            assert state.searxng_client is not None
            assert state.parser is not None
            assert state.youtube_client is not None

    @pytest.mark.asyncio
    async def test_init_without_summarization(self, mock_settings: MagicMock) -> None:
        """Test that ServerState doesn't create summarization service when disabled."""
        mock_settings.llm_summarization_enabled = False
        with patch("ssmcp.server.settings", mock_settings):
            state = ServerState()
            assert state.summarization_service is None

    @pytest.mark.asyncio
    async def test_init_with_summarization(self, mock_settings: MagicMock) -> None:
        """Test that ServerState creates summarization service when enabled."""
        mock_settings.llm_summarization_enabled = True
        mock_settings.llm_api_key = "test-key"
        mock_settings.llm_model = "gpt-4"
        mock_settings.llm_api_url = "https://custom.api/v1"
        mock_settings.llm_summarization_prompt = "Test prompt"

        with (
            patch("ssmcp.server.settings", mock_settings),
            patch("ssmcp.server.LLMClient") as mock_llm_client_class,
        ):
            state = ServerState()
            assert state.summarization_service is not None
            mock_llm_client_class.assert_called_once_with(
                api_key="test-key", api_url="https://custom.api/v1"
            )

    @pytest.mark.asyncio
    async def test_stop_closes_llm_client(self, mock_settings: MagicMock) -> None:
        """Test that stop() closes LLM client if service exists."""
        mock_settings.llm_summarization_enabled = True
        mock_settings.llm_api_key = "test-key"
        mock_settings.llm_model = "gpt-4"
        mock_settings.llm_summarization_prompt = "Test prompt"

        with (
            patch("ssmcp.server.settings", mock_settings),
            patch("ssmcp.server.LLMClient") as mock_llm_client_class,
        ):
            mock_llm_client = MagicMock()
            mock_llm_client.close = AsyncMock()
            mock_llm_client_class.return_value = mock_llm_client

            state = ServerState()
            await state.stop()
            mock_llm_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_initializes_parser(self, mock_settings: MagicMock) -> None:
        """Test that start() initializes parser resources."""
        with patch("ssmcp.server.settings", mock_settings):
            state = ServerState()
            with patch.object(state.parser, "start", new_callable=AsyncMock) as mock_start:
                await state.start()
                mock_start.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_cleans_up_resources(self, mock_settings: MagicMock) -> None:
        """Test that stop() cleans up all resources."""
        with patch("ssmcp.server.settings", mock_settings):
            state = ServerState()
            with (
                patch.object(state.parser, "close", new_callable=AsyncMock) as mock_parser_close,
                patch.object(
                    state.searxng_client, "close", new_callable=AsyncMock
                ) as mock_searxng_close,
            ):
                await state.stop()
                mock_parser_close.assert_called_once()
                mock_searxng_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_and_enrich_success(
        self, mock_settings: MagicMock, mock_context: AsyncMock
    ) -> None:
        """Test successful search and enrichment flow."""
        # Create more results than max_results to test slicing
        mock_settings.searxng_max_results = TEST_MAX_RESULTS

        with patch("ssmcp.server.settings", mock_settings):
            state = ServerState()

            mock_results = [
                {"title": "Result 1", "url": "http://example1.com", "snippet": "Snippet 1"},
                {"title": "Result 2", "url": "http://example2.com", "snippet": "Snippet 2"},
                {"title": "Result 3", "url": "http://example3.com", "snippet": "Snippet 3"},
            ]

            with (
                patch.object(
                    state.searxng_client, "search", new_callable=AsyncMock
                ) as mock_search,
                patch.object(
                    state.parser, "parse_pages", new_callable=AsyncMock
                ) as mock_parse,
            ):
                mock_search.return_value = mock_results
                mock_parse.return_value = {
                    "http://example1.com": "# Content 1",
                    "http://example2.com": "# Content 2",
                }

                result = await state.search_and_enrich("test query", mock_context)

                assert len(result) == TEST_MAX_RESULTS
                assert result[0]["url"] == "http://example1.com"
                assert result[0]["content"] == "# Content 1"
                assert result[1]["url"] == "http://example2.com"
                assert result[1]["content"] == "# Content 2"

                # Verify only max_results URLs were processed
                mock_parse.assert_called_once()
                call_urls = mock_parse.call_args[0][0]
                assert len(call_urls) == TEST_MAX_RESULTS


class TestLogToolCall:
    """Test log_tool_call function."""

    @patch("ssmcp.server.logger")
    def test_log_without_user_id(self, mock_logger: MagicMock) -> None:
        """Test logging without user ID."""
        log_tool_call("web_search", "query: test", None)

        mock_logger.info.assert_called_once()
        args = mock_logger.info.call_args[0]
        # The logger uses string formatting: "[TOOL CALLED] %s: %s"
        assert len(args) == LOG_ARGS_WITHOUT_USER
        assert args[0] == "[TOOL CALLED] %s: %s"
        assert args[1] == "web_search"
        assert args[2] == "query: test"

    @patch("ssmcp.server.logger")
    def test_log_with_user_id(self, mock_logger: MagicMock) -> None:
        """Test logging with user ID."""
        log_tool_call("web_fetch", "URL: http://example.com", "user123")

        mock_logger.info.assert_called_once()
        args = mock_logger.info.call_args[0]
        # The logger uses string formatting: "[TOOL CALLED][%s] %s: %s"
        assert len(args) == LOG_ARGS_WITH_USER
        assert args[0] == "[TOOL CALLED][%s] %s: %s"
        assert args[1] == "user123"
        assert args[2] == "web_fetch"
        assert args[3] == "URL: http://example.com"


class TestGetUserId:
    """Test get_user_id function."""

    @pytest.mark.asyncio
    async def test_oauth_disabled_returns_none(self) -> None:
        """Test that get_user_id returns None when OAuth is disabled."""
        with patch("ssmcp.server.settings") as mock_settings:
            mock_settings.oauth_enabled = False

            result = await get_user_id()
            assert result is None

    @pytest.mark.asyncio
    async def test_oauth_enabled_no_header_raises_error(self) -> None:
        """Test that missing Authorization header raises ToolError."""
        with patch("ssmcp.server.settings") as mock_settings:
            mock_settings.oauth_enabled = True

            with patch("ssmcp.server.mcp") as mock_mcp:
                mock_mcp.oauth_verifier = MagicMock()

                # Mock the request context to return empty auth header
                mock_request = MagicMock()
                mock_request.headers.get.return_value = ""

                with (
                    patch("ssmcp.server.get_http_request", return_value=mock_request),
                    pytest.raises(ToolError, match="Authorization header is missing"),
                ):
                    await get_user_id()

    @pytest.mark.asyncio
    async def test_oauth_enabled_valid_token_returns_user_id(self) -> None:
        """Test that valid token returns user ID."""
        with patch("ssmcp.server.settings") as mock_settings:
            mock_settings.oauth_enabled = True

            with patch("ssmcp.server.mcp") as mock_mcp:
                mock_verifier = AsyncMock()
                mock_verifier.verify_token.return_value = {"sub": "user@example.com"}
                mock_mcp.oauth_verifier = mock_verifier

                mock_request = MagicMock()
                mock_request.headers.get.return_value = "Bearer valid_token"

                with patch("ssmcp.server.get_http_request", return_value=mock_request):
                    result = await get_user_id()
                    assert result == "user@example.com"
                    mock_verifier.verify_token.assert_called_once_with("valid_token")


class TestGetState:
    """Test get_state function."""

    def test_get_state_returns_state_when_initialized(self) -> None:
        """Test that get_state returns state when initialized."""
        with patch("ssmcp.server.mcp") as mock_mcp:
            mock_state = MagicMock()
            mock_mcp.state = mock_state

            result = get_state()
            assert result == mock_state

    def test_get_state_raises_when_not_initialized(self) -> None:
        """Test that get_state raises RuntimeError when state is None."""
        with patch("ssmcp.server.mcp") as mock_mcp:
            mock_mcp.state = None

            with pytest.raises(RuntimeError, match="Server state not initialized"):
                get_state()


class TestDependencyGetters:
    """Test dependency getter functions."""

    def test_get_parser_returns_parser_from_state(self) -> None:
        """Test that get_parser returns parser from state."""
        mock_state = MagicMock()
        mock_parser = MagicMock()
        mock_state.parser = mock_parser

        result = get_parser(mock_state)
        assert result == mock_parser

    def test_get_youtube_client_returns_client_from_state(self) -> None:
        """Test that get_youtube_client returns client from state."""
        mock_state = MagicMock()
        mock_client = MagicMock()
        mock_state.youtube_client = mock_client

        result = get_youtube_client(mock_state)
        assert result == mock_client


class TestLifespan:
    """Test lifespan context manager."""

    @pytest.mark.asyncio
    async def test_lifespan_initializes_and_cleans_up(self) -> None:
        """Test that lifespan initializes state and cleans up properly."""
        with patch("ssmcp.server.settings") as mock_settings:
            mock_settings.redis_url = ""

            with patch("ssmcp.server.TypedFastMCP") as mock_app:
                mock_app.middleware = []
                mock_app.state = None

                with patch("ssmcp.server.ServerState") as mock_state_class:
                    mock_state = AsyncMock()
                    mock_state_class.return_value = mock_state

                    async with lifespan(mock_app) as context:
                        # Verify state was started and attached
                        mock_state.start.assert_called_once()
                        assert mock_app.state == mock_state
                        assert context["state"] == mock_state

                    # Verify cleanup occurred
                    mock_state.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_lifespan_with_middleware_lifecycle(self) -> None:
        """Test that lifespan calls middleware startup/shutdown."""
        with patch("ssmcp.server.settings") as mock_settings:
            mock_settings.redis_url = ""

            with patch("ssmcp.server.TypedFastMCP") as mock_app:
                mock_middleware = AsyncMock()
                mock_middleware.startup = AsyncMock()
                mock_middleware.shutdown = AsyncMock()
                mock_app.middleware = [mock_middleware]
                mock_app.state = None

                with patch("ssmcp.server.ServerState") as mock_state_class:
                    mock_state = AsyncMock()
                    mock_state_class.return_value = mock_state

                    async with lifespan(mock_app):
                        mock_middleware.startup.assert_called_once()

                    mock_middleware.shutdown.assert_called_once()


class TestMCPTools:
    """Test MCP tool functions."""

    @pytest.mark.asyncio
    async def test_web_search_tool_success(self, mock_context: AsyncMock) -> None:
        """Test web_search tool with mocked dependencies."""
        # Access the underlying function via .fn attribute
        tool_fn = web_search.fn

        with (
            patch("ssmcp.server.get_user_id", new_callable=AsyncMock, return_value=None),
            patch("ssmcp.server.get_state") as mock_get_state,
        ):
            mock_state = MagicMock()
            mock_state.search_and_enrich = AsyncMock(return_value=[
                {"url": "http://example.com", "content": "# Content"}
            ])
            mock_get_state.return_value = mock_state

            result = await tool_fn("test query", mock_context)

            assert len(result) == 1
            assert result[0]["url"] == "http://example.com"
            assert result[0]["content"] == "# Content"
            mock_state.search_and_enrich.assert_called_once_with("test query", mock_context)

    @pytest.mark.asyncio
    async def test_web_search_tool_wraps_ssmcp_error(self, mock_context: AsyncMock) -> None:
        """Test web_search wraps SSMCPError in ToolError."""
        tool_fn = web_search.fn

        with (
            patch("ssmcp.server.get_user_id", new_callable=AsyncMock, return_value=None),
            patch("ssmcp.server.get_state") as mock_get_state,
            pytest.raises(ToolError, match="SearXNGError"),
        ):
            mock_state = MagicMock()
            mock_state.search_and_enrich = AsyncMock(side_effect=SearXNGError("Search failed"))
            mock_get_state.return_value = mock_state

            await tool_fn("query", mock_context)

    @pytest.mark.asyncio
    async def test_web_search_tool_with_oauth_user(self, mock_context: AsyncMock) -> None:
        """Test web_search tool with authenticated user."""
        tool_fn = web_search.fn

        with (
            patch("ssmcp.server.get_user_id", new_callable=AsyncMock, return_value="user123"),
            patch("ssmcp.server.get_state") as mock_get_state,
            patch("ssmcp.server.logger") as mock_logger,
        ):
            mock_state = MagicMock()
            mock_state.search_and_enrich = AsyncMock(return_value=[])
            mock_get_state.return_value = mock_state

            await tool_fn("query", mock_context)

            # Verify user ID is logged
            mock_logger.info.assert_called_once()
            args = mock_logger.info.call_args[0]
            assert "[TOOL CALLED][%s] %s: %s" in args[0]
            assert args[1] == "user123"

    @pytest.mark.asyncio
    async def test_web_fetch_tool_success(self, mock_context: AsyncMock) -> None:
        """Test web_fetch tool with mocked dependencies."""
        tool_fn = web_fetch.fn

        with (
            patch("ssmcp.server.get_user_id", new_callable=AsyncMock, return_value=None),
            patch("ssmcp.server.get_state") as mock_get_state,
        ):
            mock_state = MagicMock()
            mock_parser = MagicMock()
            mock_parser.parse_pages = AsyncMock(return_value={"http://example.com": "# Content"})
            mock_state.parser = mock_parser
            mock_get_state.return_value = mock_state

            result = await tool_fn("http://example.com", mock_context)

            assert result == "# Content"
            mock_parser.parse_pages.assert_called_once_with(["http://example.com"], mock_context)

    @pytest.mark.asyncio
    async def test_web_fetch_tool_wraps_ssmcp_error(self, mock_context: AsyncMock) -> None:
        """Test web_fetch wraps SSMCPError in ToolError."""
        tool_fn = web_fetch.fn

        with (
            patch("ssmcp.server.get_user_id", new_callable=AsyncMock, return_value=None),
            patch("ssmcp.server.get_state") as mock_get_state,
            pytest.raises(ToolError, match="ParserError"),
        ):
            mock_state = MagicMock()
            mock_parser = MagicMock()
            mock_parser.parse_pages = AsyncMock(side_effect=ParserError("Parse failed"))
            mock_state.parser = mock_parser
            mock_get_state.return_value = mock_state

            await tool_fn("http://example.com", mock_context)

    @pytest.mark.asyncio
    async def test_youtube_get_subtitles_tool_success(self) -> None:
        """Test youtube_get_subtitles tool with mocked dependencies."""
        tool_fn = youtube_get_subtitles.fn

        with (
            patch("ssmcp.server.get_user_id", new_callable=AsyncMock, return_value=None),
            patch("ssmcp.server.get_state") as mock_get_state,
        ):
            mock_state = MagicMock()
            mock_youtube = MagicMock()
            mock_youtube.get_subtitles = AsyncMock(return_value="[00:00:00] Hello world")
            mock_state.youtube_client = mock_youtube
            mock_get_state.return_value = mock_state

            result = await tool_fn("https://youtube.com/watch?v=123")

            assert result == "[00:00:00] Hello world"
            mock_youtube.get_subtitles.assert_called_once_with("https://youtube.com/watch?v=123")

    @pytest.mark.asyncio
    async def test_youtube_get_subtitles_tool_wraps_ssmcp_error(self) -> None:
        """Test youtube_get_subtitles wraps SSMCPError in ToolError."""
        tool_fn = youtube_get_subtitles.fn

        with (
            patch("ssmcp.server.get_user_id", new_callable=AsyncMock, return_value=None),
            patch("ssmcp.server.get_state") as mock_get_state,
            pytest.raises(ToolError, match="YoutubeError"),
        ):
            mock_state = MagicMock()
            mock_youtube = MagicMock()
            mock_youtube.get_subtitles = AsyncMock(side_effect=YoutubeError("Download failed"))
            mock_state.youtube_client = mock_youtube
            mock_get_state.return_value = mock_state

            await tool_fn("https://youtube.com/watch?v=123")
