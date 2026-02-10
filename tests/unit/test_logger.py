"""Unit tests for logger configuration."""

import logging
from unittest.mock import MagicMock, patch

from ssmcp.logger import logger, setup_logging


class TestLogger:
    """Test logger configuration and setup."""

    @patch("ssmcp.logger.settings")
    def test_setup_logging_configures_level(self, mock_settings: MagicMock) -> None:
        """Test setup_logging configures correct log level based on SSMCP_DEBUG."""
        # Test DEBUG mode
        mock_settings.ssmcp_debug = True
        logging.root.handlers = []
        logger.handlers = []
        setup_logging()
        assert logger.level == logging.DEBUG

        # Test INFO mode
        mock_settings.ssmcp_debug = False
        logging.root.handlers = []
        logger.handlers = []
        setup_logging()
        assert logger.level == logging.INFO
