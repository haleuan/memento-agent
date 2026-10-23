from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Any


class BaseProvicer(ABC):
    @abstractmethod
    def __init__(self, api_key: str, base_url: str) -> None: ...

    @abstractmethod
    def chat(self, input: str | Iterable[str], model: str) -> Any: ...

    @abstractmethod
    def parse(self):
        pass


class BaseAsyncProvider(ABC):
    @abstractmethod
    def __init__(self, api_key: str, base_url: str) -> None: ...

    @abstractmethod
    async def chat(self):
        pass

    @abstractmethod
    async def parse(self):
        pass
