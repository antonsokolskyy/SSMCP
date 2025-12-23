"""Logging configuration for SSMCP."""

import logging
import sys

from ssmcp.config import settings

# Single app logger that can be imported throughout the application
logger = logging.getLogger("ssmcp")


def setup_logging() -> None:
    """Configure application logging.

    Logs to stderr to avoid interfering with MCP protocol on stdout.
    Sets up a single app logger (ssmcp) that can be controlled via SSMCP_DEBUG.
    """
    # Clear existing handlers to prevent duplicate log entries on reload
    logging.root.handlers = []

    # Configure basic logging to stderr (used by root and all loggers)
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,
    )

    # Configure the app logger level based on SSMCP_DEBUG
    app_log_level = logging.DEBUG if settings.ssmcp_debug else logging.INFO
    logger.setLevel(app_log_level)

    level_name = "DEBUG" if settings.ssmcp_debug else "INFO"
    logger.info("SSMCP logging initialized at %s level", level_name)
