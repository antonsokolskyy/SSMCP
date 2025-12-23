"""Parser package for web content extraction and markdown conversion.

This package provides a pipeline for extracting content from web pages
and converting it to clean Markdown format.
"""

from ssmcp.exceptions import FilterError
from ssmcp.parser.extractor import ExtractionResult, Extractor
from ssmcp.parser.filter import Filter
from ssmcp.parser.markdown_generator import MarkdownGenerator
from ssmcp.parser.parser import Parser
from ssmcp.parser.protocols import ContentFilter

__all__ = [
    "ContentFilter",
    "ExtractionResult",
    "Extractor",
    "Filter",
    "FilterError",
    "MarkdownGenerator",
    "Parser",
]
