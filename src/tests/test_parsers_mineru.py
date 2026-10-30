"""Tests for the MinerU parser adapter."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from io import BytesIO
import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import BinaryIO
from unittest.mock import Mock
import zipfile

import httpx
import pytest
from dotenv import load_dotenv

from mementoagent.parsers.mineru import MineruParser, MineruParserError
from mementoagent.parsers.pipeline import parse_and_save_snapshot
from mementoagent.http import HttpxTransport
from mementoagent.workspace import (
    find_workspace,
    import_source,
    init_workspace,
    load_parse_snapshot,
)


def make_result_zip(content: str = "# Parsed\n\nUnicode: 奖状\n") -> bytes:
    """Return a result archive containing the required Markdown output."""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("full.md", content)
    return buffer.getvalue()


def make_invalid_utf8_zip() -> bytes:
    """Return a valid archive whose Markdown member is not UTF-8."""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("full.md", b"\xff")
    return buffer.getvalue()


def make_client(
    handler: Callable[[httpx.Request], httpx.Response],
) -> httpx.Client:
    """Build a client for a transport handler.

    Args:
        handler: Request handler passed to `httpx.MockTransport`.

    Returns:
        A client using the mock transport.
    """
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_httpx_transport_forwards_request_arguments() -> None:
    """Forward HTTP request arguments to the injected HTTPX client."""
    response = httpx.Response(204)
    client = Mock(spec=httpx.Client)
    client.request.return_value = response
    transport = HttpxTransport(client)

    result = transport.request(
        "POST",
        "https://example.test/endpoint",
        headers={"X-Test": "value"},
        json={"key": "value"},
        content=b"body",
        timeout=3.5,
    )

    assert result is response
    client.request.assert_called_once_with(
        "POST",
        "https://example.test/endpoint",
        headers={"X-Test": "value"},
        json={"key": "value"},
        content=b"body",
        timeout=3.5,
    )


class RecordingTransport:
    """Minimal transport fake for endpoint and header assertions."""

    def __init__(self, source_path: Path, result_zip: bytes) -> None:
        """Create a fake transport for one source and result archive.

        Args:
            source_path: Source file used to derive the expected data ID.
            result_zip: ZIP bytes returned by the download request.
        """
        self.source_path = source_path
        self.result_zip = result_zip
        self.calls: list[tuple[str, str, dict[str, str]]] = []

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
        """Record a request and return the corresponding fake response.

        Args:
            method: HTTP method.
            url: Absolute request URL.
            headers: Optional request headers.
            json: Optional JSON body.
            content: Optional request body.
            timeout: Request timeout.

        Returns:
            A response matching the request stage.
        """
        del timeout
        request_headers = dict(headers or {})
        self.calls.append((method, url, request_headers))
        request = httpx.Request(method, url, headers=request_headers)
        if method == "POST":
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "batch_id": "batch-custom",
                        "file_urls": ["https://upload.example/file"],
                    },
                },
                request=request,
            )
        if method == "PUT":
            assert "Authorization" not in request_headers
            return httpx.Response(200, request=request)
        if url.endswith("/extract-results/batch/batch-custom"):
            data_id = MineruParser._stable_data_id(self.source_path)
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "extract_result": [
                            {
                                "data_id": data_id,
                                "state": "done",
                                "full_zip_url": "https://download.example/result.zip",
                            }
                        ]
                    },
                },
                request=request,
            )
        if url == "https://download.example/result.zip":
            assert "Authorization" not in request_headers
            return httpx.Response(200, content=self.result_zip, request=request)
        raise AssertionError(f"unexpected request: {method} {url}")


def test_mineru_parser_supports_custom_base_url_and_transport(
    tmp_path: Path,
) -> None:
    """Use an injected transport and a private MinerU API endpoint."""
    source_path = tmp_path / "source.pdf"
    source_path.write_bytes(b"source")
    transport = RecordingTransport(source_path, make_result_zip("# custom\n"))
    parser = MineruParser(
        "secret",
        api_base_url="https://private.example/api/v4/",
        transport=transport,
        poll_interval=0,
    )

    assert parser.parse(source_path) == "# custom\n"
    assert transport.calls[0][0:2] == (
        "POST",
        "https://private.example/api/v4/file-urls/batch",
    )
    assert transport.calls[0][2]["Authorization"] == "Bearer secret"
    assert transport.calls[2][0:2] == (
        "GET",
        "https://private.example/api/v4/extract-results/batch/batch-custom",
    )


def test_mineru_base_url_explicit_value_overrides_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolve explicit endpoint before the environment endpoint."""
    monkeypatch.setenv(
        "MEMENTO_MINERU_API_BASE_URL", "https://environment.example/api/v4/"
    )

    environment_parser = MineruParser("secret")
    explicit_parser = MineruParser(
        "secret", api_base_url="https://explicit.example/api/v4/"
    )

    assert environment_parser._api_base_url == "https://environment.example/api/v4"
    assert explicit_parser._api_base_url == "https://explicit.example/api/v4"


