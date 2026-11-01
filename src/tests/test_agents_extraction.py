"""Tests for structured achievement extraction."""

from typing import Any

import pytest
from pydantic import ValidationError

from mementoagent.agents.runtime import AgentRuntimeError
from mementoagent.schema import (
    AchievementItem,
    ParseSnapshot,
    ParseSnapshotMetadata,
)
from mementoagent.workflows.achievement import (
    AchievementDraft,
    AchievementExtraction,
    AchievementExtractionError,
    DescriptionSuggestion,
    extract_achievement,
)

SOURCE = "sha256:" + "a" * 64


def make_snapshot(
    content: str = "Certificate title\nExample University\n",
) -> ParseSnapshot:
    """Build a parse snapshot for an extraction test."""
    return ParseSnapshot(
        metadata=ParseSnapshotMetadata(
            schema="parse/1",
            parse_id="parse_" + "b" * 32,
            source=SOURCE,
            parser="test",
            parser_version="1",
            created_at="2025-01-12T09:30:00+08:00",
        ),
        content=content,
    )


class FakeRuntime:
    """Return a configured structured extraction from a task input."""

    def __init__(self, output: Any = None, error: Exception | None = None) -> None:
        """Create a fake runtime returning `output` or raising `error`."""
        self.output = output
        self.error = error
        self.agent = None
        self.value = None

    def run(self, agent: Any, value: ParseSnapshot) -> Any:
        """Record the task invocation and return its configured output."""
        self.agent = agent
        self.value = value
        if self.error is not None:
            raise self.error
        return self.output


def make_extraction(
    *,
    description_suggestion: DescriptionSuggestion | None = None,
    **data: Any,
) -> AchievementExtraction:
    """Build a valid extraction result."""
    return AchievementExtraction(
        data=AchievementItem(
            kind="award",
            title="Graduate Scholarship",
            organization="Example University",
            **data,
        ),
        description_suggestion=description_suggestion,
    )


def test_extractor_returns_draft_and_injects_source() -> None:
    """Copy structured data and source identity into an in-memory draft."""
    extraction = make_extraction(
        level_raw="First Prize", certificate_number="202412055458"
    )
    runtime = FakeRuntime(extraction)

    result = extract_achievement(
        runtime, make_snapshot("Title\nIssuer\nLevel\nNumber\n")
    )

    assert result == AchievementDraft(data=extraction.data, source=SOURCE)
    assert result.data.description is None
    assert runtime.agent.name == "achievement_extraction"
    assert runtime.value.content == "Title\nIssuer\nLevel\nNumber\n"
    assert "Do not infer" in runtime.agent.instructions


def test_extractor_keeps_description_suggestion_separate() -> None:
    """Return a candidate description without treating it as extracted data."""
    suggestion = DescriptionSuggestion(
        text="Received the Graduate Scholarship First Prize at Example University.",
        rationale="Restates only the award and level documented in the certificate.",
    )
    extraction = make_extraction(
        description_suggestion=suggestion,
        level_raw="First Prize",
    )
    runtime = FakeRuntime(extraction)

    result = extract_achievement(runtime, make_snapshot())

    assert result.description_suggestion == suggestion
    assert result.data.description is None
    assert "description_suggestion" in runtime.agent.instructions
    assert "Do not invent personal responsibilities" in runtime.agent.instructions


def test_extractor_preserves_optional_unknown_fields_as_none() -> None:
    """Keep fields absent from the structured response unset."""
    runtime = FakeRuntime(make_extraction())

    result = extract_achievement(runtime, make_snapshot())

    assert result.data.level_raw is None
    assert result.data.certificate_number is None
    assert result.data.collaborators is None
    assert result.description_suggestion is None


def test_extractor_rejects_missing_structured_output() -> None:
    """Fail clearly when the runtime produces no structured result."""
    runtime = FakeRuntime(
        error=AgentRuntimeError("provider returned no structured achievement")
    )

    with pytest.raises(
        AchievementExtractionError,
        match="no structured achievement",
    ):
        extract_achievement(runtime, make_snapshot())


def test_extractor_rejects_user_description() -> None:
    """Keep user-authored descriptions out of document extraction."""
    with pytest.raises(ValidationError, match="description"):
        AchievementExtraction(
            data=AchievementItem(
                kind="award",
                title="Award",
                organization="Institution",
                description="Model-generated description",
            )
        )


def test_extractor_rejects_invalid_structured_output() -> None:
    """Reject runtime data that does not satisfy the achievement schema."""
    runtime = FakeRuntime(
        error=AgentRuntimeError("provider returned an invalid achievement")
    )

    with pytest.raises(
        AchievementExtractionError,
        match="invalid achievement",
    ):
        extract_achievement(runtime, make_snapshot())


def test_extractor_does_not_write_files(tmp_path) -> None:
    """Extraction is in-memory and does not create workspace artifacts."""
    runtime = FakeRuntime(make_extraction())

    extract_achievement(runtime, make_snapshot())

    assert list(tmp_path.iterdir()) == []
