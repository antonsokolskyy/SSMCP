"""SSMCP custom exceptions."""

class SSMCPError(Exception):
    """Base exception for all SSMCP errors."""


class SearXNGError(SSMCPError):
    """Errors from the SearXNG client."""


class YoutubeError(SSMCPError):
    """Errors from the YouTube client."""


class ParserError(SSMCPError):
    """Errors while parsing content."""


class Crawl4AIError(ParserError):
    """Errors from the Crawl4AI library during extraction."""


class ExtractorError(ParserError):
    """Errors while extracting content."""


class FilterError(ParserError):
    """Errors while filtering content."""


class MarkdownGeneratorError(ParserError):
    """Errors while generating Markdown output."""


class OAuthError(SSMCPError):
    """Base exception for OAuth-related errors."""


class TokenValidationError(OAuthError):
    """Invalid token format or signature verification failed."""


class TokenExpiredError(OAuthError):
    """Token has expired based on exp claim."""


class AudienceMismatchError(OAuthError):
    """Token audience (aud) claim does not match expected client ID."""


class InvalidJWKSURLError(OAuthError):
    """Failed to fetch or parse JWKS from the configured endpoint."""


class SubjectClaimMissingError(OAuthError):
    """Required subject (sub) claim is missing from the token."""
