"""Runtime configuration for external service integrations."""

import os

DEFAULT_MINERU_API_BASE_URL = "https://mineru.net/api/v4"
MINERU_API_BASE_URL_ENV = "MEMENTO_MINERU_API_BASE_URL"


def resolve_mineru_api_base_url(explicit: str | None = None) -> str:
    """Resolve the MinerU API base URL from runtime configuration.

    Args:
        explicit: Optional URL supplied directly by the caller.

    Returns:
        A base URL without a trailing slash.

    Raises:
        ValueError: If an explicitly supplied or environment URL is empty.
    """
    value = explicit if explicit is not None else os.getenv(MINERU_API_BASE_URL_ENV)
    if value is None:
        value = DEFAULT_MINERU_API_BASE_URL
    value = value.strip()
    if not value:
        raise ValueError("MinerU API base URL must not be empty")
    return value.rstrip("/")
