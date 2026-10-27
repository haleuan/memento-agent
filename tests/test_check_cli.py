"""CLI error handling and console entrypoint coverage."""

from importlib.metadata import distribution
from pathlib import Path
import shutil

import pytest
from typer.testing import CliRunner

from mementoagent.cli import app

FIXTURES = Path(__file__).parent / "fixtures" / "workspaces"


def test_console_entrypoints():
    """Expose both supported console script names."""
    commands = {
        entry.name: entry.value
        for entry in distribution("memento-agent").entry_points
        if entry.group == "console_scripts"
    }
    assert commands["memento"] == "mementoagent.cli:main"
    assert commands["mementoagent"] == "mementoagent.cli:main"


def test_record_workspace_discovery_independent_of_cwd(tmp_path, monkeypatch):
    """Discover a record's workspace without relying on the current directory."""
    workspace = tmp_path / "workspace"
    shutil.copytree(FIXTURES / "clean_award", workspace)
    record = next((workspace / "records").rglob("*.toml"))
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, ["check", str(record)])
    assert result.exit_code == 0
    assert result.output.startswith("Status: verified\n")


def test_missing_workspace(tmp_path):
    """Report an error when the record is outside a workspace."""
    record = tmp_path / "record.toml"
    record.write_text("not a workspace", encoding="utf-8")
    result = CliRunner().invoke(app, ["check", str(record)])
    assert result.exit_code == 1
    assert "Not in a memento workspace (no .memento/ found)" in result.output
    assert "Traceback" not in result.output


def test_missing_record(tmp_path):
    """Report an error when the requested record does not exist."""
    (tmp_path / ".memento").mkdir()
    result = CliRunner().invoke(app, ["check", str(tmp_path / "missing.toml")])
    assert result.exit_code == 1
    assert "[ERROR] shape:" in result.output
    assert "Traceback" not in result.output


def test_malformed_toml(tmp_path):
    """Report malformed TOML without a traceback."""
    (tmp_path / ".memento").mkdir()
    record = tmp_path / "record.toml"
    record.write_text("id = [\n", encoding="utf-8")
    result = CliRunner().invoke(app, ["check", str(record)])
    assert result.exit_code == 1
    assert "[ERROR] toml_syntax:" in result.output
    assert "Traceback" not in result.output


def test_unknown_schema(tmp_path):
    """Reject record schema versions that the loader does not support."""
    (tmp_path / ".memento").mkdir()
    record = tmp_path / "record.toml"
    record.write_text('schema = "achievement/99"\n', encoding="utf-8")
    result = CliRunner().invoke(app, ["check", str(record)])
    assert result.exit_code == 1
    assert "[ERROR] shape:" in result.output
    assert "achievement/99" in result.output


@pytest.mark.parametrize("original,replacement,field", [
    (
        'created_at = "2025-01-12T09:30:00+08:00"',
        'created_at = 2025-01-12T09:30:00+08:00',
        "created_at",
    ),
    (
        'start = "2024-10"',
        'start = 2024-10-01',
        "occurred.start",
    ),
])
def test_unquoted_toml_dates_are_rejected(tmp_path, original, replacement, field):
    """Reject TOML date coercion and require timestamps to be quoted."""
    workspace = tmp_path / "workspace"
    shutil.copytree(FIXTURES / "clean_award", workspace)
    record = next((workspace / "records").rglob("*.toml"))
    record.write_text(record.read_text(encoding="utf-8").replace(original, replacement), encoding="utf-8")

    result = CliRunner().invoke(app, ["check", str(record)])

    assert result.exit_code == 1
    assert "[ERROR] toml_syntax:" in result.output or f"[ERROR] shape: {field}:" in result.output


def test_duplicate_toml_keys_do_not_silently_override_facts(tmp_path):
    """Reject duplicate TOML keys instead of silently overriding facts."""
    workspace = tmp_path / "workspace"
    shutil.copytree(FIXTURES / "clean_award", workspace)
    record = next((workspace / "records").rglob("*.toml"))
    record.write_text(
        record.read_text(encoding="utf-8").replace(
            'provenance = "document"', 'provenance = "document"\nprovenance = "user"'
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["check", str(record)])

    assert result.exit_code == 1
    assert "[ERROR] toml_syntax: Invalid TOML" in result.output


def test_non_toml_record_path_is_rejected(tmp_path):
    """Reject record paths that do not use the TOML extension."""
    (tmp_path / ".memento").mkdir()
    record = tmp_path / "record.md"
    record.write_text("", encoding="utf-8")
    result = CliRunner().invoke(app, ["check", str(record)])
    assert result.exit_code == 1
    assert "Record path must end with .toml" in result.output


def test_body_after_table_is_rejected(tmp_path):
    """Reject misplaced top-level body keys after a TOML table header."""
    workspace = tmp_path / "workspace"
    shutil.copytree(FIXTURES / "clean_award", workspace)
    record = next((workspace / "records").rglob("*.toml"))
    record.write_text(record.read_text(encoding="utf-8").replace(
        'body = \'\'\'\n\n用户自己的补充描述，不参与验证封印。\n\'\'\'\n\n', ""), encoding="utf-8")
    record.write_text(record.read_text(encoding="utf-8").replace(
        '[occurred]\n', '[occurred]\nbody = "misplaced"\n'), encoding="utf-8")
    result = CliRunner().invoke(app, ["check", str(record)])
    assert result.exit_code == 1
    assert "shape:" in result.output
    assert "top-level keys must precede table headers" in result.output


def test_absent_verification_and_occurred_default_to_null(tmp_path):
    """Load absent optional tables as null values in the typed record."""
    from mementoagent.validation.shape import load_record_file

    workspace = tmp_path / "workspace"
    shutil.copytree(FIXTURES / "user_narration", workspace)
    record = next((workspace / "records").rglob("*.toml"))
    content = record.read_text(encoding="utf-8")
    content = content.replace('[occurred]\nstart = "2024-10"\nend = "2024-10"\n\n', "")
    record.write_text(content, encoding="utf-8")
    loaded = load_record_file(record)
    assert loaded.record.occurred is None
    assert loaded.record.verification is None
