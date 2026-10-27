"""Cross-file provenance checks. Every operation in this module is read-only."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from mementoagent.schema import (
    AchievementData,
    ParsedBlock,
    ParseMeta,
    RecordEnvelope,
    SourceMetadata,
)
from mementoagent.workspace import WorkspacePaths

from .seal import verify_seal


@dataclass(frozen=True)
class Issue:
    """One stable validation diagnostic."""

    severity: Literal["ERROR", "WARN", "INFO"]
    code: str
    message: str


@dataclass(frozen=True)
class CheckResult:
    """Validation status and diagnostics for one record."""

    status: Literal["draft", "verified", "tampered"]
    issues: list[Issue]

    @property
    def exit_code(self) -> int:
        """Return the CLI exit code corresponding to this result."""
        if any(issue.severity == "ERROR" for issue in self.issues):
            return 1
        if self.status != "verified" or any(
            issue.severity == "WARN" for issue in self.issues
        ):
            return 2
        return 0


def normalize_whitespace(value: str) -> str:
    """Collapse runs of whitespace to a single space.

    Args:
        value: Text to normalize.

    Returns:
        Text with leading, trailing, and repeated whitespace removed.
    """
    return " ".join(value.split())


def _shape_issue(context: str, exc: Exception) -> Issue:
    """Convert a parse or schema exception to a shape diagnostic.

    Args:
        context: Location being validated.
        exc: Exception raised during parsing or validation.

    Returns:
        An error issue with a readable detail message.
    """
    if isinstance(exc, ValidationError):
        detail = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors(include_url=False)
        )
    else:
        detail = str(exc)
    return Issue("ERROR", "shape", f"{context}: {detail}")


def _check_evidence(
    record: RecordEnvelope[AchievementData], paths: WorkspacePaths
) -> list[Issue]:
    """Validate evidence references, quotes, and supported field paths.

    Args:
        record: Typed record whose evidence should be checked.
        paths: Workspace paths used to resolve source and parse files.

    Returns:
        Errors found while checking the record's evidence.
    """
    issues: list[Issue] = []
    for index, evidence in enumerate(record.evidence):
        context = f"evidence[{index}]"
        source_path = paths.source_path(evidence.source)
        if source_path is None or not source_path.is_file():
            issues.append(
                Issue(
                    "ERROR",
                    "missing_source",
                    f"{context}.source not found: {evidence.source}",
                )
            )
        else:
            metadata_path = (
                paths.source_dir(evidence.source)
                / f"{evidence.source.removeprefix('sha256:')}.json"
            )
            if not metadata_path.is_file():
                issues.append(
                    Issue(
                        "ERROR",
                        "missing_source",
                        f"{context}.source metadata not found",
                    )
                )
            else:
                try:
                    metadata = SourceMetadata.model_validate_json(
                        metadata_path.read_text(encoding="utf-8")
                    )
                    if metadata.hash != evidence.source:
                        issues.append(
                            Issue(
                                "ERROR",
                                "shape",
                                f"{context}.source metadata hash differs from reference",
                            )
                        )
                except (OSError, UnicodeError, ValidationError) as exc:
                    issues.append(_shape_issue(f"{context}.source metadata", exc))
        try:
            parse_dir = paths.parse_dir(evidence.source, evidence.parse)
        except ValueError as exc:
            issues.append(_shape_issue(f"{context}.parse", exc))
            continue
        blocks_path = parse_dir / "blocks.jsonl"
        metadata_path = parse_dir / "meta.json"
        if (
            not parse_dir.is_dir()
            or not blocks_path.is_file()
            or not metadata_path.is_file()
        ):
            issues.append(
                Issue(
                    "ERROR",
                    "missing_parse",
                    f"{context}.parse not found: {evidence.parse}",
                )
            )
            continue
        try:
            meta = ParseMeta.model_validate_json(
                metadata_path.read_text(encoding="utf-8")
            )
            if meta.source != evidence.source or meta.parse_id != evidence.parse:
                issues.append(
                    Issue(
                        "ERROR",
                        "shape",
                        f"{context}.parse metadata differs from reference",
                    )
                )
            blocks: dict[str, ParsedBlock] = {}
            with blocks_path.open(encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    block = ParsedBlock.model_validate_json(line)
                    if block.id in blocks:
                        issues.append(
                            Issue(
                                "ERROR",
                                "shape",
                                f"{context}.parse contains duplicate block ID {block.id}",
                            )
                        )
                    blocks[block.id] = block
        except (OSError, UnicodeError, ValidationError) as exc:
            issues.append(_shape_issue(f"{context}.parse", exc))
            continue
        block = blocks.get(evidence.block)
        if block is None:
            issues.append(
                Issue(
                    "ERROR",
                    "missing_block",
                    f"{context}.block not found: {evidence.block}",
                )
            )
        elif normalize_whitespace(evidence.quote) not in normalize_whitespace(
            block.text
        ):
            issues.append(
                Issue(
                    "ERROR",
                    "quote_mismatch",
                    f"{context}.quote not found in block text",
                )
            )
        payload = record.model_dump(mode="json", by_alias=True)
        for support in evidence.supports:
            if not (
                support.startswith("data.")
                or support in {"occurred", "occurred.start", "occurred.end"}
            ):
                issues.append(
                    Issue(
                        "ERROR",
                        "shape",
                        f"{context}.supports references unknown field: {support}",
                    )
                )
                continue
            target = payload
            found = True
            for part in support.split("."):
                if not isinstance(target, dict) or part not in target:
                    found = False
                    break
                target = target[part]
            if not found:
                issues.append(
                    Issue(
                        "ERROR",
                        "shape",
                        f"{context}.supports references unknown field: {support}",
                    )
                )
    return issues


def _duplicate_sources(paths: WorkspacePaths) -> list[Issue]:
    """Detect repeated source bytes or sidecar identities in legacy imports."""
    groups: dict[str, list[str]] = defaultdict(list)
    metadata_groups: dict[str, list[str]] = defaultdict(list)
    if not paths.sources.is_dir():
        return []
    for source_path in sorted(paths.sources.rglob("*")):
        if not source_path.is_file():
            continue
        if source_path.suffix == ".json":
            try:
                metadata = SourceMetadata.model_validate_json(
                    source_path.read_text(encoding="utf-8")
                )
            except (OSError, UnicodeError, ValidationError):
                continue
            metadata_groups[metadata.hash].append(
                source_path.relative_to(paths.root).as_posix()
            )
            continue
        try:
            with source_path.open("rb") as handle:
                digest = hashlib.file_digest(handle, "sha256").hexdigest()
        except OSError:
            continue
        groups[digest].append(source_path.relative_to(paths.root).as_posix())
    issues = [
        Issue(
            "WARN", "duplicate_source", f"identical source content: {', '.join(names)}"
        )
        for _, names in sorted(groups.items())
        if len(names) > 1
    ]
    issues.extend(
        Issue(
            "WARN", "duplicate_source", f"duplicate source metadata: {', '.join(names)}"
        )
        for _, names in sorted(metadata_groups.items())
        if len(names) > 1
    )
    return issues


def validate_record(
    record: RecordEnvelope[AchievementData], workspace: Path | str | WorkspacePaths
) -> CheckResult:
    """Check record invariants and its verification seal.

    Args:
        record: Typed achievement record to validate.
        workspace: Workspace root or its path helper.

    Returns:
        Status and ordered issues. Validation does not modify workspace files.
    """
    paths = (
        workspace
        if isinstance(workspace, WorkspacePaths)
        else WorkspacePaths(Path(workspace))
    )
    issues: list[Issue] = []
    if record.provenance == "document" and not record.evidence:
        issues.append(
            Issue(
                "ERROR",
                "missing_evidence",
                "document provenance requires at least one evidence entry",
            )
        )
    issues.extend(_check_evidence(record, paths))
    sealed = record.verification is not None
    intact_seal = verify_seal(record)
    tampered = sealed and not intact_seal
    if tampered:
        issues.append(
            Issue(
                "ERROR",
                "seal_mismatch",
                "verification seal does not match critical fields",
            )
        )
    status: Literal["draft", "verified", "tampered"] = (
        "tampered" if tampered else "verified" if intact_seal else "draft"
    )
    if any(issue.severity == "ERROR" for issue in issues) and status == "verified":
        status = "draft"
    if not intact_seal:
        for field in ("data.level_raw", "data.issuer", "occurred"):
            issues.append(
                Issue("WARN", "critical_field", f"{field} requires human review")
            )
        issues.append(Issue("INFO", "verification", "not yet verified"))
    issues.extend(_duplicate_sources(paths))
    rank = {"ERROR": 0, "WARN": 1, "INFO": 2}
    issues.sort(key=lambda issue: rank[issue.severity])
    return CheckResult(status=status, issues=issues)
