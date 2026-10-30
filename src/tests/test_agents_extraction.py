"""Tests for structured achievement extraction."""

from dataclasses import dataclass
from typing import Any

import pytest
from pydantic import ValidationError

from mementoagent.agents import (
    AchievementDraft,
    AchievementExtraction,
    AchievementExtractionError,
    AchievementExtractor,
    DescriptionSuggestion,
)
from mementoagent.schema import (
    AchievementItem,
    ParseSnapshot,
    ParseSnapshotMetadata,
)


SOURCE = "sha256:" + "a" * 64


def make_snapshot(content: str = "证书标题\n重庆师范大学\n") -> ParseSnapshot:
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


@dataclass
class FakeResponse:
    """Minimal structured response returned by the fake provider."""

    output_parsed: Any


class FakeProvider:
    """Record provider calls and return a configured structured result."""

    def __init__(self, output: Any) -> None:
        """Create a provider returning `output`."""
        self.output = output
        self.instructions = ""
        self.input = ""
        self.model = ""
        self.text_format: type[AchievementExtraction] | None = None

    def parse(
        self,
        instructions: str,
        input: str,
        model: str,
        text_format: type[AchievementExtraction],
    ) -> FakeResponse:
        """Record the structured request and return its fake response."""
        self.instructions = instructions
        self.input = input
        self.model = model
        self.text_format = text_format
        return FakeResponse(self.output)


def make_extraction(
    *,
    description_suggestion: DescriptionSuggestion | None = None,
    **data: Any,
) -> AchievementExtraction:
    """Build a valid extraction result."""
    return AchievementExtraction(
        data=AchievementItem(
            kind="award",
            title="研究生学业奖学金",
            organization="重庆师范大学",
            **data,
        ),
        description_suggestion=description_suggestion,
    )


def test_extractor_returns_draft_and_injects_source() -> None:
    """Copy structured data and source identity into an in-memory draft."""
    extraction = make_extraction(level_raw="一等奖", certificate_number="202412055458")
    provider = FakeProvider(extraction)

    result = AchievementExtractor(provider, "test-model").extract(
        make_snapshot("标题\n机构\n等级\n编号\n")
    )

    assert result == AchievementDraft(data=extraction.data, source=SOURCE)
    assert result.data.description is None
    assert provider.input == "标题\n机构\n等级\n编号\n"
    assert provider.model == "test-model"
    assert provider.text_format is AchievementExtraction
    assert "Do not infer" in provider.instructions


def test_extractor_keeps_description_suggestion_separate() -> None:
    """Return a candidate description without treating it as extracted data."""
    suggestion = DescriptionSuggestion(
        text="获得重庆师范大学研究生学业奖学金一等奖。",
        rationale="该表述只复述证书明确记载的奖项和等级。",
    )
    extraction = make_extraction(
        description_suggestion=suggestion,
        level_raw="一等奖",
    )
    provider = FakeProvider(extraction)

    result = AchievementExtractor(provider, "test-model").extract(make_snapshot())

    assert result.description_suggestion == suggestion
    assert result.data.description is None
    assert "description_suggestion" in provider.instructions
    assert "Do not invent personal responsibilities" in provider.instructions


def test_extractor_preserves_optional_unknown_fields_as_none() -> None:
    """Keep fields absent from the structured response unset."""
    provider = FakeProvider(make_extraction())

    result = AchievementExtractor(provider, "test-model").extract(make_snapshot())

    assert result.data.level_raw is None
    assert result.data.certificate_number is None
    assert result.data.collaborators is None
    assert result.description_suggestion is None


def test_extractor_rejects_missing_structured_output() -> None:
    """Fail clearly when the provider produces no structured result."""
    provider = FakeProvider(None)

    with pytest.raises(
        AchievementExtractionError,
        match="no structured achievement",
    ):
        AchievementExtractor(provider, "test-model").extract(make_snapshot())


def test_extractor_rejects_user_description() -> None:
    """Keep user-authored descriptions out of document extraction."""
    with pytest.raises(ValidationError, match="description"):
        AchievementExtraction(
            data=AchievementItem(
                kind="award",
                title="奖项",
                organization="机构",
                description="模型生成的描述",
            )
        )


def test_extractor_rejects_invalid_structured_output() -> None:
    """Reject provider data that does not satisfy the achievement schema."""
    provider = FakeProvider({"data": {"kind": "award"}})

    with pytest.raises(
        AchievementExtractionError,
        match="invalid achievement",
    ):
        AchievementExtractor(provider, "test-model").extract(make_snapshot())


def test_extractor_rejects_extra_model_source() -> None:
    """Do not allow the provider to choose the source hash."""
    provider = FakeProvider(
        {
            "data": {
                "kind": "award",
                "title": "奖项",
                "organization": "机构",
            },
            "source": "sha256:" + "c" * 64,
        }
    )

    with pytest.raises(
        AchievementExtractionError,
        match="invalid achievement",
    ):
        AchievementExtractor(provider, "test-model").extract(make_snapshot())


def test_extractor_rejects_extra_suggestion_fields() -> None:
    """Keep suggestion output within its declared schema."""
    provider = FakeProvider(
        {
            "data": {
                "kind": "award",
                "title": "奖项",
                "organization": "机构",
            },
            "description_suggestion": {
                "text": "建议文本",
                "rationale": "建议依据",
                "source": "sha256:" + "c" * 64,
            },
        }
    )

    with pytest.raises(
        AchievementExtractionError,
        match="invalid achievement",
    ):
        AchievementExtractor(provider, "test-model").extract(make_snapshot())


def test_extractor_does_not_write_files(tmp_path) -> None:
    """Extraction is in-memory and does not create workspace artifacts."""
    provider = FakeProvider(make_extraction())

    AchievementExtractor(provider, "test-model").extract(make_snapshot())

    assert list(tmp_path.iterdir()) == []
