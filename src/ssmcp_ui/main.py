"""Web UI for monitoring ssmcp requests and responses."""

import json
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from redis.asyncio import Redis

from ssmcp.config import settings


class UIState:
    """Application state for UI server."""

    def __init__(self) -> None:
        """Initialize UI state."""
        self.redis_client: Redis | None = None

    async def start(self) -> None:
        """Initialize Redis connection."""
        if settings.redis_url:
            self.redis_client = Redis.from_url(settings.redis_url)

    async def stop(self) -> None:
        """Cleanup Redis connection."""
        if self.redis_client:
            await self.redis_client.aclose()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[dict[str, UIState]]:
    """Manage application lifespan: initialize and cleanup Redis client."""
    state = UIState()
    await state.start()
    app.state.ui_state = state
    try:
        yield {"ui_state": state}
    finally:
        await state.stop()


app = FastAPI(title="ssmcp Monitor", lifespan=lifespan)
templates = Jinja2Templates(directory="src/ssmcp_ui/templates")

# Pattern to validate Redis key format: prefix:timestamp:unique_id
KEY_PATTERN = re.compile(rf"^{re.escape(settings.redis_key_prefix)}:\d+:[a-f0-9]+$")


def format_timestamp(key: str) -> str:
    """Extract and format timestamp from Redis key.

    Key format: prefix:timestamp:unique_id
    """
    try:
        parts = key.split(":")
        ts = int(parts[1])  # Second part is the timestamp
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, IndexError):
        return "Unknown"


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """List all requests stored in Redis."""
    state: UIState = app.state.ui_state
    redis_client = state.redis_client

    if not redis_client:
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "message": "Redis not configured"},
        )

    # Use SCAN instead of KEYS for production safety
    pattern = f"{settings.redis_key_prefix}:*"
    keys: list[bytes] = []
    cursor = 0
    while True:
        cursor, batch = await redis_client.scan(cursor, match=pattern, count=100)
        keys.extend(batch)
        if cursor == 0:
            break

    # Sort keys by timestamp (descending)
    keys.sort(reverse=True)

    # Use mget for batch fetching to reduce Redis round trips
    requests = []
    if keys:
        values = await redis_client.mget(keys)
        for key, data_raw in zip(keys, values, strict=True):
            if data_raw:
                key_str = key.decode("utf-8")
                try:
                    data = json.loads(data_raw)
                    requests.append({
                        "id": key_str,
                        "timestamp": format_timestamp(key_str),
                        "tool": data.get("tool", "Unknown"),
                        "params": json.dumps(data.get("params", {}), indent=2),
                    })
                except json.JSONDecodeError:
                    # Skip corrupted data
                    continue

    return templates.TemplateResponse(
        "index.html",
        {"request": request, "requests": requests},
    )


@app.get("/request/{request_id:path}", response_class=HTMLResponse)
async def request_detail(request: Request, request_id: str) -> HTMLResponse:
    """Show details for a specific request.

    Args:
        request: FastAPI request object
        request_id: Redis key to lookup (validated against expected pattern)

    Returns:
        HTML response with request details

    Raises:
        HTTPException: If Redis not configured, key invalid, or not found

    """
    state: UIState = app.state.ui_state
    redis_client = state.redis_client

    if not redis_client:
        raise HTTPException(status_code=500, detail="Redis not configured")

    # Security: Validate request_id matches expected pattern (prevent path traversal)
    if not KEY_PATTERN.match(request_id):
        raise HTTPException(status_code=400, detail="Invalid request ID format")

    data_raw = await redis_client.get(request_id)
    if not data_raw:
        raise HTTPException(status_code=404, detail="Request not found")

    try:
        data = json.loads(data_raw)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail="Corrupted data in Redis") from e

    return templates.TemplateResponse(
        "detail.html",
        {
            "request": request,
            "id": request_id,
            "timestamp": format_timestamp(request_id),
            "tool": data.get("tool", "Unknown"),
            "params": json.dumps(data.get("params", {}), indent=2),
            "response": data.get("response", ""),
        },
    )
