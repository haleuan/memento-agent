"""Evidence grounding checks for records."""

import json
from pathlib import Path

from mementoagent.schema import AchievementData, RecordEnvelope
from mementoagent.workspace import WorkspacePaths


def normalize_whitespace(value: str) -> str:
    """Collapse repeated whitespace before comparing evidence text."""
    return " ".join(value.split())


def validate_record(record: RecordEnvelope[AchievementData], workspace: Path | str) -> list[str]:
    """Return evidence errors for a record in a workspace."""
    if record.provenance != "document":
        return []
    if not record.evidence:
        return ["document provenance requires evidence"]
    paths = WorkspacePaths(Path(workspace))
    errors: list[str] = []
    for index, evidence in enumerate(record.evidence):
        prefix = f"evidence[{index}]"
        source = paths.source_path(evidence.source)
        if source is None:
            errors.append(f"{prefix}: source not found")
            continue
        blocks_path = paths.blocks_path(evidence.source, evidence.parse)
        if not blocks_path.is_file():
            errors.append(f"{prefix}: parse snapshot not found")
            continue
        block = None
        for line in blocks_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                candidate = json.loads(line)
                if candidate.get("id") == evidence.block:
                    block = candidate
                    break
        if block is None:
            errors.append(f"{prefix}: block not found")
        elif normalize_whitespace(evidence.quote) not in normalize_whitespace(
            block.get("text", "")
        ):
            errors.append(f"{prefix}: quote not found in block text")
    return errors
