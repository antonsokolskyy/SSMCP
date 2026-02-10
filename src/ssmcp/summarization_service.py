"""LLM summarization service for search results.

This module provides the business logic for summarizing web search results
using an LLM. It handles parallel processing of multiple pages and filters
out empty or failed summaries.
"""

from __future__ import annotations

import asyncio

from ssmcp.llm_client import LLMClient, LLMResponse
from ssmcp.logger import logger


class SummarizationService:
    """Service for summarizing search results using LLM.

    Attributes:
        client: LLMClient instance for making completion requests
        model: Model identifier to use for summarization
        system_prompt: System prompt for summarization behavior

    """

    def __init__(
        self,
        *,
        client: LLMClient,
        model: str,
        system_prompt: str,
    ) -> None:
        """Initialize the summarization service.

        Args:
            client: Configured LLMClient instance
            model: LLM model identifier
            system_prompt: System prompt defining summarization behavior

        """
        self.client = client
        self.model = model
        self.system_prompt = system_prompt

    async def summarize_page(
        self,
        *,
        query: str,
        content: str,
    ) -> LLMResponse:
        """Summarize a single page's content in relation to the query.

        Args:
            query: Original search query for context
            content: Page content to summarize

        Returns:
            LLMResponse with summary or error

        """
        if not content or not content.strip():
            return LLMResponse(content=None, error="Empty content")

        user_prompt = (
            f"Search query: {query}\n\n"
            f"Content to summarize:\n\n"
            f"{content}"
        )

        return await self.client.complete(
            model=self.model,
            system_prompt=self.system_prompt,
            user_prompt=user_prompt,
            temperature=0.0,
        )

    async def summarize_results(
        self,
        *,
        query: str,
        results: list[dict],
    ) -> list[dict]:
        """Summarize multiple search results in parallel.

        Args:
            query: Original search query
            results: List of result dicts with 'url' and 'content' keys

        Returns:
            Filtered list of results with 'summary' field added (empty summaries removed)

        """
        if not results:
            return []

        # Create summarization tasks for all pages
        async def summarize_with_index(
            idx: int,
            result: dict,
        ) -> tuple[int, LLMResponse]:
            response = await self.summarize_page(
                query=query,
                content=result.get("content", ""),
            )
            return (idx, response)

        # Execute all summaries concurrently
        tasks = [summarize_with_index(i, r) for i, r in enumerate(results)]
        summaries = await asyncio.gather(*tasks, return_exceptions=True)

        # Build result list, filtering out empty/failed summaries
        summarized_results: list[dict] = []

        for i, result in enumerate(results):
            summary_data = summaries[i]

            # Handle exceptions in the gather result
            if isinstance(summary_data, Exception):
                continue

            idx, llm_response = summary_data

            # Skip if LLM call failed
            if llm_response.error:
                continue

            # Skip if content is empty/whitespace-only
            if not llm_response.content or not llm_response.content.strip():
                continue

            # Replace content with summary
            result_with_summary = {
                **result,
                "content": llm_response.content,
            }
            summarized_results.append(result_with_summary)

        logger.debug(
            "LLM summarization complete: %d of %d results returned",
            len(summarized_results),
            len(results),
        )

        return summarized_results