def test_mineru_parser_uploads_polls_and_extracts_markdown(
    tmp_path: Path,
) -> None:
    """Run the complete mocked MinerU flow and preserve Markdown exactly."""
    source_path = tmp_path / "certificate.pdf"
    source_bytes = b"opaque source bytes"
    source_path.write_bytes(source_bytes)
    result_content = "# 证书\n\n---\nUnicode: 郑皓月\n"
    result_zip = make_result_zip(result_content)
    requests: list[httpx.Request] = []
    poll_count = 0
    data_id = ""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal poll_count, data_id
        requests.append(request)
        if request.url.path == "/api/v4/file-urls/batch":
            assert request.headers["Authorization"] == "Bearer secret"
            payload = json.loads(request.content)
            data_id = payload["files"][0]["data_id"]
            expected_digest = hashlib.sha256(source_bytes).digest()
            expected_data_id = hashlib.sha256(
                b"certificate.pdf\0" + expected_digest
            ).hexdigest()
            assert data_id == expected_data_id
            assert payload["files"][0]["name"] == "certificate.pdf"
            assert payload["model_version"] == "vlm"
            assert payload["files"][0]["is_ocr"] is True
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "batch_id": "batch-1",
                        "file_urls": ["https://upload.example/file"],
                    },
                },
                request=request,
            )
        if request.url.host == "upload.example":
            assert request.method == "PUT"
            assert "Authorization" not in request.headers
            assert request.content == source_bytes
            return httpx.Response(200, request=request)
        if request.url.path == "/api/v4/extract-results/batch/batch-1":
            assert request.headers["Authorization"] == "Bearer secret"
            poll_count += 1
            state = ["pending", "running", "done"][poll_count - 1]
            result = {"data_id": data_id, "state": state}
            if state == "done":
                result["full_zip_url"] = "https://download.example/result.zip"
            return httpx.Response(
                200,
                json={"code": 0, "data": {"extract_result": [result]}},
                request=request,
            )
        if request.url.host == "download.example":
            assert "Authorization" not in request.headers
            return httpx.Response(200, content=result_zip, request=request)
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    client = make_client(handler)
    parser = MineruParser(
        "secret",
        transport=HttpxTransport(client),
        poll_interval=0,
        timeout=1,
    )

    assert parser.parse(source_path) == result_content
    assert poll_count == 3
    assert len(requests) == 6
    client.close()


def test_parse_and_save_snapshot_integrates_with_workspace(tmp_path: Path) -> None:
    """Persist successful MinerU output through the existing snapshot API."""
    workspace_root = init_workspace(tmp_path / "workspace")
    staged_source = tmp_path / "source.pdf"
    staged_source.write_bytes(b"source")
    source_id = import_source(workspace_root, staged_source)
    result_content = "# parsed\n\n内容\n"
    data_id = ""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal data_id
        if request.url.path == "/api/v4/file-urls/batch":
            data_id = json.loads(request.content)["files"][0]["data_id"]
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "batch_id": "batch-1",
                        "file_urls": ["https://upload.example/file"],
                    },
                },
                request=request,
            )
        if request.url.host == "upload.example":
            return httpx.Response(200, request=request)
        if request.url.path == "/api/v4/extract-results/batch/batch-1":
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "extract_result": [
                            {
                                "data_id": data_id,
                                "state": "done",
                                "full_zip_url": "https://download.example/result.zip",
                            }
                        ]
                    },
                },
                request=request,
            )
        if request.url.host == "download.example":
            return httpx.Response(
                200,
                content=make_result_zip(result_content),
                request=request,
            )
        raise AssertionError(f"unexpected request: {request.url}")

    client = make_client(handler)
    parser = MineruParser(
        "secret",
        transport=HttpxTransport(client),
        poll_interval=0,
        timeout=1,
    )
    snapshot_dir = parse_and_save_snapshot(workspace_root, source_id, parser)
    snapshot = load_parse_snapshot(snapshot_dir)

    assert snapshot.content == result_content
    assert snapshot.metadata.source == source_id
    assert snapshot.metadata.parser == "mineru"
    assert snapshot.metadata.parser_version == "api-v4/vlm"
    assert (snapshot_dir / "metadata.toml").is_file()
    assert (snapshot_dir / "content.md").read_text(encoding="utf-8") == result_content
    client.close()


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (
            httpx.Response(503, text="unavailable"),
            "upload URL request failed with HTTP 503",
        ),
        (
            httpx.Response(200, json={"code": 1, "msg": "bad token"}),
            "MinerU API error",
        ),
    ],
)
def test_mineru_parser_rejects_upload_request_errors(
    tmp_path: Path,
    response: httpx.Response,
    message: str,
) -> None:
    """Convert HTTP and API-level upload errors into parser errors."""
    source_path = tmp_path / "source.pdf"
    source_path.write_bytes(b"source")

    def handler(request: httpx.Request) -> httpx.Response:
        response.request = request
        return response

    client = make_client(handler)
    parser = MineruParser(
        "secret",
        transport=HttpxTransport(client),
        poll_interval=0,
        timeout=1,
    )
    with pytest.raises(MineruParserError, match=message):
        parser.parse(source_path)
    client.close()


