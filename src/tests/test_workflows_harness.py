"""Tests for the TUI-neutral Memento Agent harness."""

from pathlib import Path
from typing import Any

import pytest

from mementoagent.capabilities.achievement import AchievementExtraction
from mementoagent.schema import AchievementItem
from mementoagent.workflows import MementoAgent
from mementoagent.workspace import init_workspace, load_record


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
