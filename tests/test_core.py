"""Tests for the minimal record checker and parser contract."""

from pathlib import Path
import shutil

import pytest
from pydantic import ValidationError

from mementoagent.cli import main
from mementoagent.schema import AchievementData, ParseMeta, ParsedBlock
from mementoagent.validation.shape import load_record_file


FIXTURES = Path(__file__).parent / "fixtures" / "workspaces"
RECORD_NAME = "ach_01JBX7Q3M8K2N5R9V4W6Y0ZDEF.toml"


def run_fixture(name: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> tuple[int, str, Path]:
    """Copy a fixture, run the CLI, and return result text and workspace."""
    workspace = tmp_path / name
    shutil.copytree(FIXTURES / name, workspace)
    record = workspace / "records" / "achievement" / RECORD_NAME
    status = main(["check", str(record)])
    return status, capsys.readouterr().out, record


def test_clean_document_record_passes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Accept a document record whose quote appears in its parse block."""
    status, output, _ = run_fixture("clean", tmp_path, capsys)
    assert status == 0
    assert output.strip() == "OK"


def test_quote_mismatch_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Reject a quote absent from the referenced block."""
    status, output, _ = run_fixture("quote_mismatch", tmp_path, capsys)
    assert status == 1
    assert "quote not found" in output


def test_user_record_without_evidence_passes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Allow user provenance without evidence."""
    status, output, _ = run_fixture("user_narration", tmp_path, capsys)
    assert status == 0
    assert output.strip() == "OK"


def test_malformed_toml_is_readable(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Report malformed TOML without exposing a traceback."""
    workspace = tmp_path / "workspace"
    (workspace / ".memento").mkdir(parents=True)
    record = workspace / "record.toml"
    record.write_text("id = [\n", encoding="utf-8")
    assert main(["check", str(record)]) == 1
    assert "Invalid TOML at line" in capsys.readouterr().out


def test_unquoted_datetime_is_rejected(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Reject TOML datetime values where the schema requires a string."""
    status, _, record = run_fixture("clean", tmp_path, capsys)
    assert status == 0
    record.write_text(record.read_text(encoding="utf-8").replace(
        'created_at = "2025-01-12T09:30:00+08:00"',
        "created_at = 2025-01-12T09:30:00+08:00",
    ), encoding="utf-8")
    assert main(["check", str(record)]) == 1
    assert "quote the timestamp" in capsys.readouterr().out


def test_body_after_table_is_rejected(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Reject top-level body content placed after a TOML table header."""
    status, _, record = run_fixture("clean", tmp_path, capsys)
    assert status == 0
    source = record.read_text(encoding="utf-8")
    body_start = source.index("body =")
    body_end = source.index("\n\n[occurred]")
    body = source[body_start:body_end]
    source = source[:body_start] + source[body_end + 2:]
    source = source.replace("[occurred]\n", "[occurred]\n" + body + "\n")
    record.write_text(source, encoding="utf-8")
    assert main(["check", str(record)]) == 1
    assert "top-level keys must precede table headers" in capsys.readouterr().out


def test_non_toml_path_is_rejected(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Reject paths that do not end in TOML."""
    assert main(["check", str(tmp_path / "record.md")]) == 1
    assert ".toml" in capsys.readouterr().out


@pytest.mark.parametrize(("field", "replacement", "message"), [
    ("source", "sha256:" + "0" * 64, "source not found"),
    ("parse", "p_missing", "parse snapshot not found"),
    ("block", "p0-missing", "block not found"),
])
def test_missing_evidence_reference_fails(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    field: str,
    replacement: str,
    message: str,
) -> None:
    """Report missing source, parse, and block references."""
    status, _, record = run_fixture("clean", tmp_path, capsys)
    assert status == 0
    source = record.read_text(encoding="utf-8")
    import re

    record.write_text(re.sub(rf'^{field} = .*$', f'{field} = "{replacement}"', source, flags=re.MULTILINE), encoding="utf-8")
    assert main(["check", str(record)]) == 1
    assert message in capsys.readouterr().out


def test_strict_record_model_rejects_extra_fields() -> None:
    """Reject fields outside the declared achievement shape."""
    with pytest.raises(ValidationError):
        AchievementData.model_validate({
            "kind": "award", "title": "t", "issuer": "i", "level_raw": "l", "extra": True,
        })


def test_parser_models_allow_nullable_geometry_and_confidence() -> None:
    """Accept normalized blocks with absent geometry and confidence."""
    meta = ParseMeta(
        parse_id="p1", source="sha256:" + "a" * 64, engine="future",
        version="1", parsed_at="2025-01-12T09:30:00+08:00",
    )
    block = ParsedBlock(id="b1", page=0, bbox=None, type="text", text="text", conf=None)
    assert meta.engine == "future"
    assert block.bbox is None and block.conf is None
