"""Unit tests for configuration."""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from ssmcp.config import Settings


class TestSettings:
    """Test application settings."""

    def test_settings_default_values(self) -> None:
        """Test that default values are correctly set."""
        # Use a mock environment to avoid loading real .env
        expected_max_results = 5
        with (
            patch.dict(os.environ, {"SEARXNG_SEARCH_URL": "http://test.com"}, clear=True),
            patch("pydantic_settings.sources.DotEnvSettingsSource.__call__", return_value={}),
        ):
            settings = Settings(searxng_search_url="http://test.com")
            assert settings.searxng_search_url == "http://test.com"
            assert settings.ssmcp_debug is False  # Default should be False
            assert settings.searxng_max_results == expected_max_results

    def test_settings_override_from_env(self) -> None:
        """Test that environment variables override defaults."""
        expected_max_results = 10
        env_vars = {
            "SEARXNG_SEARCH_URL": "http://env.com",
            "SSMCP_DEBUG": "true",
            "SEARXNG_MAX_RESULTS": str(expected_max_results),
        }
        with patch.dict(os.environ, env_vars):
            settings = Settings(searxng_search_url="http://env.com")
            assert settings.searxng_search_url == "http://env.com"
            assert settings.ssmcp_debug is True
            assert settings.searxng_max_results == expected_max_results

    def test_required_fields(self) -> None:
        """Test that missing required fields raise ValidationError."""
        # Clear environment
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("pydantic_settings.sources.DotEnvSettingsSource.__call__", return_value={}),
            pytest.raises(ValidationError),
        ):
            # We must also ensure .env is not found or ignored
            Settings()  # type: ignore[call-arg]
