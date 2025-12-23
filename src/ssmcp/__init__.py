"""SSMCP - Super Simple MCP Server.

A Model Context Protocol server providing web search with content extraction.
"""

from ssmcp.config import Settings, settings
from ssmcp.searxng_client import SearXNGClient
from ssmcp.youtube_client import YouTubeClient

__version__ = "0.2.0"

__all__ = [
    "SearXNGClient",
    "Settings",
    "YouTubeClient",
    "__version__",
    "settings",
]
