"""Unit tests for OAuth token verification."""

import asyncio
import time
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat

from ssmcp.exceptions import (
    AudienceMismatchError,
    InvalidJWKSURLError,
    IssuerMismatchError,
    SubjectClaimMissingError,
    TokenExpiredError,
    TokenValidationError,
)
from ssmcp.oauth import JWKSProvider, OAuthTokenVerifier

# Test configuration
TEST_ISSUER = "https://auth.example.com"

DEFAULT_CACHE_TTL = 3600
CUSTOM_CACHE_TTL = 1800
EXPECTED_NUM_FETCHES = 2


@pytest.fixture
def mock_jwks_url() -> str:
    """Return a mock JWKS URL for testing."""
    return "https://auth.example.com/jwks"


@pytest.fixture
def rsa_keys() -> tuple[bytes, dict[str, Any]]:
    """Generate RSA key pair for testing.

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
        "kid": "test-key-id",
        "e": e.decode(),
        "n": n.decode(),
        "alg": "RS256",
        "use": "sig",
    }

    return private_pem, jwk_data


@pytest.fixture
def sample_jwks_response(rsa_keys: tuple[bytes, dict[str, Any]]) -> dict[str, Any]:
    """Create a sample JWKS response.

    Args:
        rsa_keys: RSA key pair

    Returns:
        JWKS response dict
    """
    _, jwk_data = rsa_keys
    return {"keys": [jwk_data]}


class TestJWKSProvider:
    """Tests for JWKSProvider class."""

    def test_init(self, mock_jwks_url: str) -> None:
        """Test JWKSProvider initialization."""
        provider = JWKSProvider(mock_jwks_url)
        assert provider.jwks_url == mock_jwks_url
        assert provider.cache_ttl == DEFAULT_CACHE_TTL
        assert provider._keys == {}
        assert provider._cache_time == 0.0

    def test_init_custom_ttl(self, mock_jwks_url: str) -> None:
        """Test JWKSProvider with custom TTL."""
        provider = JWKSProvider(mock_jwks_url, cache_ttl=CUSTOM_CACHE_TTL)
        assert provider.cache_ttl == CUSTOM_CACHE_TTL

    @pytest.mark.asyncio
    async def test_get_key_success(
        self,
        mock_jwks_url: str,
        sample_jwks_response: dict[str, Any],
        rsa_keys: tuple[bytes, dict[str, Any]],
    ) -> None:
        """Test successful key retrieval."""
        # Mock the httpx.AsyncClient.get method
        mock_response = AsyncMock()
        mock_response.raise_for_status = Mock()
        mock_response.json = Mock(return_value=sample_jwks_response)

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            provider = JWKSProvider(mock_jwks_url)
            key = await provider.get_key("test-key-id")

            assert key is not None
            assert "test-key-id" in provider._keys
            assert provider._cache_time > 0

    @pytest.mark.asyncio
    async def test_get_key_not_found(
        self,
        mock_jwks_url: str,
        sample_jwks_response: dict[str, Any],
    ) -> None:
        """Test key retrieval with non-existent key ID."""
        mock_response = AsyncMock()
        mock_response.raise_for_status = Mock()
        mock_response.json = Mock(return_value=sample_jwks_response)

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            provider = JWKSProvider(mock_jwks_url)

            with pytest.raises(InvalidJWKSURLError, match="Key with kid 'non-existent' not found"):
                await provider.get_key("non-existent")

    @pytest.mark.asyncio
    async def test_get_key_http_error(
        self,
        mock_jwks_url: str,
    ) -> None:
        """Test key retrieval when JWKS endpoint returns HTTP error."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_get = AsyncMock()
            mock_get.side_effect = httpx.HTTPStatusError(
                "Server error",
                request=Mock(),
                response=Mock(status_code=500)
            )
            mock_client.return_value.__aenter__.return_value.get = mock_get

            provider = JWKSProvider(mock_jwks_url)

            with pytest.raises(InvalidJWKSURLError, match="Failed to fetch JWKS"):
                await provider.get_key("test-key-id")

    @pytest.mark.asyncio
    async def test_get_key_invalid_json(
        self,
        mock_jwks_url: str,
    ) -> None:
        """Test key retrieval when JWKS endpoint returns invalid JSON."""
        mock_response = AsyncMock()
        mock_response.raise_for_status = Mock()
        mock_response.json = Mock(side_effect=Exception("Invalid JSON"))

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            provider = JWKSProvider(mock_jwks_url)

            # The error is caught and wrapped in InvalidJWKSURLError
            with pytest.raises(InvalidJWKSURLError):
                await provider.get_key("test-key-id")

    @pytest.mark.asyncio
    async def test_get_key_missing_keys_field(
        self,
        mock_jwks_url: str,
    ) -> None:
        """Test key retrieval when JWKS response is missing 'keys' field."""
        mock_response = AsyncMock()
        mock_response.raise_for_status = Mock()
        mock_response.json = Mock(return_value={})

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            provider = JWKSProvider(mock_jwks_url)

            with pytest.raises(InvalidJWKSURLError):
                await provider.get_key("test-key-id")

    @pytest.mark.asyncio
    async def test_cache_expiration(
        self,
        mock_jwks_url: str,
        sample_jwks_response: dict[str, Any],
    ) -> None:
        """Test that cache expires after TTL."""
        mock_response = AsyncMock()
        mock_response.raise_for_status = Mock()
        mock_response.json = Mock(return_value=sample_jwks_response)

        with patch("httpx.AsyncClient") as mock_client:
            get_mock = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.get = get_mock

            provider = JWKSProvider(mock_jwks_url, cache_ttl=1)

            # First call - should fetch
            await provider.get_key("test-key-id")
            assert get_mock.call_count == 1

            # Second call within TTL - should use cache
            await provider.get_key("test-key-id")
            assert get_mock.call_count == 1

            # Wait for cache to expire
            await asyncio.sleep(1.1)

            # Third call after TTL - should fetch again
            await provider.get_key("test-key-id")
            assert get_mock.call_count == EXPECTED_NUM_FETCHES

    @pytest.mark.asyncio
    async def test_concurrent_refresh(
        self,
        mock_jwks_url: str,
        sample_jwks_response: dict[str, Any],
    ) -> None:
        """Test that concurrent refreshes are handled correctly."""
        mock_response = AsyncMock()
        mock_response.raise_for_status = Mock()
        mock_response.json = Mock(return_value=sample_jwks_response)

        with patch("httpx.AsyncClient") as mock_client:
            get_mock = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.get = get_mock

            # Use a positive TTL to allow caching
            provider = JWKSProvider(mock_jwks_url, cache_ttl=10)

            # Make multiple concurrent requests
            tasks = [provider.get_key("test-key-id") for _ in range(10)]
            results = await asyncio.gather(*tasks)

            # All should succeed
            assert all(r is not None for r in results)

            # Should only make one HTTP request (lock prevents concurrent fetches)
            assert get_mock.call_count == 1


