"""Unit tests for LLM client."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ssmcp.llm_client import LLMClient


class TestLLMClient:
    """Test LLMClient class."""

    @pytest.fixture
    def mock_openai(self) -> Generator[MagicMock]:
        """Create mock OpenAI client."""
        with patch("ssmcp.llm_client.AsyncOpenAI") as mock:
            yield mock

    def test_init_default_api_url(self, mock_openai: MagicMock) -> None:
        """Test client initialization with default API URL."""
        client = LLMClient(api_key="test-key")
        mock_openai.assert_called_once_with(api_key="test-key", base_url=None)
        assert client._client is not None

    def test_init_custom_api_url(self, mock_openai: MagicMock) -> None:
        """Test client initialization with custom API URL."""
        client = LLMClient(api_key="test-key", api_url="https://custom.api/v1")
        mock_openai.assert_called_once_with(
            api_key="test-key", base_url="https://custom.api/v1"
        )
        assert client._client is not None

    @pytest.mark.asyncio
    async def test_complete_success(self, mock_openai: MagicMock) -> None:
        """Test successful completion request."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test summary"

        mock_openai.return_value.chat.completions.create = AsyncMock(
            return_value=mock_response
        )

        client = LLMClient(api_key="test-key")
        response = await client.complete(
            model="gpt-4",
            system_prompt="You are helpful.",
            user_prompt="Summarize this.",
            temperature=0.0,
        )

        assert response.content == "Test summary"
        assert response.error is None

        mock_openai.return_value.chat.completions.create.assert_called_once_with(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Summarize this."},
            ],
            temperature=0.0,
        )

    @pytest.mark.asyncio
    async def test_complete_empty_response(self, mock_openai: MagicMock) -> None:
        """Test completion when LLM returns empty content."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None

        mock_openai.return_value.chat.completions.create = AsyncMock(
            return_value=mock_response
        )

        client = LLMClient(api_key="test-key")
        response = await client.complete(
            model="gpt-4",
            system_prompt="You are helpful.",
            user_prompt="Summarize this.",
        )

        assert response.content is None
        assert response.error == "Empty response from LLM"

    @pytest.mark.asyncio
    async def test_complete_api_error(self, mock_openai: MagicMock) -> None:
        """Test completion when API raises an error."""
        mock_openai.return_value.chat.completions.create = AsyncMock(
            side_effect=Exception("API failure")
        )

        client = LLMClient(api_key="test-key")
        response = await client.complete(
            model="gpt-4",
            system_prompt="You are helpful.",
            user_prompt="Summarize this.",
        )

        assert response.content is None
        assert response.error == "LLM request failed: API failure"

    @pytest.mark.asyncio
    async def test_close(self, mock_openai: MagicMock) -> None:
        """Test closing the client."""
        mock_openai.return_value.close = AsyncMock()

        client = LLMClient(api_key="test-key")
        await client.close()

        mock_openai.return_value.close.assert_called_once()
