"""In-memory conversation history for an Agent."""

from typing import Any


class Conversation:
    """Hold the replay history for one in-memory conversation."""

    def __init__(self) -> None:
        """Create an empty conversation."""
        self._items: list[Any] = []

    def clear(self) -> None:
        """Forget all model and tool items in this conversation."""
        self._items.clear()
