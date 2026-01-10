import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.middleware import MiddlewareContext
from redis.asyncio import Redis

from ssmcp.config import settings
from ssmcp.middleware.redis_middleware import RedisLoggingMiddleware


@pytest.mark.asyncio
async def test_redis_logging_integration() -> None:
    """Integration test to verify that middleware stores data in Redis."""
    redis_url = settings.redis_url or "redis://redis:6379"

    redis_client = Redis.from_url(redis_url)

    # Get initial keys to compare later
    initial_keys = await redis_client.keys(f"{settings.redis_key_prefix}:*")

    #Verify we can connect to redis first
    try:
        await redis_client.ping()
    except Exception as e:
        # skip the test if connection fails
        pytest.skip(f"Could not connect to Redis: {e}")

    middleware = RedisLoggingMiddleware(redis_url=redis_url)
    await middleware.startup()

    context = MagicMock(spec=MiddlewareContext)
    context.message = MagicMock()
    context.message.name = "integration_test_tool"
    context.message.arguments = {"q": "integration-test"}

    call_next = AsyncMock(return_value="integration-test-response")

    await middleware.on_call_tool(context, call_next)

    # Verify data in Redis
    new_keys = await redis_client.keys(f"{settings.redis_key_prefix}:*")
    added_keys = set(new_keys) - set(initial_keys)

    assert len(added_keys) >= 1

    # Check the content of one of the new keys
    key = next(iter(added_keys))
    data_json = await redis_client.get(key)
    assert data_json is not None

    data = json.loads(data_json)
    assert data["tool"] == "integration_test_tool"
    assert data["params"] == {"q": "integration-test"}
    assert data["response"] == "integration-test-response"

    # Cleanup
    for k in added_keys:
        await redis_client.delete(k)
    await redis_client.aclose()
