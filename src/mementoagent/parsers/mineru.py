"""Synchronous adapter for the MinerU V4 parsing API."""

import hashlib
from pathlib import Path
import tempfile
import time
from typing import Any
from urllib.parse import quote
from zipfile import BadZipFile, ZipFile

import httpx

from mementoagent.config import resolve_mineru_api_base_url
from mementoagent.http import HttpTransport, HttpxTransport


_REQUEST_TIMEOUT_SECONDS = 30.0
_UPLOAD_CHUNK_SIZE = 1024 * 1024


class MineruParserError(RuntimeError):
    """Raised when the MinerU API cannot produce Markdown output."""


class MineruParser:
    """Parse a local source file with MinerU's V4 batch upload API."""

    name = "mineru"

    def __init__(
        self,
        api_key: str,
        *,
        model_version: str = "vlm",
        is_ocr: bool = True,
        poll_interval: float = 2.0,
        timeout: float = 600.0,
        api_base_url: str | None = None,
        transport: HttpTransport | None = None,
    ) -> None:
        """Create a MinerU parser.

        Args:
            api_key: MinerU API token.
            model_version: MinerU V4 model version.
            is_ocr: Whether OCR is enabled for the source file.
            poll_interval: Delay between result polling requests.
            timeout: Maximum time allowed for one parse operation.
            api_base_url: Optional MinerU V4 API base URL.
            transport: Optional HTTP transport, primarily for testing.
        """
        self._api_key = api_key
        self._model_version = model_version
        self._is_ocr = is_ocr
        self._poll_interval = poll_interval
        self._timeout = timeout
        self._api_base_url = resolve_mineru_api_base_url(api_base_url)
        self._transport = transport or HttpxTransport()

    @property
    def version(self) -> str:
        """Return the API and model version recorded in snapshots."""
        return f"api-v4/{self._model_version}"

    def parse(self, source_path: Path) -> str:
        """Parse one file and return its root `full.md` result.

        Args:
            source_path: Path to the source file to parse.

        Returns:
            The complete Markdown result from MinerU.

        Raises:
            MineruParserError: If the API request, task, timeout, or result is invalid.
        """
        deadline = time.monotonic() + self._timeout
        return self._parse_with_transport(source_path, deadline)

    def _parse_with_transport(
        self,
        source_path: Path,
        deadline: float,
    ) -> str:
        data_id = self._stable_data_id(source_path)
        response_data = self._api_request(
            "POST",
            f"{self._api_base_url}/file-urls/batch",
            deadline,
            json={
                "files": [
                    {
                        "name": source_path.name,
                        "data_id": data_id,
                        "is_ocr": self._is_ocr,
                    }
                ],
                "model_version": self._model_version,
            },
        )
        batch_id = response_data.get("batch_id")
        file_urls = response_data.get("file_urls")
        if not isinstance(batch_id, str) or not isinstance(file_urls, list):
            raise MineruParserError("MinerU returned an invalid upload response")
        if len(file_urls) != 1 or not isinstance(file_urls[0], str):
            raise MineruParserError("MinerU returned an invalid upload URL list")

        self._upload_file(source_path, file_urls[0], deadline)
        zip_url = self._wait_for_result(batch_id, data_id, deadline)
        return self._download_markdown(zip_url, deadline)

    def _api_request(
        self,
        method: str,
        url: str,
        deadline: float,
        *,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            response = self._transport.request(
                method,
                url,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=json,
                timeout=self._request_timeout(deadline),
            )
        except httpx.HTTPError:
            operation = self._api_operation(method)
            raise MineruParserError(f"MinerU {operation} failed") from None

        if response.is_error:
            operation = self._api_operation(method)
            raise MineruParserError(
                f"MinerU {operation} failed with HTTP {response.status_code}"
            )

        try:
            payload = response.json()
        except ValueError:
            raise MineruParserError("MinerU returned invalid JSON") from None

        if not isinstance(payload, dict):
            raise MineruParserError("MinerU returned an invalid API response")
        if payload.get("code") != 0:
            message = payload.get("msg")
            if isinstance(message, str) and message:
                raise MineruParserError(f"MinerU API error: {message}")
            raise MineruParserError("MinerU API request was rejected")

        data = payload.get("data")
        if not isinstance(data, dict):
            raise MineruParserError("MinerU returned an invalid API response")
        return data

    def _upload_file(
        self,
        source_path: Path,
        upload_url: str,
        deadline: float,
    ) -> None:
        try:
            with source_path.open("rb") as source_file:
                response = self._transport.request(
                    "PUT",
                    upload_url,
                    content=source_file,
                    headers={"Content-Length": str(source_path.stat().st_size)},
                    timeout=self._request_timeout(deadline),
                )
        except httpx.HTTPError:
            raise MineruParserError("MinerU file upload failed") from None

        if response.is_error:
            raise MineruParserError(
                f"MinerU file upload failed with HTTP {response.status_code}"
            )

    @staticmethod
    def _stable_data_id(source_path: Path) -> str:
        digest = hashlib.sha256()
        with source_path.open("rb") as source_file:
            while chunk := source_file.read(_UPLOAD_CHUNK_SIZE):
                digest.update(chunk)
        identity = hashlib.sha256()
        identity.update(source_path.name.encode("utf-8"))
        identity.update(b"\0")
        identity.update(digest.digest())
        return identity.hexdigest()

    @staticmethod
    def _api_operation(method: str) -> str:
        if method == "POST":
            return "upload URL request"
        return "result polling request"

    def _wait_for_result(
        self,
        batch_id: str,
        data_id: str,
        deadline: float,
    ) -> str:
        result_url = (
            f"{self._api_base_url}/extract-results/batch/{quote(batch_id, safe='')}"
        )
        while True:
            data = self._api_request("GET", result_url, deadline)
            results = data.get("extract_result")
            if not isinstance(results, list):
                raise MineruParserError(
                    "MinerU returned an invalid batch result response"
                )
            result = next(
                (
                    item
                    for item in results
                    if isinstance(item, dict) and item.get("data_id") == data_id
                ),
                None,
            )
            if result is None:
                raise MineruParserError(
                    "MinerU batch result does not contain the requested data ID"
                )

            state = result.get("state")
            if state == "done":
                zip_url = result.get("full_zip_url")
                if isinstance(zip_url, str) and zip_url:
                    return zip_url
                raise MineruParserError(
                    "MinerU completed the task without a result ZIP URL"
                )
            if state == "failed":
                message = result.get("err_msg")
                if isinstance(message, str) and message:
                    raise MineruParserError(f"MinerU parsing failed: {message}")
                raise MineruParserError("MinerU parsing failed")
            if state not in {"waiting-file", "pending", "running", "converting"}:
                raise MineruParserError(
                    f"MinerU returned an unknown task state: {state}"
                )

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise MineruParserError("MinerU parsing timed out")
            time.sleep(min(self._poll_interval, remaining))

    def _download_markdown(
        self,
        zip_url: str,
        deadline: float,
    ) -> str:
        try:
            response = self._transport.request(
                "GET",
                zip_url,
                timeout=self._request_timeout(deadline),
            )
            if response.is_error:
                raise MineruParserError(
                    f"MinerU result download failed with HTTP {response.status_code}"
                )
            with tempfile.TemporaryFile() as result_file:
                result_file.write(response.content)
                result_file.seek(0)
                with ZipFile(result_file) as result_zip:
                    content = result_zip.read("full.md")
        except httpx.HTTPError:
            raise MineruParserError("MinerU result download failed") from None
        except (BadZipFile, KeyError):
            raise MineruParserError(
                "MinerU result ZIP does not contain a valid root full.md"
            ) from None

        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            raise MineruParserError("MinerU full.md is not valid UTF-8") from None

    def _request_timeout(self, deadline: float) -> float:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise MineruParserError("MinerU parsing timed out")
        return min(_REQUEST_TIMEOUT_SECONDS, remaining)
