"""Tests for the TUI-neutral Memento Agent harness."""

from pathlib import Path
from typing import Any

import pytest

from mementoagent.capabilities.achievement import AchievementExtraction
from mementoagent.schema import (
    AchievementItem,
    PartialDate,
    RecordEnvelope,
)
from mementoagent.schema.envelope import TimeRange
from mementoagent.workflows import MementoAgent
from mementoagent.workflows.tools import MementoContext, MementoToolset
from mementoagent.workspace import init_workspace, load_record, save_record


class FakeParser:
    """Return deterministic Markdown for one source file."""

    name = "fake"
    version = "1"

    def parse(self, source_path: Path) -> str:
        """Return content without exposing the source body to the test."""
        assert source_path.is_file()
        return "Certificate title\nExample University\n"


class FakeRuntime:
    """Execute extraction while leaving conversation execution to the test."""

    def run(self, task: Any, value: Any, *, context: object | None = None) -> Any:
        """Return one structured achievement extraction."""
        assert task.name == "achievement_extraction"
        assert value.content.startswith("Certificate title")
        return AchievementExtraction(
            data=AchievementItem(
                kind="certificate",
                title="Certificate of Completion",
                organization=None,
            )
        )


def get_tool(agent: MementoAgent, name: str) -> Any:
    """Return one named tool from the application Agent."""
    return next(tool for tool in agent.tools() if tool.name == name)


def test_memento_tools_prepare_extract_and_save(tmp_path: Path) -> None:
    """Compose semantic tools without a fixed Python pipeline."""
    workspace_root = init_workspace(tmp_path / "workspace")
    source_path = workspace_root / "inbox" / "certificate.pdf"
    source_path.write_bytes(b"certificate")
    agent = MementoAgent(workspace_root, FakeParser(), FakeRuntime())  # type: ignore[arg-type]
    context = agent._session.context  # type: ignore[attr-defined]

    prepare = get_tool(agent, "prepare_source")
    prepared = prepare.handler(
        prepare.parameters(filename="certificate.pdf"),
        context,
    )
    assert prepared["parser"] == "fake"

    extract = get_tool(agent, "extract_achievement")
    extracted = extract.handler(extract.parameters(), context)
    assert extracted["data"]["title"] == "Certificate of Completion"

    save = get_tool(agent, "save_achievement")
    data = AchievementItem.model_validate(extracted["data"])
    data = data.model_copy(update={"description": "Completed the program."})
    record_path = save.handler(save.parameters(data=data), context)

    record = load_record(Path(record_path), AchievementItem)
    assert record.data.description == "Completed the program."
    assert record.provenance == "document"
    assert record.evidence[0].supports == []


def test_prepare_source_rejects_path_traversal(tmp_path: Path) -> None:
    """Do not let the Agent tool read outside the workspace inbox."""
    workspace_root = init_workspace(tmp_path / "workspace")
    agent = MementoAgent(workspace_root, FakeParser(), FakeRuntime())  # type: ignore[arg-type]
    prepare = get_tool(agent, "prepare_source")

    with pytest.raises(ValueError, match="relative"):
        prepare.handler(
            prepare.parameters(filename="../secret.pdf"),
            agent._session.context,  # type: ignore[attr-defined]
        )


def test_toolset_uses_runtime_context_and_isolated_sessions(tmp_path: Path) -> None:
    """Use the context supplied by the Runtime for each tool invocation."""
    first_root = init_workspace(tmp_path / "first")
    second_root = init_workspace(tmp_path / "second")
    (first_root / "inbox" / "first.pdf").write_bytes(b"first")
    (second_root / "inbox" / "second.pdf").write_bytes(b"second")

    first_agent = MementoAgent(first_root, FakeParser(), FakeRuntime())  # type: ignore[arg-type]
    second_agent = MementoAgent(second_root, FakeParser(), FakeRuntime())  # type: ignore[arg-type]
    first_context = first_agent._session.context  # type: ignore[attr-defined]
    second_context = second_agent._session.context  # type: ignore[attr-defined]
    assert isinstance(first_context, MementoContext)
    assert isinstance(second_context, MementoContext)
    assert first_context is not second_context
    list_tool = next(
        tool for tool in MementoToolset().specs() if tool.name == "list_inbox"
    )

    assert list_tool.handler(list_tool.parameters(), first_context) == ["first.pdf"]
    assert list_tool.handler(list_tool.parameters(), second_context) == ["second.pdf"]


def test_toolset_rejects_missing_runtime_context() -> None:
    """Require the Memento session context at the tool boundary."""
    list_tool = next(
        tool for tool in MementoToolset().specs() if tool.name == "list_inbox"
    )

    with pytest.raises(TypeError, match="MementoContext"):
        list_tool.handler(list_tool.parameters(), None)


