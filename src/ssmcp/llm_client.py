"""Generic OpenAI-compatible LLM client.

This module provides a reusable, feature-agnostic LLM client.
"""

from __future__ import annotations

from dataclasses import dataclass

from openai import AsyncOpenAI


@dataclass(slots=True, kw_only=True)
class LLMResponse:
    """Response from an LLM completion request.

    Attributes:
        content: The generated text content, or None if generation failed
        error: Error message if the request failed, otherwise None

    """

    content: str | None
    error: str | None


class LLMClient:
    """Generic OpenAI-compatible LLM client.

    This client provides a simple interface for making LLM completion requests
    to any OpenAI-compatible API endpoint.

    The client uses connection pooling internally (via httpx) to efficiently
    handle multiple concurrent requests with a single instance.
    """

    def __init__(
        self,
        *,
        api_key: str,
        api_url: str | None = None,
    ) -> None:
        """Initialize the LLM client.

        Args:
            api_key: API key for authentication
            api_url: Optional custom API base URL. If not provided, uses default.

        """
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=api_url if api_url else None,
        )

    async def complete(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """Send a completion request to the LLM.

        Args:
            model: Model identifier to use for completion
            system_prompt: System message content
            user_prompt: User message content
            temperature: Sampling temperature (0.0 = deterministic, default)

        Returns:
            LLMResponse with either content or error message

        """
        try:
            response = await self._client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
            )

            content = response.choices[0].message.content
            if content is None:
                return LLMResponse(content=None, error="Empty response from LLM")

            return LLMResponse(content=content.strip(), error=None)

        except Exception as e:
            return LLMResponse(content=None, error=f"LLM request failed: {e!s}")

    async def close(self) -> None:
        """Close the client and release resources."""
        await self._client.close()
