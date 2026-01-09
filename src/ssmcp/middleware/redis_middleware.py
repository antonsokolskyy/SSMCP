"""Redis Middleware for storing requests and responses."""

import json
import time
from typing import Any

from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.tools.tool import ToolResult
from redis.asyncio import Redis

from ssmcp.config import settings
from ssmcp.logger import logger


class RedisLoggingMiddleware(Middleware):
    """Middleware that stores tool parameters and responses in Redis."""

    def __init__(self, redis_url: str = "") -> None:
        """Initialize the middleware.

        Args:
            redis_url: Redis connection URL

        """
        if not redis_url:
            self.redis_client = None
        else:
            self.redis_client = Redis.from_url(redis_url)

    async def on_call_tool(self, context: MiddlewareContext, call_next: Any) -> Any:
        """Process the tool call and store params and response in Redis.

        Args:
            context: The middleware context
            call_next: Function to process the next middleware or tool

        Returns:
            The result from the tool execution

        """
        # If Redis is not configured, just pass through
        if self.redis_client is None:
            return await call_next(context)

        # Process the tool call and get result
        result = await call_next(context)

        try:
            # Extract content from ToolResult if necessary
            # FastMCP wraps tool outputs in ToolResult objects
            response_content = ""
            if isinstance(result, ToolResult):
                # ToolResult.content is a list of ContentBlock objects
                contents = []
                for item in result.content:
                    if hasattr(item, "text"):
                        contents.append(item.text)
                    else:
                        contents.append(str(item))
                response_content = "\n".join(contents)

                # If there's structured content and it's not just the same as text
                if result.structured_content and not response_content:
                    response_content = json.dumps(result.structured_content, indent=2)
            elif isinstance(result, list | dict):
                response_content = json.dumps(result, indent=2)
            else:
                response_content = str(result)

            # Store tool params and response
            log_data = {
                "tool": context.message.name,
                "params": context.message.arguments,
                "response": response_content,
            }

            # Unique key with timestamp
            key = f"{settings.redis_key_prefix}:{int(time.time())}"
            await self.redis_client.setex(
                key,
                settings.redis_expiration_seconds,
                json.dumps(log_data),
            )
        except Exception:
            logger.exception("Failed to store data in Redis")
            # We don't raise here as logging is a non-critical side effect
            return result

        return result