class TestOAuthTokenVerifier:
    """Tests for OAuthTokenVerifier class."""

    @pytest.fixture
    def sample_token(
        self,
        rsa_keys: tuple[bytes, dict[str, Any]],
    ) -> str:
        """Create a sample JWT token.

        Args:
            rsa_keys: RSA key pair

        Returns:
            JWT token string
        """
        private_pem, jwk_data = rsa_keys

        payload = {
            "iss": TEST_ISSUER,
            "sub": "user@example.com",
            "aud": "test-client-id",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
            "kid": jwk_data["kid"],
        }

        return jwt.encode(payload, private_pem, algorithm="RS256", headers={"kid": jwk_data["kid"]})

    @pytest.fixture
    def expired_token(
        self,
        rsa_keys: tuple[bytes, dict[str, Any]],
    ) -> str:
        """Create an expired JWT token.

        Args:
            rsa_keys: RSA key pair

        Returns:
            Expired JWT token string
        """
        private_pem, jwk_data = rsa_keys

        payload = {
            "iss": TEST_ISSUER,
            "sub": "user@example.com",
            "aud": "test-client-id",
            "exp": int(time.time()) - 3600,  # Expired 1 hour ago
            "iat": int(time.time()) - 7200,
            "kid": jwk_data["kid"],
        }

        return jwt.encode(payload, private_pem, algorithm="RS256", headers={"kid": jwk_data["kid"]})

    @pytest.fixture
    def wrong_audience_token(
        self,
        rsa_keys: tuple[bytes, dict[str, Any]],
    ) -> str:
        """Create a token with wrong audience.

        Args:
            rsa_keys: RSA key pair

        Returns:
            JWT token with wrong audience
        """
        private_pem, jwk_data = rsa_keys

        payload = {
            "iss": TEST_ISSUER,
            "sub": "user@example.com",
            "aud": "wrong-client-id",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
            "kid": jwk_data["kid"],
        }

        return jwt.encode(payload, private_pem, algorithm="RS256", headers={"kid": jwk_data["kid"]})

    @pytest.fixture
    def missing_sub_token(
        self,
        rsa_keys: tuple[bytes, dict[str, Any]],
    ) -> str:
        """Create a token missing the subject claim.

        Args:
            rsa_keys: RSA key pair

        Returns:
            JWT token without subject claim
        """
        private_pem, jwk_data = rsa_keys

        payload = {
            "iss": TEST_ISSUER,
            "aud": "test-client-id",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
            "kid": jwk_data["kid"],
        }

        return jwt.encode(payload, private_pem, algorithm="RS256", headers={"kid": jwk_data["kid"]})

    @pytest.fixture
    def wrong_issuer_token(
        self,
        rsa_keys: tuple[bytes, dict[str, Any]],
    ) -> str:
        """Create a token with wrong issuer.

        Args:
            rsa_keys: RSA key pair

        Returns:
            JWT token with wrong issuer
        """
        private_pem, jwk_data = rsa_keys

        payload = {
            "iss": "https://wrong-issuer.example.com",
            "sub": "user@example.com",
            "aud": "test-client-id",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
            "kid": jwk_data["kid"],
        }

        return jwt.encode(payload, private_pem, algorithm="RS256", headers={"kid": jwk_data["kid"]})

    @pytest.mark.asyncio
    async def test_verify_token_success(
        self,
        sample_token: str,
        sample_jwks_response: dict[str, Any],
    ) -> None:
        """Test successful token verification."""
        mock_response = AsyncMock()
        mock_response.raise_for_status = Mock()
        mock_response.json = Mock(return_value=sample_jwks_response)

        # Patch settings directly in oauth module
        with patch("ssmcp.oauth.settings") as mock_settings:
            mock_settings.oauth_jwks_url = "https://auth.example.com/jwks"
            mock_settings.oauth_client_id = "test-client-id"
            mock_settings.oauth_issuer = TEST_ISSUER

            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                    return_value=mock_response
                )

                verifier = OAuthTokenVerifier()
                result = await verifier.verify_token(sample_token)

                assert result["sub"] == "user@example.com"
                assert "payload" in result
                assert result["payload"]["aud"] == "test-client-id"

    @pytest.mark.asyncio
    async def test_verify_token_expired(
        self,
        expired_token: str,
        sample_jwks_response: dict[str, Any],
    ) -> None:
        """Test verification of expired token."""
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
                with pytest.raises(TokenExpiredError, match="Token has expired"):
                    await verifier.verify_token(expired_token)

    @pytest.mark.asyncio
    async def test_verify_token_wrong_audience(
        self,
        wrong_audience_token: str,
        sample_jwks_response: dict[str, Any],
    ) -> None:
        """Test verification of token with wrong audience."""
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
                with pytest.raises(
                    AudienceMismatchError, match="Token audience does not match"
                ):
                    await verifier.verify_token(wrong_audience_token)

    @pytest.mark.asyncio
    async def test_verify_token_missing_sub(
        self,
        missing_sub_token: str,
        sample_jwks_response: dict[str, Any],
    ) -> None:
        """Test verification of token missing subject claim."""
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
                with pytest.raises(
                    SubjectClaimMissingError, match="Token missing 'sub' claim"
                ):
                    await verifier.verify_token(missing_sub_token)

    @pytest.mark.asyncio
    async def test_verify_token_missing_kid(
        self,
        rsa_keys: tuple[bytes, dict[str, Any]],
    ) -> None:
        """Test verification of token missing kid in header."""
        private_pem, _ = rsa_keys

        payload = {
            "iss": TEST_ISSUER,
            "sub": "user@example.com",
            "aud": "test-client-id",
            "exp": int(time.time()) + 3600,
        }

        # Create token without kid in header
        token = jwt.encode(payload, private_pem, algorithm="RS256")

        with patch("ssmcp.oauth.settings") as mock_settings:
            mock_settings.oauth_jwks_url = "https://auth.example.com/jwks"
            mock_settings.oauth_client_id = "test-client-id"
            mock_settings.oauth_issuer = TEST_ISSUER

            verifier = OAuthTokenVerifier()
            with pytest.raises(TokenValidationError, match="Token missing 'kid' in header"):
                await verifier.verify_token(token)

    @pytest.mark.asyncio
    async def test_verify_token_invalid_signature(
        self,
        sample_jwks_response: dict[str, Any],
    ) -> None:
        """Test verification of token with invalid signature."""
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

                # Create a token with a different private key
                wrong_private_key = rsa.generate_private_key(
                    public_exponent=65537,
                    key_size=2048,
                )
                wrong_pem = wrong_private_key.private_bytes(
                    encoding=Encoding.PEM,
                    format=PrivateFormat.PKCS8,
                    encryption_algorithm=NoEncryption(),
                )

                payload = {
                    "iss": TEST_ISSUER,
                    "sub": "user@example.com",
                    "aud": "test-client-id",
                    "exp": int(time.time()) + 3600,
                }

                token = jwt.encode(
                    payload,
                    wrong_pem,
                    algorithm="RS256",
                    headers={"kid": "test-key-id"},
                )

                verifier = OAuthTokenVerifier()
                with pytest.raises(TokenValidationError, match="Invalid token"):
                    await verifier.verify_token(token)

    @pytest.mark.asyncio
    async def test_verify_token_wrong_issuer(
        self,
        wrong_issuer_token: str,
        sample_jwks_response: dict[str, Any],
    ) -> None:
        """Test verification of token with wrong issuer."""
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
                with pytest.raises(
                    IssuerMismatchError, match="Token issuer does not match"
                ):
                    await verifier.verify_token(wrong_issuer_token)

    @pytest.mark.asyncio
    async def test_verify_token_invalid_format(
        self,
    ) -> None:
        """Test verification of invalid token format."""
        with patch("ssmcp.oauth.settings") as mock_settings:
            mock_settings.oauth_jwks_url = "https://auth.example.com/jwks"
            mock_settings.oauth_client_id = "test-client-id"
            mock_settings.oauth_issuer = TEST_ISSUER

            verifier = OAuthTokenVerifier()
            with pytest.raises(TokenValidationError, match="Invalid token"):
                await verifier.verify_token("not-a-valid-jwt-token")
