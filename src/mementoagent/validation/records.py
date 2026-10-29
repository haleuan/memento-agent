"""Validation rules for persisted records and their source references."""

from pathlib import Path
from typing import Any

from mementoagent.schema import RecordEnvelope
from mementoagent.workspace import WorkspacePaths


def validate_record(
    workspace_root: Path,
    record: RecordEnvelope[Any],
) -> list[str]:
    """Validate a record's source-level provenance.

    Args:
        workspace_root: Workspace root containing the `sources` directory.
        record: Record to validate.

    Returns:
        Validation error messages. An empty list means the record is valid.

    Notes:
        Page numbers and quotes are optional evidence metadata. This validation
        does not require them or match quotes against parsed blocks.
    """
    errors: list[str] = []
    if record.provenance == "document" and not record.evidence:
        errors.append("document provenance requires at least one evidence item")

    paths = WorkspacePaths(workspace_root)
    for evidence in record.evidence:
        if paths.find_source_file_by_hash(evidence.source) is None:
            errors.append(f"evidence source not found: {evidence.source}")

    return errors
