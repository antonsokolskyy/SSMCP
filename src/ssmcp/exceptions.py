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
