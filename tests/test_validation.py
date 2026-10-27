"""Golden integration tests for adversarial workspace scenarios."""

from pathlib import Path
import shutil

import pytest
from typer.testing import CliRunner

from mementoagent.cli import app

FIXTURES = Path(__file__).parent / "fixtures" / "workspaces"
SCENARIOS = (
    "clean_award",
    "quote_mismatch",
    "tampered_seal",
    "duplicate_source",
    "agent_inference",
    "user_narration",
)


def test_clean_achievement_seal_is_pinned() -> None:
    """Pin the canonical seal for the clean achievement fixture."""
    from mementoagent.validation.shape import load_record_file
    from mementoagent.validation.seal import compute_seal

    record_path = next((FIXTURES / "clean_award" / "records").rglob("*.toml"))
    assert compute_seal(load_record_file(record_path).record) == (
        "sha256:1fe2c60053cb829d75a74f2472450abcc6eea8e7342bc5b8c55775e1cf193cad"
    )


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_workspace_golden(scenario, tmp_path, monkeypatch):
    """Match CLI output and exit status to the selected workspace golden."""
    workspace = tmp_path / scenario
    shutil.copytree(FIXTURES / scenario, workspace)
    monkeypatch.chdir(workspace)
    record = next((workspace / "records").rglob("*.toml"))
    before = {
        path.relative_to(workspace): path.read_bytes()
        for path in workspace.rglob("*")
        if path.is_file()
    }

    result = CliRunner().invoke(app, ["check", str(record.relative_to(workspace))])

    assert result.output == (workspace / "expected.txt").read_text(encoding="utf-8")
    assert result.exit_code == int((workspace / "expected_exit_code.txt").read_text())
    after = {
        path.relative_to(workspace): path.read_bytes()
        for path in workspace.rglob("*")
        if path.is_file()
    }
    assert after == before
