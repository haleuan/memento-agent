"""In-memory conversation history for an Agent."""

from collections.abc import Sequence
from typing import cast

from openai.types.responses import ResponseInputItemParam, ResponseOutputItem


class Conversation:
    """Hold the replay history for one in-memory conversation."""

    def __init__(self) -> None:
        """Create an empty conversation."""
        self._items: list[ResponseInputItemParam] = []

    def snapshot(self) -> list[ResponseInputItemParam]:
        """Return a copy of the replayable Responses input history."""
        return [*self._items]

    def append_user_message(self, content: str) -> None:
        """Append one user message to the conversation history."""
        self._items.append({"role": "user", "content": content})

    def append_completed_response(
        self,
        output_items: Sequence[ResponseOutputItem],
        tool_outputs: Sequence[tuple[str, str]] = (),
    ) -> None:
        """Append a completed model response and its tool outputs atomically.

        Args:
            output_items: Complete output items returned by Responses API.
            tool_outputs: Ordered `(call_id, output)` pairs produced for the
                function calls in `output_items`.
        """
        items: list[ResponseInputItemParam] = [
            cast(
                ResponseInputItemParam,
                item.model_dump(by_alias=True, exclude_none=True),
            )
            for item in output_items
        ]
        items.extend(
            {
                "type": "function_call_output",
                "call_id": call_id,
                "output": output,
            }
            for call_id, output in tool_outputs
        )
        self._items.extend(items)

    def clear(self) -> None:
        """Forget all model and tool items in this conversation."""
        self._items.clear()
