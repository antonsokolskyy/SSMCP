import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastmcp.server.middleware import MiddlewareContext

from ssmcp.config import settings
from ssmcp.middleware.redis_middleware import RedisLoggingMiddleware

REDIS_TTL_SECONDS = 3600  # 1 hour
KEY_PARTS_COUNT = 3  # prefix:timestamp:unique_id
UNIQUE_ID_LENGTH = 8  # 4-byte hex = 8 characters


@pytest.mark.asyncio
async def test_middleware_no_redis() -> None:
    """Test middleware when Redis is not configured."""
    middleware = RedisLoggingMiddleware(redis_url="")

    context = MagicMock(spec=MiddlewareContext)
    call_next = AsyncMock(return_value="ok")

    result = await middleware.on_call_tool(context, call_next)

    assert result == "ok"
    call_next.assert_called_once_with(context)
    assert middleware.redis_client is None


@pytest.mark.asyncio
async def test_middleware_with_redis() -> None:
    """Test middleware when Redis is configured and working."""
    redis_url = "redis://redis:6379"

    with patch("ssmcp.middleware.redis_middleware.Redis.from_url") as mock_from_url:
        mock_redis = AsyncMock()
        mock_from_url.return_value = mock_redis

        middleware = RedisLoggingMiddleware(redis_url=redis_url)
        await middleware.startup()

        context = MagicMock(spec=MiddlewareContext)
        context.message = MagicMock()
        context.message.name = "test_tool"
        context.message.arguments = {"q": "test"}

        call_next = AsyncMock(return_value="tool response")

        result = await middleware.on_call_tool(context, call_next)

        assert result == "tool response"
        assert mock_redis.setex.called

        # Check data stored in Redis
        args, _ = mock_redis.setex.call_args
        key = args[0]
        ttl = args[1]
        data = json.loads(args[2])

        # Verify key format: prefix:timestamp:unique_id
        key_parts = key.split(":")
        assert len(key_parts) == KEY_PARTS_COUNT
        assert key_parts[0] == settings.redis_key_prefix
        assert key_parts[1].isdigit()  # timestamp
        assert len(key_parts[2]) == UNIQUE_ID_LENGTH

        assert ttl == REDIS_TTL_SECONDS
        assert data["tool"] == "test_tool"
        assert data["params"] == {"q": "test"}
        assert data["response"] == "tool response"


@pytest.mark.asyncio
async def test_middleware_redis_error() -> None:
    """Test middleware when Redis raises an error."""
    redis_url = "redis://redis:6379"

    with patch("ssmcp.middleware.redis_middleware.Redis.from_url") as mock_from_url:
        mock_redis = AsyncMock()
        mock_redis.setex.side_effect = Exception("Redis down")
        mock_from_url.return_value = mock_redis

        middleware = RedisLoggingMiddleware(redis_url=redis_url)
        await middleware.startup()

        context = MagicMock(spec=MiddlewareContext)
        context.message = MagicMock()
        context.message.name = "test_tool"
        context.message.arguments = {}

        call_next = AsyncMock(return_value="ok")

        # should not raise exception
        result = await middleware.on_call_tool(context, call_next)

        assert result == "ok"
        assert mock_redis.setex.called


@pytest.mark.asyncio
async def test_middleware_lifecycle() -> None:
    """Test middleware startup and shutdown lifecycle."""
    redis_url = "redis://redis:6379"

    with patch("ssmcp.middleware.redis_middleware.Redis.from_url") as mock_from_url:
        mock_redis = AsyncMock()
        mock_from_url.return_value = mock_redis

        middleware = RedisLoggingMiddleware(redis_url=redis_url)

        # Before startup, client should be None
        assert middleware.redis_client is None

        # Call startup
        await middleware.startup()
        assert middleware.redis_client is not None
        mock_from_url.assert_called_once_with(redis_url)

        # Call shutdown
        await middleware.shutdown()
        assert middleware.redis_client is None
        mock_redis.aclose.assert_called_once()
