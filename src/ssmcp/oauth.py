"""OAuth token verification using JWKS from any OIDC-compliant identity provider."""

import asyncio
import time
from typing import Any

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers

from ssmcp.config import settings
from ssmcp.exceptions import (
    AudienceMismatchError,
    InvalidJWKSURLError,
    SubjectClaimMissingError,
    TokenExpiredError,
    TokenValidationError,
)

__all__ = ["JWKSProvider", "OAuthTokenVerifier"]


class JWKSProvider:
    """Fetches and caches JWKS (JSON Web Key Set) from any OIDC-compliant identity provider.

    This provider retrieves public keys from the JWKS endpoint and caches
    them to avoid repeated requests. Keys are cached with a TTL.
    """

    def __init__(self, jwks_url: str, cache_ttl: int = 3600) -> None:
        """Initialize JWKS provider.

        Args:
            jwks_url: URL to the JWKS endpoint (e.g., https://auth.example.com/application/o/app/jwks)
            cache_ttl: Time-to-live for cached keys in seconds (default: 1 hour)

        """
        self.jwks_url = jwks_url
        self.cache_ttl = cache_ttl
        self._cache_time: float = 0.0
        self._keys: dict[str, Any] = {}
        self._refresh_lock = asyncio.Lock()

    async def get_key(self, kid: str) -> Any:
        """Get a public key by key ID.

        Args:
            kid: Key ID from JWT header

        Returns:
            Public key for the given kid

        Raises:
            InvalidJWKSURLError: If key cannot be fetched or found

        """
        # Check if cache is still valid
        if time.time() - self._cache_time > self.cache_ttl:
            await self._refresh_cache()

        if kid not in self._keys:
            # Try to refresh cache if key not found
            await self._refresh_cache()
            if kid not in self._keys:
                msg = f"Key with kid '{kid}' not found in JWKS"
                raise InvalidJWKSURLError(msg)

        return self._keys[kid]

    async def _refresh_cache(self) -> None:
        """Fetch and cache JWKS from the configured endpoint.

        Uses a lock to prevent concurrent refresh requests.

        Raises:
            InvalidJWKSURLError: If JWKS cannot be fetched or parsed

        """
        async with self._refresh_lock:
            # Check again if another task already refreshed while we waited for the lock
            if time.time() - self._cache_time <= self.cache_ttl:
                return

            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(self.jwks_url)
                    response.raise_for_status()
                    jwks_data = response.json()

                # Parse and cache keys
                self._keys = {}
                for key_data in jwks_data.get("keys", []):
                    key = self._parse_jwk(key_data)
                    self._keys[key_data["kid"]] = key

                self._cache_time = time.time()
            except httpx.HTTPError as e:
                msg = f"Failed to fetch JWKS from {self.jwks_url}: {e}"
                raise InvalidJWKSURLError(msg) from e
            except KeyError as e:
                msg = f"Invalid JWKS format: missing key {e}"
                raise InvalidJWKSURLError(msg) from e

    def _parse_jwk(self, jwk_data: dict[str, Any]) -> Any:
        """Parse a JWK into a public key.

        Args:
            jwk_data: JWK data from JWKS endpoint

        Returns:
            Public key object

        Raises:
            InvalidJWKSURLError: If JWK cannot be parsed

        """
        try:
            if jwk_data.get("kty") != "RSA":
                msg = f"Unsupported key type: {jwk_data.get('kty')}"
                raise InvalidJWKSURLError(msg)

            # Extract RSA public key components
            e = int.from_bytes(jwt.utils.base64url_decode(jwk_data["e"]))
            n = int.from_bytes(jwt.utils.base64url_decode(jwk_data["n"]))

            # Create RSA public key
            numbers = RSAPublicNumbers(e=e, n=n)
            return numbers.public_key()
        except (KeyError, ValueError) as e:
            msg = f"Failed to parse JWK: {e}"
            raise InvalidJWKSURLError(msg) from e


class OAuthTokenVerifier:
    """Verifies OAuth JWT tokens from any OIDC-compliant identity provider using JWKS.

    This verifier implements the MCP TokenVerifier protocol and validates:
    - JWT signature using JWKS public keys
    - Token expiration (exp claim)
    - Audience (aud claim) matches configured client ID
    - Subject (sub claim) exists and contains user email

    """

    def __init__(self) -> None:
        """Initialize OAuth token verifier."""
        self.jwks_provider = JWKSProvider(settings.oauth_jwks_url)

    async def verify_token(self, token: str) -> dict[str, Any]:
        """Verify a JWT token and return its payload.

        Args:
            token: JWT access token string

        Returns:
            Dictionary containing token payload with user information

        Raises:
            TokenValidationError: If token format or signature is invalid
            TokenExpiredError: If token has expired
            AudienceMismatchError: If aud claim doesn't match client ID
            SubjectClaimMissingError: If sub claim is missing

        """
        try:
            # Decode header to get kid (key ID)
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")

            if not kid:
                msg = "Token missing 'kid' in header"
                raise TokenValidationError(msg)

            # Get the public key for this token
            public_key = await self.jwks_provider.get_key(kid)

            # Verify and decode the token
            payload = jwt.decode(
                token,
                key=public_key,
                algorithms=["RS256"],
                options={
                    "verify_iss": False,  # Don't validate issuer
                    "verify_aud": True,
                    "verify_exp": True,
                },
                audience=settings.oauth_client_id,
            )

            # Verify subject claim exists
            sub = payload.get("sub")
            if not sub:
                msg = "Token missing 'sub' claim"
                raise SubjectClaimMissingError(msg)

            # Return user information
            return {"sub": sub, "payload": payload}

        except jwt.ExpiredSignatureError as e:
            raise TokenExpiredError("Token has expired") from e
        except jwt.InvalidAudienceError as e:
            msg = f"Token audience does not match expected client ID '{settings.oauth_client_id}'"
            raise AudienceMismatchError(msg) from e
        except jwt.InvalidTokenError as e:
            msg = f"Invalid token: {e}"
            raise TokenValidationError(msg) from e
        except (InvalidJWKSURLError, SubjectClaimMissingError):
            raise  # Re-raise our custom exceptions
        except Exception as e:
            msg = f"Unexpected error verifying token: {e}"
            raise TokenValidationError(msg) from e
