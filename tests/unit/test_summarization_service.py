"""Unit tests for summarization service."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from ssmcp.llm_client import LLMClient, LLMResponse
from ssmcp.summarization_service import SummarizationService

# Test constants
NUM_RESULTS_THREE = 3
NUM_RESULTS_TWO = 2
SCORE_VALUE = 0.9


class TestSummarizationService:
    """Test SummarizationService class."""

    @pytest.fixture
    def mock_llm_client(self) -> MagicMock:
        """Create mock LLM client."""
        client = MagicMock(spec=LLMClient)
        client.complete = AsyncMock()
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def service(self, mock_llm_client: MagicMock) -> SummarizationService:
        """Create SummarizationService instance."""
        return SummarizationService(
            client=mock_llm_client,
            model="gpt-4",
            system_prompt="You are a summarizer.",
        )

    @pytest.mark.asyncio
    async def test_summarize_page_success(
        self, service: SummarizationService, mock_llm_client: MagicMock
    ) -> None:
        """Test successful page summarization."""
        mock_llm_client.complete.return_value = LLMResponse(
            content="Summary of content", error=None
        )

        response = await service.summarize_page(
            query="test query",
            content="This is test content to summarize",
        )

        assert response.content == "Summary of content"
        assert response.error is None

        mock_llm_client.complete.assert_called_once_with(
            model="gpt-4",
            system_prompt="You are a summarizer.",
            user_prompt=(
                "Search query: test query\n\n"
                "Content to summarize:\n\n"
                "This is test content to summarize"
            ),
            temperature=0.0,
        )

    @pytest.mark.asyncio
    async def test_summarize_page_empty_content(
        self, service: SummarizationService, mock_llm_client: MagicMock
    ) -> None:
        """Test summarization with empty content."""
        response = await service.summarize_page(query="test", content="")

        assert response.content is None
        assert response.error == "Empty content"
        mock_llm_client.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_summarize_page_whitespace_only(
        self, service: SummarizationService, mock_llm_client: MagicMock
    ) -> None:
        """Test summarization with whitespace-only content."""
        response = await service.summarize_page(query="test", content="   \n\t  ")

        assert response.content is None
        assert response.error == "Empty content"
        mock_llm_client.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_summarize_results_empty_list(
        self, service: SummarizationService,
    ) -> None:
        """Test summarization with empty results list."""
        results = await service.summarize_results(query="test", results=[])

        assert results == []

    @pytest.mark.asyncio
    async def test_summarize_results_all_success(
        self, service: SummarizationService, mock_llm_client: MagicMock
    ) -> None:
        """Test summarizing multiple pages all successfully."""
        mock_llm_client.complete.side_effect = [
            LLMResponse(content="Summary 1", error=None),
            LLMResponse(content="Summary 2", error=None),
            LLMResponse(content="Summary 3", error=None),
        ]

        input_results = [
            {"url": "http://example1.com", "content": "Content 1"},
            {"url": "http://example2.com", "content": "Content 2"},
            {"url": "http://example3.com", "content": "Content 3"},
        ]

        results = await service.summarize_results(
            query="test query", results=input_results
        )

        assert len(results) == NUM_RESULTS_THREE
        assert results[0]["url"] == "http://example1.com"
        assert results[0]["content"] == "Summary 1"
        assert results[1]["url"] == "http://example2.com"
        assert results[1]["content"] == "Summary 2"
        assert results[2]["url"] == "http://example3.com"
        assert results[2]["content"] == "Summary 3"

        assert mock_llm_client.complete.call_count == NUM_RESULTS_THREE

    @pytest.mark.asyncio
    async def test_summarize_results_filters_empty_summaries(
        self, service: SummarizationService, mock_llm_client: MagicMock
    ) -> None:
        """Test that empty summaries are filtered out."""
        mock_llm_client.complete.side_effect = [
            LLMResponse(content="Summary 1", error=None),
            LLMResponse(content="", error=None),  # Empty string
            LLMResponse(content="   ", error=None),  # Whitespace only
            LLMResponse(content="Summary 4", error=None),
        ]

        input_results = [
            {"url": "http://example1.com", "content": "Content 1"},
            {"url": "http://example2.com", "content": "Content 2"},
            {"url": "http://example3.com", "content": "Content 3"},
            {"url": "http://example4.com", "content": "Content 4"},
        ]

        results = await service.summarize_results(
            query="test query", results=input_results
        )

        assert len(results) == NUM_RESULTS_TWO
        assert results[0]["content"] == "Summary 1"
        assert results[1]["content"] == "Summary 4"

    @pytest.mark.asyncio
    async def test_summarize_results_filters_errors(
        self, service: SummarizationService, mock_llm_client: MagicMock
    ) -> None:
        """Test that failed LLM calls are filtered out."""
        mock_llm_client.complete.side_effect = [
            LLMResponse(content="Summary 1", error=None),
            LLMResponse(content=None, error="API error"),
            LLMResponse(content="Summary 3", error=None),
        ]

        input_results = [
            {"url": "http://example1.com", "content": "Content 1"},
            {"url": "http://example2.com", "content": "Content 2"},
            {"url": "http://example3.com", "content": "Content 3"},
        ]

        results = await service.summarize_results(
            query="test query", results=input_results
        )

        assert len(results) == NUM_RESULTS_TWO
        assert results[0]["content"] == "Summary 1"
        assert results[1]["content"] == "Summary 3"

    @pytest.mark.asyncio
    async def test_summarize_results_handles_exceptions(
        self, service: SummarizationService, mock_llm_client: MagicMock
    ) -> None:
        """Test that exceptions during LLM calls are handled gracefully."""
        mock_llm_client.complete.side_effect = [
            LLMResponse(content="Summary 1", error=None),
            Exception("Network error"),
            LLMResponse(content="Summary 3", error=None),
        ]

        input_results = [
            {"url": "http://example1.com", "content": "Content 1"},
            {"url": "http://example2.com", "content": "Content 2"},
            {"url": "http://example3.com", "content": "Content 3"},
        ]

        results = await service.summarize_results(
            query="test query", results=input_results
        )

        assert len(results) == NUM_RESULTS_TWO
        assert results[0]["content"] == "Summary 1"
        assert results[1]["content"] == "Summary 3"

    @pytest.mark.asyncio
    async def test_summarize_results_preserves_other_fields(
        self, service: SummarizationService, mock_llm_client: MagicMock
    ) -> None:
        """Test that other fields in result dict are preserved."""
        mock_llm_client.complete.return_value = LLMResponse(
            content="Summary", error=None
        )

        input_results = [
            {
                "url": "http://example.com",
                "content": "Content",
                "title": "Test",
                "score": SCORE_VALUE,
            },
        ]

        results = await service.summarize_results(query="test", results=input_results)

        assert len(results) == 1
        assert results[0]["url"] == "http://example.com"
        assert results[0]["content"] == "Summary"  # Replaced
        assert results[0]["title"] == "Test"  # Preserved
        assert results[0]["score"] == SCORE_VALUE  # Preserved

    @pytest.mark.asyncio
    async def test_summarize_results_with_missing_content(
        self, service: SummarizationService, mock_llm_client: MagicMock
    ) -> None:
        """Test handling results with missing content field."""
        mock_llm_client.complete.return_value = LLMResponse(
            content="Summary", error=None
        )

        input_results = [
            {"url": "http://example1.com", "content": "Content 1"},
            {"url": "http://example2.com"},  # No content field
        ]

        results = await service.summarize_results(query="test", results=input_results)

        # Only first result should be processed - second has no content and gets filtered out
        assert mock_llm_client.complete.call_count == 1
        assert len(results) == 1
        assert results[0]["url"] == "http://example1.com"
