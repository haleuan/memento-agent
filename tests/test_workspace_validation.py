"""Adversarial tests for workspace and provenance invariants."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from mementoagent.schema import AchievementData, RecordEnvelope, Verification
from mementoagent.validation import (
    RecordLoadError,
    canonical_critical_fields,
    compute_seal,
    load_record_file,
    validate_record,
)
from mementoagent.workspace import (
    WorkspaceNotFoundError,
    WorkspacePaths,
    clear_workspace_cache,
    find_workspace,
    load_workspace_config,
    write_workspace_config,
)


TIMESTAMP = "2025-01-12T09:30:00+08:00"


def record_payload() -> dict:
    """Build a valid user-asserted record payload."""
    return {
        "id": "ach_01JBX7Q3M8K2N5R9V4W6Y0ZDEF",
        "schema": "achievement/1",
        "provenance": "user",
        "created_at": TIMESTAMP,
        "occurred": {"start": "2024-10", "end": "2024-10"},
        "data": {"kind": "award", "title": "竞赛", "issuer": "组委会", "level_raw": "二等奖"},
        "evidence": [],
        "verification": None,
    }


def as_record(payload: dict) -> RecordEnvelope[AchievementData]:
    """Validate a mapping as a typed achievement record."""
    return RecordEnvelope[AchievementData].model_validate(payload)


@pytest.fixture
def grounded_record(tmp_path: Path) -> tuple[RecordEnvelope[AchievementData], WorkspacePaths]:
    """Build a record grounded by a source block."""
    text = "授予\n 张三同学 二等奖"
    source_bytes = text.encode("utf-8")
    digest = hashlib.sha256(source_bytes).hexdigest()
    source = "sha256:" + digest
    paths = WorkspacePaths(tmp_path)
    paths.source_dir(source).mkdir(parents=True)
    (paths.source_dir(source) / f"{digest}.txt").write_bytes(source_bytes)
    (paths.source_dir(source) / f"{digest}.json").write_text(json.dumps({
        "hash": source, "original_filename": "certificate.txt", "imported_at": TIMESTAMP,
        "mime_type": "text/plain", "size_bytes": len(source_bytes), "origin": "inbox", "sensitive": False,
    }), encoding="utf-8")
    parse_dir = paths.parse_dir(source, "p_test")
    parse_dir.mkdir(parents=True)
    (parse_dir / "meta.json").write_text(json.dumps({
        "parse_id": "p_test", "source": source, "engine": "test", "version": "1",
        "params": {}, "parsed_at": TIMESTAMP, "remote": False,
    }), encoding="utf-8")
    (parse_dir / "blocks.jsonl").write_text(json.dumps({
        "id": "p0-b0", "page": 0, "bbox": [0.0, 0.0, 1.0, 1.0], "type": "text", "text": text,
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    payload = record_payload()
    payload["provenance"] = "document"
    payload["evidence"] = [{
        "source": source, "parse": "p_test", "block": "p0-b0", "supports": ["data.level_raw"],
        "quote": "授予 张三同学\t二等奖",
    }]
    return as_record(payload), paths


def test_discovery_finds_nearest_workspace_and_reports_absence(tmp_path: Path) -> None:
    """Verify that discovery finds nearest workspace and reports absence."""
    clear_workspace_cache()
    with pytest.raises(WorkspaceNotFoundError, match=r"Not in a memento workspace"):
        find_workspace(tmp_path)
    (tmp_path / ".memento").mkdir()
    nested = tmp_path / "nested" / "child"
    nested.mkdir(parents=True)
    assert find_workspace(nested) == tmp_path
    (tmp_path / "nested" / ".memento").mkdir()
    clear_workspace_cache()
    assert find_workspace(nested) == tmp_path / "nested"


@pytest.mark.parametrize("parse_id", ["..", ".", "../parse", "/parse", "a\\b"])
def test_parse_paths_cannot_escape_workspace(tmp_path: Path, parse_id: str) -> None:
    """Verify that parse paths cannot escape workspace."""
    with pytest.raises(ValueError):
        WorkspacePaths(tmp_path).parse_dir("sha256:" + "a" * 64, parse_id)


def test_full_workspace_config_round_trip(tmp_path: Path) -> None:
    """Round-trip workspace configuration deterministically."""
    config = {
        "schema": "envelope/1",
        "z_last": "line one\nline two\tquoted \"value\"",
        "parse": {"engine": "mineru", "tier": "standard", "language": "ch", "remote": {
            "enabled": True, "api_url": "https://example.test/api",
        }},
    }
    path = write_workspace_config(tmp_path, config)
    before = path.read_bytes()
    assert load_workspace_config(tmp_path) == config
    write_workspace_config(tmp_path, dict(reversed(list(config.items()))))
    assert path.read_bytes() == before


def test_toml_load_preserves_body_and_dispatches_schema(tmp_path: Path) -> None:
    """Preserve the TOML body and dispatch the achievement schema."""
    path = tmp_path / "record.toml"
    path.write_text('''id = "ach_01JBX7Q3M8K2N5R9V4W6Y0ZDEF"
schema = "achievement/1"
provenance = "user"
created_at = "2025-01-12T09:30:00+08:00"
body = """# Narrative
self-reported"""

[occurred]
start = "2024-10"
end = "2024-10"

[data]
kind = "award"
title = "竞赛"
issuer = "组委会"
level_raw = "二等奖"
''', encoding="utf-8")
    loaded = load_record_file(path)
    assert isinstance(loaded.record.data, AchievementData)
    assert loaded.body == "# Narrative\nself-reported"


@pytest.mark.parametrize("text", ["id = [\n", 'schema = "other/1"\n'])
def test_invalid_toml_is_a_shape_error(tmp_path: Path, text: str) -> None:
    """Reject malformed TOML and unsupported schema versions."""
    path = tmp_path / "record.toml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(RecordLoadError):
        load_record_file(path)


def test_seal_matches_fixed_unicode_vector() -> None:
    """Match the fixed UTF-8 seal vector and ignore envelope metadata."""
    record = as_record(record_payload())
    canonical = canonical_critical_fields(record)
    expected = (
        '{"data":{"issuer":"组委会","kind":"award","level_raw":"二等奖","notes":null,"title":"竞赛"},'
        '"evidence":[],"occurred":{"end":"2024-10","start":"2024-10"}}'
    ).encode("utf-8")
    assert canonical == expected
    seal = compute_seal(record)
    assert seal == "sha256:bb4a19f5ee989213d5ad8476f964d774269de05562011435fb0a948244917e32"
    # Key order and Markdown metadata are not critical fields.
    reordered = dict(reversed(list(record.model_dump(mode="json", by_alias=True).items())))
    reordered["created_at"] = "2025-01-13T09:30:00+08:00"
    assert compute_seal(reordered) == seal


def test_evidence_array_order_changes_the_seal(grounded_record) -> None:
    """Verify that evidence array order changes the seal."""
    record, _ = grounded_record
    second = record.evidence[0].model_copy(update={"quote": "二等奖"})
    record.evidence.append(second)
    before = compute_seal(record)
    record.evidence.reverse()
    assert compute_seal(record) != before


@pytest.mark.parametrize("field", ["data", "occurred", "evidence"])
def test_every_critical_field_changes_the_seal(grounded_record, field: str) -> None:
    """Verify that every critical field changes the seal."""
    record, _ = grounded_record
    before = compute_seal(record)
    if field == "data":
        record.data.level_raw = "一等奖"
    elif field == "occurred":
        record.occurred.start = "2024-09"
    else:
        record.evidence[0].quote = "二等奖"
    assert compute_seal(record) != before


def test_grounding_accepts_whitespace_and_human_seal(grounded_record) -> None:
    """Match whitespace-normalized quotes and accept an intact human seal."""
    record, paths = grounded_record
    assert "quote_mismatch" not in {issue.code for issue in validate_record(record, paths).issues}
    record.verification = Verification(by="human", at=TIMESTAMP, sealed=compute_seal(record))
    result = validate_record(record, paths)
    assert result.status == "verified"
    assert result.exit_code == 0


@pytest.mark.parametrize("missing", ["source", "parse", "block"])
def test_missing_evidence_references_are_errors(grounded_record, missing: str) -> None:
    """Report missing source, parse, and block references as errors."""
    record, paths = grounded_record
    record.verification = Verification(by="human", at=TIMESTAMP, sealed=compute_seal(record))
    evidence = record.evidence[0]
    if missing == "source":
        paths.source_path(evidence.source).unlink()
    elif missing == "parse":
        paths.blocks_path(evidence.source, evidence.parse).unlink()
    else:
        paths.blocks_path(evidence.source, evidence.parse).write_text("", encoding="utf-8")
    result = validate_record(record, paths)
    assert result.exit_code == 1
    # Missing files never become verified, even when the record seal is intact.
    assert result.status == "draft"
    assert f"missing_{missing}" in {issue.code for issue in result.issues}


def test_hallucinated_quote_and_unknown_support_are_rejected(grounded_record) -> None:
    """Reject unsupported quotes and invalid evidence field paths."""
    record, paths = grounded_record
    record.evidence[0].quote = "一等奖"
    record.evidence[0].supports = ["data.invented_field"]
    codes = {issue.code for issue in validate_record(record, paths).issues}
    assert {"quote_mismatch", "shape"} <= codes


def test_duplicate_source_warning_is_read_only(grounded_record) -> None:
    """Warn about duplicate source content without modifying workspace files."""
    record, paths = grounded_record
    original = paths.source_path(record.evidence[0].source)
    copy = original.with_name("renamed-import.txt")
    copy.write_bytes(original.read_bytes())
    before = {path: path.read_bytes() for path in paths.root.rglob("*") if path.is_file()}
    result = validate_record(record, paths)
    assert "duplicate_source" in {issue.code for issue in result.issues}
    assert {path: path.read_bytes() for path in paths.root.rglob("*") if path.is_file()} == before


def test_canonical_source_and_single_sidecar_are_not_duplicates(grounded_record) -> None:
    """Ignore the expected source file and its single metadata sidecar."""
    record, paths = grounded_record
    assert "duplicate_source" not in {issue.code for issue in validate_record(record, paths).issues}


def test_duplicate_sidecar_identity_warns_without_duplicate_source_bytes(grounded_record) -> None:
    """Warn about duplicate sidecar identities without changing workspace files."""
    record, paths = grounded_record
    source = record.evidence[0].source
    digest = source.removeprefix("sha256:")
    original = paths.source_dir(source) / f"{digest}.json"
    duplicate = original.with_name("legacy-import.json")
    duplicate.write_bytes(original.read_bytes())
    before = {path: path.read_bytes() for path in paths.root.rglob("*") if path.is_file()}
    duplicates = [issue for issue in validate_record(record, paths).issues if issue.code == "duplicate_source"]
    names = sorted([original.relative_to(paths.root).as_posix(), duplicate.relative_to(paths.root).as_posix()])
    assert len(duplicates) == 1
    assert duplicates[0].severity == "WARN"
    assert duplicates[0].message == "duplicate source metadata: " + ", ".join(names)
    assert {path: path.read_bytes() for path in paths.root.rglob("*") if path.is_file()} == before


def test_agent_can_only_be_verified_by_human_seal(tmp_path: Path) -> None:
    """Require a human seal to verify agent records and detect tampering."""
    payload = record_payload()
    payload["provenance"] = "agent"
    record = as_record(payload)
    assert validate_record(record, tmp_path).status == "draft"
    record.verification = Verification(by="human", at=TIMESTAMP, sealed=compute_seal(record))
    assert validate_record(record, tmp_path).status == "verified"
    record.data.title = "changed"
    result = validate_record(record, tmp_path)
    assert result.status == "tampered"
    assert result.exit_code == 1


@pytest.mark.parametrize("sealed", [False, True])
def test_document_without_evidence_cannot_be_verified(tmp_path: Path, sealed: bool) -> None:
    """Keep document records unverified when evidence is absent."""
    payload = record_payload()
    payload["provenance"] = "document"
    record = as_record(payload)
    if sealed:
        record.verification = Verification(by="human", at=TIMESTAMP, sealed=compute_seal(record))

    result = validate_record(record, tmp_path)

    assert result.status == "draft"
    assert result.exit_code == 1
    assert "missing_evidence" in {issue.code for issue in result.issues}