def test_list_records_returns_empty_list_for_new_workspace(tmp_path: Path) -> None:
    """Return no records without creating workspace files."""
    workspace_root = init_workspace(tmp_path / "workspace")
    agent = MementoAgent(workspace_root, FakeParser(), FakeRuntime())  # type: ignore[arg-type]
    list_records = get_tool(agent, "list_records")

    before = sorted(
        path.relative_to(workspace_root) for path in workspace_root.rglob("*")
    )
    result = list_records.handler(
        list_records.parameters(),
        agent._session.context,  # type: ignore[attr-defined]
    )

    assert result == []
    assert before == sorted(
        path.relative_to(workspace_root) for path in workspace_root.rglob("*")
    )


def test_list_records_returns_metadata_and_achievement_summary(
    tmp_path: Path,
) -> None:
    """Summarize known achievement fields while preserving time metadata."""
    workspace_root = init_workspace(tmp_path / "workspace")
    record = RecordEnvelope[AchievementItem](
        id="ach_01JBX7Q3M8K2N5R9V4W6Y0ZDEF",
        schema="achievement/1",
        provenance="document",
        created_at="2025-01-12T09:30:00+08:00",
        occurred=TimeRange(start=PartialDate(year=2024, month=10, precision="month")),
        data=AchievementItem(
            kind="award",
            title="First Prize",
            organization="Example University",
        ),
    )
    save_record(workspace_root, record)
    agent = MementoAgent(workspace_root, FakeParser(), FakeRuntime())  # type: ignore[arg-type]
    list_records = get_tool(agent, "list_records")

    result = list_records.handler(
        list_records.parameters(),
        agent._session.context,  # type: ignore[attr-defined]
    )

    assert result == [
        {
            "id": record.id,
            "schema": "achievement/1",
            "provenance": "document",
            "created_at": record.created_at,
            "occurred": {"start": {"year": 2024, "month": 10, "precision": "month"}},
            "path": f"records/achievement/{record.id}.toml",
            "summary": {
                "title": "First Prize",
                "kind": "award",
                "organization": "Example University",
            },
        }
    ]


def test_unknown_schema_record_is_listed_and_loaded_as_raw_toml(
    tmp_path: Path,
) -> None:
    """Read an unsupported record schema without payload validation."""
    workspace_root = init_workspace(tmp_path / "workspace")
    record_id = "note_01JBX7Q3M8K2N5R9V4W6Y0ZDEF"
    path = workspace_root / "records" / "note" / f"{record_id}.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'id = "{record_id}"\n'
        'schema = "note/1"\n'
        'provenance = "user"\n'
        'created_at = "2025-01-12T09:30:00+08:00"\n\n'
        "[data]\n"
        'title = "A note"\n'
        'arbitrary = "value"\n',
        encoding="utf-8",
    )
    agent = MementoAgent(workspace_root, FakeParser(), FakeRuntime())  # type: ignore[arg-type]
    list_records = get_tool(agent, "list_records")
    get_record = get_tool(agent, "get_record")
    context = agent._session.context  # type: ignore[attr-defined]

    summaries = list_records.handler(list_records.parameters(), context)
    loaded = get_record.handler(get_record.parameters(record_id=record_id), context)

    assert summaries[0]["summary"] == {"title": "A note"}
    assert loaded["data"] == {"title": "A note", "arbitrary": "value"}


def test_get_record_rejects_missing_and_invalid_ids(tmp_path: Path) -> None:
    """Reject missing records and path-like identifiers."""
    workspace_root = init_workspace(tmp_path / "workspace")
    agent = MementoAgent(workspace_root, FakeParser(), FakeRuntime())  # type: ignore[arg-type]
    get_record = get_tool(agent, "get_record")
    context = agent._session.context  # type: ignore[attr-defined]

    with pytest.raises(ValueError):
        get_record.parameters(record_id="../secret")
    with pytest.raises(FileNotFoundError):
        get_record.handler(
            get_record.parameters(record_id="note_01JBX7Q3M8K2N5R9V4W6Y0ZDEF"),
            context,
        )


def test_list_records_rejects_malformed_toml(tmp_path: Path) -> None:
    """Do not silently ignore a malformed record file."""
    workspace_root = init_workspace(tmp_path / "workspace")
    path = workspace_root / "records" / "note" / "note_invalid.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("id = [", encoding="utf-8")
    agent = MementoAgent(workspace_root, FakeParser(), FakeRuntime())  # type: ignore[arg-type]
    list_records = get_tool(agent, "list_records")

    with pytest.raises(ValueError, match="invalid TOML record"):
        list_records.handler(
            list_records.parameters(),
            agent._session.context,  # type: ignore[attr-defined]
        )
