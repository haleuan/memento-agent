from typing import TypeVar

from openai import AsyncOpenAI, OpenAI
from openai.types.responses import ResponseInputItemParam
from openai.types.responses.parsed_response import ParsedResponse
from pydantic import BaseModel

ResponseFormat = TypeVar("ResponseFormat", bound=BaseModel)

class OpenAIProvider:
    def __init__(self, api_key: str, base_url: str) -> None:
        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url or None,
        )

    def chat(self, input: str | list[ResponseInputItemParam], model: str):
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
        return self._client.responses.parse(
            model=model,
            instructions=instructions,
            input=input,
            text_format=text_format,
        )


class OpenAIAsyncProvider:
    def __init__(self, api_key: str, base_url: str) -> None:
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url or None,
        )

    async def chat(self, input: str | list[ResponseInputItemParam], model: str):
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
        return await self._client.responses.parse(
            model=model,
            instructions=instructions,
            input=input,
            text_format=text_format,
        )
