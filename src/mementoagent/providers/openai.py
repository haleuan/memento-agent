"""OpenAI-compatible synchronous and asynchronous providers."""

from typing import TypeVar

from openai import AsyncOpenAI, OpenAI
from openai.types.responses import ResponseInputItemParam
from openai.types.responses.parsed_response import ParsedResponse
from pydantic import BaseModel

ResponseFormat = TypeVar("ResponseFormat", bound=BaseModel)

class OpenAIProvider:
    """Call the OpenAI Responses API synchronously."""

    def __init__(self, api_key: str, base_url: str) -> None:
        """Create a provider client.

        Args:
            api_key: API key used for authentication.
            base_url: Optional custom API base URL.
        """
        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url or None,
        )

    def chat(self, input: str | list[ResponseInputItemParam], model: str):
        """Create a response from input messages.

        Args:
            input: Prompt text or Responses API input items.
            model: Model identifier to use.

        Returns:
            The raw Responses API result.
        """
        return self._client.responses.create(
            model=model,
            input=input,
        )

    def parse(
        self,
        instructions: str,
        input: str | list[ResponseInputItemParam],
        model: str,
        text_format: type[ResponseFormat],
    ) -> ParsedResponse[ResponseFormat]:
        """Parse a response into a Pydantic model.

        Args:
            instructions: System instructions for the model.
            input: Prompt text or Responses API input items.
            model: Model identifier to use.
            text_format: Pydantic model type expected from the response.

        Returns:
            The parsed Responses API result.
        """
        return self._client.responses.parse(
            model=model,
            instructions=instructions,
            input=input,
            text_format=text_format,
        )


class OpenAIAsyncProvider:
    """Call the OpenAI Responses API asynchronously."""

    def __init__(self, api_key: str, base_url: str) -> None:
        """Create an asynchronous provider client.

        Args:
            api_key: API key used for authentication.
            base_url: Optional custom API base URL.
        """
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url or None,
        )

    async def chat(self, input: str | list[ResponseInputItemParam], model: str):
        """Create a response asynchronously.

        Args:
            input: Prompt text or Responses API input items.
            model: Model identifier to use.

        Returns:
            The raw Responses API result.
        """
        return await self._client.responses.create(
            model=model,
            input=input,
        )

    async def parse(
        self,
        instructions: str,
        input: str | list[ResponseInputItemParam],
        model: str,
        text_format: type[ResponseFormat],
    ) -> ParsedResponse[ResponseFormat]:
        """Parse a response into a Pydantic model asynchronously.

        Args:
            instructions: System instructions for the model.
            input: Prompt text or Responses API input items.
            model: Model identifier to use.
            text_format: Pydantic model type expected from the response.

        Returns:
            The parsed Responses API result.
        """
        return await self._client.responses.parse(
            model=model,
            instructions=instructions,
            input=input,
            text_format=text_format,
        )