def test_mineru_parser_rejects_failed_task(tmp_path: Path) -> None:
    """Raise when MinerU reports a failed task."""
    source_path = tmp_path / "source.pdf"
    source_path.write_bytes(b"source")
    data_id = ""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal data_id
        if request.url.path == "/api/v4/file-urls/batch":
            data_id = json.loads(request.content)["files"][0]["data_id"]
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "batch_id": "batch-1",
                        "file_urls": ["https://upload.example/file"],
                    },
                },
                request=request,
            )
        if request.url.host == "upload.example":
            return httpx.Response(200, request=request)
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "extract_result": [
                        {
                            "data_id": data_id,
                            "state": "failed",
                            "err_msg": "parse failed",
                        }
                    ]
                },
            },
            request=request,
        )

    client = make_client(handler)
    parser = MineruParser(
        "secret",
        transport=HttpxTransport(client),
        poll_interval=0,
        timeout=1,
    )
    with pytest.raises(MineruParserError, match="parse failed"):
        parser.parse(source_path)
    client.close()


def test_mineru_parser_rejects_upload_failure(tmp_path: Path) -> None:
    """Raise a parser error when the signed upload URL rejects the file."""
    source_path = tmp_path / "source.pdf"
    source_path.write_bytes(b"source")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v4/file-urls/batch":
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "batch_id": "batch-1",
                        "file_urls": ["https://upload.example/file"],
                    },
                },
                request=request,
            )
        return httpx.Response(403, request=request)

    client = make_client(handler)
    parser = MineruParser("secret", transport=HttpxTransport(client))
    with pytest.raises(MineruParserError, match="file upload failed with HTTP 403"):
        parser.parse(source_path)
    client.close()


@pytest.mark.parametrize(
    ("state", "message"),
    [("queued", "unknown task state"), ("pending", "timed out")],
)
def test_mineru_parser_rejects_unknown_state_and_timeout(
    tmp_path: Path,
    state: str,
    message: str,
) -> None:
    """Reject unsupported task states and bound polling by the parse timeout."""
    source_path = tmp_path / "source.pdf"
    source_path.write_bytes(b"source")
    data_id = ""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal data_id
        if request.url.path == "/api/v4/file-urls/batch":
            data_id = json.loads(request.content)["files"][0]["data_id"]
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "batch_id": "batch-1",
                        "file_urls": ["https://upload.example/file"],
                    },
                },
                request=request,
            )
        if request.url.host == "upload.example":
            return httpx.Response(200, request=request)
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {"extract_result": [{"data_id": data_id, "state": state}]},
            },
            request=request,
        )

    client = make_client(handler)
    timeout = 0.001 if state == "pending" else 1
    parser = MineruParser(
        "secret",
        transport=HttpxTransport(client),
        poll_interval=0,
        timeout=timeout,
    )
    with pytest.raises(MineruParserError, match=message):
        parser.parse(source_path)
    client.close()


def test_mineru_parser_rejects_missing_full_markdown(tmp_path: Path) -> None:
    """Require the documented `full.md` member in the result archive."""
    source_path = tmp_path / "source.pdf"
    source_path.write_bytes(b"source")
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("other.md", "content")
    data_id = ""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal data_id
        if request.url.path == "/api/v4/file-urls/batch":
            data_id = json.loads(request.content)["files"][0]["data_id"]
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "batch_id": "batch-1",
                        "file_urls": ["https://upload.example/file"],
                    },
                },
                request=request,
            )
        if request.url.host == "upload.example":
            return httpx.Response(200, request=request)
        if request.url.path == "/api/v4/extract-results/batch/batch-1":
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "extract_result": [
                            {
                                "data_id": data_id,
                                "state": "done",
                                "full_zip_url": "https://download.example/result.zip",
                            }
                        ]
                    },
                },
                request=request,
            )
        return httpx.Response(200, content=buffer.getvalue(), request=request)

    client = make_client(handler)
    parser = MineruParser(
        "secret",
        transport=HttpxTransport(client),
        poll_interval=0,
        timeout=1,
    )
    with pytest.raises(MineruParserError, match="full.md"):
        parser.parse(source_path)
    client.close()


