"""Unit tests for logger configuration."""

import logging
import sys
from unittest.mock import MagicMock, patch

from ssmcp.logger import logger, setup_logging


class TestLogger:
    """Test logger configuration and setup."""

    def test_logger_instance_exists(self) -> None:
        """Test that the logger instance is properly created."""
        assert logger is not None
        assert logger.name == "ssmcp"
        assert isinstance(logger, logging.Logger)

    @patch("ssmcp.logger.settings")
    def test_setup_logging_debug_mode(self, mock_settings: MagicMock) -> None:
        """Test setup_logging configures DEBUG level when SSMCP_DEBUG is True."""
        mock_settings.ssmcp_debug = True

        # Clear any existing handlers before test
        logging.root.handlers = []
        logger.handlers = []

        with patch("logging.basicConfig") as mock_basic_config:
            setup_logging()

            # Verify basicConfig was called with correct parameters
            mock_basic_config.assert_called_once()
            call_kwargs = mock_basic_config.call_args.kwargs
            assert call_kwargs["level"] == logging.WARNING
            assert call_kwargs["stream"] == sys.stderr
            assert "%(asctime)s" in call_kwargs["format"]
            assert "%(name)s" in call_kwargs["format"]
            assert "%(levelname)s" in call_kwargs["format"]
            assert "%(message)s" in call_kwargs["format"]

            # Verify logger level is set to DEBUG
            assert logger.level == logging.DEBUG

    @patch("ssmcp.logger.settings")
    def test_setup_logging_info_mode(self, mock_settings: MagicMock) -> None:
        """Test setup_logging configures INFO level when SSMCP_DEBUG is False."""
        mock_settings.ssmcp_debug = False

        # Clear any existing handlers before test
        logging.root.handlers = []
        logger.handlers = []

        with patch("logging.basicConfig") as mock_basic_config:
            setup_logging()

            # Verify basicConfig was called
            mock_basic_config.assert_called_once()

            # Verify logger level is set to INFO
            assert logger.level == logging.INFO

    @patch("ssmcp.logger.settings")
    def test_setup_logging_clears_handlers(self, mock_settings: MagicMock) -> None:
        """Test that setup_logging clears existing root handlers."""
        mock_settings.ssmcp_debug = False

        # Add some dummy handlers to root
        dummy_handler1 = logging.StreamHandler()
        dummy_handler2 = logging.StreamHandler()
        logging.root.handlers = [dummy_handler1, dummy_handler2]

        setup_logging()

        # Verify handlers were cleared (basicConfig will add new ones)
        # The function should have cleared the list before basicConfig
        assert dummy_handler1 not in logging.root.handlers
        assert dummy_handler2 not in logging.root.handlers

    @patch("ssmcp.logger.settings")
    def test_setup_logging_logs_to_stderr(self, mock_settings: MagicMock) -> None:
        """Test that logging is configured to use stderr."""
        mock_settings.ssmcp_debug = False

        with patch("logging.basicConfig") as mock_basic_config:
            setup_logging()

            # Verify stderr is used
            call_kwargs = mock_basic_config.call_args.kwargs
            assert call_kwargs["stream"] == sys.stderr

    @patch("ssmcp.logger.settings")
    @patch("ssmcp.logger.logger")
    def test_setup_logging_logs_initialization_message(
        self, mock_logger: MagicMock, mock_settings: MagicMock
    ) -> None:
        """Test that setup_logging logs an initialization message."""
        mock_settings.ssmcp_debug = True

        setup_logging()

        # Verify the logger.info was called with initialization message
        mock_logger.info.assert_called_once()
        args = mock_logger.info.call_args[0]
        assert "SSMCP logging initialized" in args[0]
        assert "DEBUG" in args[1]

    @patch("ssmcp.logger.settings")
    @patch("ssmcp.logger.logger")
    def test_setup_logging_initialization_message_info_level(
        self, mock_logger: MagicMock, mock_settings: MagicMock
    ) -> None:
        """Test that setup_logging logs correct level name for INFO mode."""
        mock_settings.ssmcp_debug = False

        setup_logging()

        # Verify the logger.info was called with INFO level name
        mock_logger.info.assert_called_once()
        args = mock_logger.info.call_args[0]
        assert "SSMCP logging initialized" in args[0]
        assert "INFO" in args[1]

    @patch("ssmcp.logger.settings")
    def test_setup_logging_format_includes_required_fields(
        self, mock_settings: MagicMock
    ) -> None:
        """Test that the logging format includes all required fields."""
        mock_settings.ssmcp_debug = False

        with patch("logging.basicConfig") as mock_basic_config:
            setup_logging()

            call_kwargs = mock_basic_config.call_args.kwargs
            log_format = call_kwargs["format"]

            # Verify all required format fields are present
            assert "%(asctime)s" in log_format
            assert "%(name)s" in log_format
            assert "%(levelname)s" in log_format
            assert "%(message)s" in log_format

    @patch("ssmcp.logger.settings")
    def test_setup_logging_root_level_warning(self, mock_settings: MagicMock) -> None:
        """Test that root logger level is set to WARNING."""
        mock_settings.ssmcp_debug = True

        with patch("logging.basicConfig") as mock_basic_config:
            setup_logging()

            # Verify root logger level is WARNING (not DEBUG)
            call_kwargs = mock_basic_config.call_args.kwargs
            assert call_kwargs["level"] == logging.WARNING
