"""Integration tests for OAuth functionality in the MCP server.

These tests require:
1. The MCP server running (make up)
2. External OAuth services accessible (for JWKS endpoint mocking)

Run: make test

These tests verify OAuth behavior when enabled and disabled.
"""

import time
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat

from ssmcp.config import settings
from ssmcp.exceptions import (
    AudienceMismatchError,
    InvalidJWKSURLError,
    SubjectClaimMissingError,
    TokenExpiredError,
    TokenValidationError,
)
from ssmcp.oauth import JWKSProvider, OAuthTokenVerifier
from ssmcp.server import log_tool_call

# Test configuration
TEST_ISSUER = "https://auth.example.com"


@pytest.fixture
def rsa_keys_for_integration() -> tuple[bytes, dict[str, str]]:
    """Generate RSA key pair for integration testing.

    Returns:
        Tuple of (private_key_pem, jwk_data)
    """
    # Generate RSA key pair
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    public_key = private_key.public_key()

    # Export private key
    private_pem = private_key.private_bytes(
        encoding=Encoding.PEM,
        format=PrivateFormat.PKCS8,
        encryption_algorithm=NoEncryption(),
    )

    # Create JWK data
    public_numbers = public_key.public_numbers()
    e_bytes = public_numbers.e.to_bytes((public_numbers.e.bit_length() + 7) // 8, "big")
    e = jwt.utils.base64url_encode(e_bytes)
    n_bytes = public_numbers.n.to_bytes((public_numbers.n.bit_length() + 7) // 8, "big")
    n = jwt.utils.base64url_encode(n_bytes)

    jwk_data = {
        "kty": "RSA",
        "kid": "integration-test-key",
        "e": e.decode(),
        "n": n.decode(),
        "alg": "RS256",
        "use": "sig",
    }

    return private_pem, jwk_data


@pytest.fixture
def valid_jwt_token(rsa_keys_for_integration: tuple[bytes, dict[str, str]]) -> str:
    """Create a valid JWT token for testing.

    Args:
        rsa_keys_for_integration: RSA key pair

    Returns:
        Valid JWT token
    """
    private_pem, jwk_data = rsa_keys_for_integration

    payload = {
        "iss": TEST_ISSUER,
        "sub": "test@example.com",
        "aud": "test-client-id",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }

    return jwt.encode(payload, private_pem, algorithm="RS256", headers={"kid": jwk_data["kid"]})


@pytest.fixture
def sample_jwks_response(rsa_keys_for_integration: tuple[bytes, dict[str, str]]) -> dict[str, Any]:
    """Create sample JWKS response.

    Args:
        rsa_keys_for_integration: RSA key pair

    Returns:
        JWKS response
    """
    _, jwk_data = rsa_keys_for_integration
    return {"keys": [jwk_data]}


class TestOAuthDisabledBehavior:
    """Tests for server behavior when OAuth is disabled."""

    def test_oauth_disabled_by_default(self) -> None:
        """Test that OAuth is disabled by default."""
        assert not settings.oauth_enabled


class TestOAuthEnabledBehavior:
    """Tests for server behavior when OAuth is enabled."""

    @pytest.mark.asyncio
    async def test_oauth_enabled_requires_valid_token(
        self,
        valid_jwt_token: str,
        sample_jwks_response: dict[str, Any],
    ) -> None:
        """Test that requests require valid OAuth token when enabled."""
        # Mock JWKS endpoint
        mock_response = AsyncMock()
        mock_response.raise_for_status = Mock()
        mock_response.json = Mock(return_value=sample_jwks_response)

        with patch("ssmcp.oauth.settings") as mock_settings:
            mock_settings.oauth_jwks_url = "https://auth.example.com/jwks"
            mock_settings.oauth_client_id = "test-client-id"
            mock_settings.oauth_issuer = TEST_ISSUER

            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                    return_value=mock_response
                )

                verifier = OAuthTokenVerifier()
                result = await verifier.verify_token(valid_jwt_token)

                assert result["sub"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_oauth_enabled_rejects_invalid_token(
        self,
    ) -> None:
        """Test that invalid tokens are rejected when OAuth is enabled."""
        with patch("ssmcp.oauth.settings") as mock_settings:
            mock_settings.oauth_jwks_url = "https://auth.example.com/jwks"
            mock_settings.oauth_client_id = "test-client-id"
            mock_settings.oauth_issuer = TEST_ISSUER

            # Test with invalid token
            verifier = OAuthTokenVerifier()

            with pytest.raises(TokenValidationError):
                await verifier.verify_token("invalid-token")

    @pytest.mark.asyncio
    async def test_oauth_enabled_logging_with_user(
        self,
        valid_jwt_token: str,
        sample_jwks_response: dict[str, Any],
    ) -> None:
        """Test that logging function works with user ID."""
        # Mock JWKS endpoint
        mock_response = AsyncMock()
        mock_response.raise_for_status = Mock()
        mock_response.json = Mock(return_value=sample_jwks_response)

        with patch("ssmcp.oauth.settings") as mock_settings:
            mock_settings.oauth_jwks_url = "https://auth.example.com/jwks"
            mock_settings.oauth_client_id = "test-client-id"
            mock_settings.oauth_issuer = TEST_ISSUER

            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                    return_value=mock_response
                )

                # Verify token and check that user ID is extracted
                verifier = OAuthTokenVerifier()
                result = await verifier.verify_token(valid_jwt_token)

                assert result["sub"] == "test@example.com"

                # The logging function should work with user ID
                # We can't easily test log capture, so just verify it doesn't crash
                # This should not raise any exceptions
                log_tool_call("test_tool", "test details", result["sub"])


class TestOAuthErrorHandling:
    """Tests for OAuth error handling."""

    @pytest.mark.asyncio
    async def test_expired_token_rejected(
        self,
        rsa_keys_for_integration: tuple[bytes, dict[str, str]],
        sample_jwks_response: dict[str, Any],
    ) -> None:
        """Test that expired tokens are rejected."""
        # Mock JWKS endpoint
        mock_response = AsyncMock()
        mock_response.raise_for_status = Mock()
        mock_response.json = Mock(return_value=sample_jwks_response)

        # Create expired token
        private_pem, jwk_data = rsa_keys_for_integration

        payload = {
            "iss": TEST_ISSUER,
            "sub": "test@example.com",
            "aud": "test-client-id",
            "exp": int(time.time()) - 3600,  # Expired
            "iat": int(time.time()) - 7200,
        }

        expired_token = jwt.encode(
            payload,
            private_pem,
            algorithm="RS256",
            headers={"kid": jwk_data["kid"]},
        )

        with patch("ssmcp.oauth.settings") as mock_settings:
            mock_settings.oauth_jwks_url = "https://auth.example.com/jwks"
            mock_settings.oauth_client_id = "test-client-id"
            mock_settings.oauth_issuer = TEST_ISSUER

            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                    return_value=mock_response
                )

                verifier = OAuthTokenVerifier()

                with pytest.raises(TokenExpiredError, match="Token has expired"):
                    await verifier.verify_token(expired_token)

    @pytest.mark.asyncio
    async def test_wrong_audience_rejected(
        self,
        rsa_keys_for_integration: tuple[bytes, dict[str, str]],
        sample_jwks_response: dict[str, Any],
    ) -> None:
        """Test that tokens with wrong audience are rejected."""
        # Mock JWKS endpoint
        mock_response = AsyncMock()
        mock_response.raise_for_status = Mock()
        mock_response.json = Mock(return_value=sample_jwks_response)

        # Create token with wrong audience
        private_pem, jwk_data = rsa_keys_for_integration

        payload = {
            "iss": TEST_ISSUER,
            "sub": "test@example.com",
            "aud": "wrong-client-id",
            "exp": int(time.time()) + 3600,
        }

        token = jwt.encode(
            payload,
            private_pem,
            algorithm="RS256",
            headers={"kid": jwk_data["kid"]},
        )

        with patch("ssmcp.oauth.settings") as mock_settings:
            mock_settings.oauth_jwks_url = "https://auth.example.com/jwks"
            mock_settings.oauth_client_id = "test-client-id"
            mock_settings.oauth_issuer = TEST_ISSUER

            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                    return_value=mock_response
                )

                verifier = OAuthTokenVerifier()

                with pytest.raises(
                    AudienceMismatchError, match="Token audience does not match"
                ):
                    await verifier.verify_token(token)

    @pytest.mark.asyncio
    async def test_missing_subject_rejected(
        self,
        rsa_keys_for_integration: tuple[bytes, dict[str, str]],
        sample_jwks_response: dict[str, Any],
    ) -> None:
        """Test that tokens without subject claim are rejected."""
        # Mock JWKS endpoint
        mock_response = AsyncMock()
        mock_response.raise_for_status = Mock()
        mock_response.json = Mock(return_value=sample_jwks_response)

        # Create token without subject
        private_pem, jwk_data = rsa_keys_for_integration

        payload = {
            "iss": TEST_ISSUER,
            "aud": "test-client-id",
            "exp": int(time.time()) + 3600,
        }

        token = jwt.encode(
            payload,
            private_pem,
            algorithm="RS256",
            headers={"kid": jwk_data["kid"]},
        )

        with patch("ssmcp.oauth.settings") as mock_settings:
            mock_settings.oauth_jwks_url = "https://auth.example.com/jwks"
            mock_settings.oauth_client_id = "test-client-id"
            mock_settings.oauth_issuer = TEST_ISSUER

            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                    return_value=mock_response
                )

                verifier = OAuthTokenVerifier()

                with pytest.raises(
                    SubjectClaimMissingError, match="Token missing 'sub' claim"
                ):
                    await verifier.verify_token(token)


