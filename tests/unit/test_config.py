"""Unit tests for configuration."""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from ssmcp.config import Settings

# Test constants
DEFAULT_MAX_RESULTS = 5
CUSTOM_MAX_RESULTS = 10
NEGATIVE_TIMEOUT = -5.0
ZERO_VALUE = 0
TEST_PORT = 8000


class TestSettings:
    """Test application settings."""

    def test_settings_default_values(self) -> None:
        """Test that default values are correctly set."""
        with (
            patch.dict(os.environ, {"SEARXNG_SEARCH_URL": "http://test.com"}, clear=True),
            patch("pydantic_settings.sources.DotEnvSettingsSource.__call__", return_value={}),
        ):
            settings = Settings(searxng_search_url="http://test.com")
            assert settings.searxng_search_url == "http://test.com"
            assert settings.ssmcp_debug is False  # Default should be False
            assert settings.searxng_max_results == DEFAULT_MAX_RESULTS

    def test_settings_override_from_env(self) -> None:
        """Test that environment variables override defaults."""
        env_vars = {
            "SEARXNG_SEARCH_URL": "http://env.com",
            "SSMCP_DEBUG": "true",
            "SEARXNG_MAX_RESULTS": str(CUSTOM_MAX_RESULTS),
        }
        with patch.dict(os.environ, env_vars):
            settings = Settings(searxng_search_url="http://env.com")
            assert settings.searxng_search_url == "http://env.com"
            assert settings.ssmcp_debug is True
            assert settings.searxng_max_results == CUSTOM_MAX_RESULTS

    def test_required_fields(self) -> None:
        """Test that missing required fields raise ValidationError."""
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("pydantic_settings.sources.DotEnvSettingsSource.__call__", return_value={}),
            pytest.raises(ValidationError),
        ):
            # We must also ensure .env is not found or ignored
            # Settings requires searxng_search_url which is not provided
            Settings() # type: ignore[call-arg]

    def test_oauth_validation_missing_jwks_url(self) -> None:
        """Test that OAuth validation fails when jwks_url is missing."""
        with pytest.raises(ValueError, match="OAUTH_JWKS_URL must be set"):
            Settings(
                searxng_search_url="http://test.com",
                oauth_enabled=True,
                oauth_jwks_url="",
                oauth_client_id="test-client",
                oauth_issuer="https://auth.com",
            )

    def test_oauth_validation_missing_client_id(self) -> None:
        """Test that OAuth validation fails when client_id is missing."""
        with pytest.raises(ValueError, match="OAUTH_CLIENT_ID must be set"):
            Settings(
                searxng_search_url="http://test.com",
                oauth_enabled=True,
                oauth_jwks_url="https://auth.com/jwks",
                oauth_client_id="",
                oauth_issuer="https://auth.com",
            )

    def test_oauth_validation_missing_issuer(self) -> None:
        """Test that OAuth validation fails when issuer is missing."""
        with pytest.raises(ValueError, match="OAUTH_ISSUER must be set"):
            Settings(
                searxng_search_url="http://test.com",
                oauth_enabled=True,
                oauth_jwks_url="https://auth.com/jwks",
                oauth_client_id="test-client",
                oauth_issuer="",
            )

    def test_oauth_disabled_allows_empty_fields(self) -> None:
        """Test that OAuth validation passes when OAuth is disabled, even with empty fields."""
        settings = Settings(
            searxng_search_url="http://test.com",
            oauth_enabled=False,
            oauth_jwks_url="",
            oauth_client_id="",
            oauth_issuer="",
        )
        assert settings.oauth_enabled is False
        assert settings.oauth_jwks_url == ""
        assert settings.oauth_client_id == ""
        assert settings.oauth_issuer == ""

    def test_oauth_enabled_with_all_fields(self) -> None:
        """Test that OAuth validation passes when all required fields are provided."""
        settings = Settings(
            searxng_search_url="http://test.com",
            oauth_enabled=True,
            oauth_jwks_url="https://auth.com/jwks",
            oauth_client_id="test-client",
            oauth_issuer="https://auth.com",
        )
        assert settings.oauth_enabled is True
        assert settings.oauth_jwks_url == "https://auth.com/jwks"
        assert settings.oauth_client_id == "test-client"
        assert settings.oauth_issuer == "https://auth.com"

    def test_invalid_numeric_value_raises_error(self) -> None:
        """Test that invalid numeric values in environment raise validation errors."""
        with pytest.raises(ValueError):
            # Pydantic will fail to convert "not_a_number" to int
            Settings(
                searxng_search_url="http://test.com",
                searxng_max_results="not_a_number",  # type: ignore[arg-type]  # Invalid: should be int
            )

    def test_zero_values_accepted(self) -> None:
        """Test that zero values are accepted for numeric fields."""
        settings = Settings(
            searxng_search_url="http://test.com",
            searxng_max_results=ZERO_VALUE,
            searxng_timeout=ZERO_VALUE,
            crawl4ai_browser_pool_size=ZERO_VALUE,
        )
        assert settings.searxng_max_results == ZERO_VALUE
        assert settings.searxng_timeout == float(ZERO_VALUE)
        assert settings.crawl4ai_browser_pool_size == ZERO_VALUE

    def test_invalid_boolean_value_raises_error(self) -> None:
        """Test that invalid boolean values raise validation errors."""
        with pytest.raises(ValueError):
            Settings(
                searxng_search_url="http://test.com",
                ssmcp_debug="not_a_boolean",  # type: ignore[arg-type]  # Invalid: should be bool
            )

    def test_empty_string_for_optional_fields(self) -> None:
        """Test that empty strings are accepted for optional fields."""
        settings = Settings(
            searxng_search_url="http://test.com",
            redis_url="",
            oauth_jwks_url="",
        )
        assert settings.redis_url == ""
        assert settings.oauth_jwks_url == ""
