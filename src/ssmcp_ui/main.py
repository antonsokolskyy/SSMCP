"""Web UI for monitoring ssmcp requests and responses."""

import json
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from redis.asyncio import Redis

from ssmcp.config import settings

app = FastAPI(title="ssmcp Monitor")
templates = Jinja2Templates(directory="src/ssmcp_ui/templates")

redis_client = Redis.from_url(settings.redis_url) if settings.redis_url else None


def format_timestamp(key: str) -> str:
    """Extract and format timestamp from Redis key."""
    try:
        ts = int(key.split(":")[-1])
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, IndexError):
        return "Unknown"


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> Any:
    """List all requests stored in Redis."""
    if not redis_client:
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "message": "Redis not configured"},
        )

    # Get all keys matching the prefix
    pattern = f"{settings.redis_key_prefix}:*"
    keys = await redis_client.keys(pattern)

    # Sort keys by timestamp (descending)
    keys.sort(reverse=True)

    requests = []
    for key in keys:
        key_str = key.decode("utf-8")
        data_raw = await redis_client.get(key)
        if data_raw:
            data = json.loads(data_raw)
            requests.append({
                "id": key_str,
                "timestamp": format_timestamp(key_str),
                "tool": data.get("tool", "Unknown"),
                "params": json.dumps(data.get("params", {}), indent=2),
            })

    return templates.TemplateResponse(
        "index.html",
        {"request": request, "requests": requests},
    )


@app.get("/request/{request_id:path}", response_class=HTMLResponse)
async def request_detail(request: Request, request_id: str) -> Any:
    """Show details for a specific request."""
    if not redis_client:
        raise HTTPException(status_code=500, detail="Redis not configured")

    data_raw = await redis_client.get(request_id)
    if not data_raw:
        raise HTTPException(status_code=404, detail="Request not found")

    data = json.loads(data_raw)

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
