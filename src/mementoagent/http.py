"""Small HTTP transport abstractions used by external providers."""

from collections.abc import Mapping
from typing import BinaryIO, Protocol

import httpx


class HttpTransport(Protocol):
    """Send HTTP requests without imposing provider-specific semantics."""

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        json: object | None = None,
        content: bytes | BinaryIO | None = None,
        timeout: float | None = None,
    ) -> httpx.Response:
        """Send one HTTP request and return its response.

        Args:
            method: HTTP method.
            url: Absolute request URL.
            headers: Optional request headers.
            json: Optional JSON request body.
            content: Optional raw request body.
            timeout: Optional request timeout in seconds.

        Returns:
            The HTTP response.
        """
        ...


class HttpxTransport:
    """Default transport backed by an `httpx.Client`."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        """Create an HTTPX transport.

        Args:
            client: Optional client to use for requests.
        """
        self._client = client or httpx.Client()

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        json: object | None = None,
        content: bytes | BinaryIO | None = None,
        timeout: float | None = None,
    ) -> httpx.Response:
        """Send one request through the configured HTTPX client.

        Args:
            method: HTTP method.
            url: Absolute request URL.
            headers: Optional request headers.
            json: Optional JSON request body.
            content: Optional raw request body.
            timeout: Optional request timeout in seconds.

        Returns:
            The HTTP response.
        """
        return self._client.request(
            method,
            url,
            headers=headers,
            json=json,
            content=content,
            timeout=timeout,
        )
