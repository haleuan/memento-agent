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