@pytest.mark.parametrize(
    ("archive_bytes", "message"),
    [
        (b"not a zip file", "result ZIP"),
        (make_invalid_utf8_zip(), "not valid UTF-8"),
    ],
)
def test_mineru_parser_rejects_invalid_result_archive(
    tmp_path: Path,
    archive_bytes: bytes,
    message: str,
) -> None:
    """Reject corrupt ZIP results and non-UTF-8 Markdown."""
    source_path = tmp_path / "source.pdf"
    source_path.write_bytes(b"source")
    data_id = ""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal data_id
        if request.url.path == "/api/v4/file-urls/batch":
            data_id = json.loads(request.content)["files"][0]["data_id"]
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "batch_id": "batch-1",
                        "file_urls": ["https://upload.example/file"],
                    },
                },
                request=request,
            )
        if request.url.host == "upload.example":
            return httpx.Response(200, request=request)
        if request.url.path == "/api/v4/extract-results/batch/batch-1":
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "extract_result": [
                            {
                                "data_id": data_id,
                                "state": "done",
                                "full_zip_url": "https://download.example/result.zip",
                            }
                        ]
                    },
                },
                request=request,
            )
        return httpx.Response(200, content=archive_bytes, request=request)

    client = make_client(handler)
    parser = MineruParser("secret", transport=HttpxTransport(client), poll_interval=0)
    with pytest.raises(MineruParserError, match=message):
        parser.parse(source_path)
    client.close()


def test_parse_and_save_snapshot_rejects_missing_source(tmp_path: Path) -> None:
    """Reject a source hash that is not present in workspace storage."""
    workspace_root = init_workspace(tmp_path / "workspace")
    parser = MineruParser("secret")

    with pytest.raises(FileNotFoundError):
        parse_and_save_snapshot(
            workspace_root,
            "sha256:" + "a" * 64,
            parser,
        )


def test_parse_failure_does_not_create_snapshot(tmp_path: Path) -> None:
    """Do not persist a snapshot when the parser raises."""
    workspace_root = init_workspace(tmp_path / "workspace")
    staged_source = tmp_path / "source.pdf"
    staged_source.write_bytes(b"source")
    source_id = import_source(workspace_root, staged_source)

    class FailingParser:
        name = "mineru"
        version = "api-v4/vlm"

        def parse(self, source_path: Path) -> str:
            raise MineruParserError("parse failed")

    with pytest.raises(MineruParserError, match="parse failed"):
        parse_and_save_snapshot(workspace_root, source_id, FailingParser())

    digest = source_id.removeprefix("sha256:")
    assert not (workspace_root / ".memento" / "parses" / digest).exists()


def test_mineru_live_api_saves_workspace_snapshots(tmp_path: Path) -> None:
    """Exercise MinerU on the supplied documents only after explicit opt-in."""
    if os.getenv("MEMENTO_RUN_MINERU_INTEGRATION") != "1":
        pytest.skip("set MEMENTO_RUN_MINERU_INTEGRATION=1 to run MinerU integration")

    project_root = Path(__file__).resolve().parents[2]
    load_dotenv(project_root / ".env")
    api_key = os.getenv("MINERU_API_KEY")
    if not api_key:
        pytest.skip("MINERU_API_KEY is not configured")

    inbox = project_root / "scratch" / "datatest" / "inbox"
    workspace_root = find_workspace(inbox)
    source_paths = sorted(path for path in inbox.iterdir() if path.is_file())
    assert len(source_paths) == 3

    parser = MineruParser(api_key)
    for source_path in source_paths:
        staged_copy = tmp_path / source_path.name
        shutil.copy2(source_path, staged_copy)
        source_id = import_source(workspace_root, staged_copy)
        snapshot_dir = parse_and_save_snapshot(workspace_root, source_id, parser)
        snapshot = load_parse_snapshot(snapshot_dir)

        assert snapshot.metadata.source == source_id
        assert snapshot.metadata.parser == "mineru"
        assert snapshot.metadata.parser_version == parser.version
        assert (snapshot_dir / "content.md").stat().st_size > 0