class TestOAuthTokenCache:
    """Tests for JWKS caching behavior."""

    @pytest.mark.asyncio
    async def test_jwks_cached_between_requests(
        self,
        sample_jwks_response: dict[str, Any],
    ) -> None:
        """Test that JWKS is cached between token verifications."""
        # Mock JWKS endpoint
        mock_response = AsyncMock()
        mock_response.raise_for_status = Mock()
        mock_response.json = Mock(return_value=sample_jwks_response)

        with patch("httpx.AsyncClient") as mock_client:
            get_mock = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.get = get_mock

            provider = JWKSProvider("https://auth.example.com/jwks", cache_ttl=10)

            # First request
            await provider.get_key("integration-test-key")
            assert get_mock.call_count == 1

            # Second request should use cache
            await provider.get_key("integration-test-key")
            assert get_mock.call_count == 1

            # Third request should still use cache
            await provider.get_key("integration-test-key")
            assert get_mock.call_count == 1

    @pytest.mark.asyncio
    async def test_jwks_fetch_error_handling(
        self,
    ) -> None:
        """Test that JWKS fetch errors are handled gracefully."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_get = AsyncMock()
            mock_get.side_effect = httpx.HTTPStatusError(
                "Server error",
                request=Mock(),
                response=Mock(status_code=500)
            )
            mock_client.return_value.__aenter__.return_value.get = mock_get

            provider = JWKSProvider("https://auth.example.com/jwks")

            with pytest.raises(InvalidJWKSURLError, match="Failed to fetch JWKS"):
                await provider.get_key("integration-test-key")
