"""Abstract interfaces for synchronous and asynchronous providers."""

from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Any


class BaseProvicer(ABC):
    """Base interface for synchronous language-model providers."""

    @abstractmethod
    def __init__(self, api_key: str, base_url: str) -> None:
        """Initialize provider credentials and endpoint.

        Args:
            api_key: Secret token used to authenticate with the provider.
            base_url: Optional provider API endpoint.
        """
        ...

    @abstractmethod
    def chat(self, input: str | Iterable[str], model: str) -> Any:
        """Generate a response from input messages.

        Args:
            input: Prompt text or a sequence of message strings.
            model: Provider model identifier.

        Returns:
            The provider response.
        """
        ...

    @abstractmethod
    def parse(self):
        """Parse a response into a structured representation.

        Returns:
            The provider response in its structured representation.
        """
        pass


class BaseAsyncProvider(ABC):
    """Base interface for asynchronous language-model providers."""

    @abstractmethod
    def __init__(self, api_key: str, base_url: str) -> None:
        """Initialize provider credentials and endpoint.

        Args:
            api_key: Secret token used to authenticate with the provider.
            base_url: Optional provider API endpoint.
        """
        ...

    @abstractmethod
    async def chat(self):
        """Generate a response asynchronously.

        Returns:
            The provider response.
        """
        pass

    @abstractmethod
    async def parse(self):
        """Parse a response into a structured representation asynchronously.

        Returns:
            The provider response in its structured representation.
        """
        pass
