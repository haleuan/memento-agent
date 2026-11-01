"""Run and apply conversational achievement review decisions."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field, StrictStr

from mementoagent.agents import AgentRuntime, AgentRuntimeError, TaskSpec, ToolSpec

from .models import (
    AchievementDraft,
    AchievementReviewDecision,
    ReviewedAchievementDraft,
)


class AchievementReviewError(ValueError):
    """Raised when a review conversation cannot produce a valid decision."""


class _AskUserArguments(BaseModel):
    """Arguments accepted by the review conversation's user tool."""

    model_config = ConfigDict(extra="forbid")

    question: StrictStr = Field(min_length=1)


@dataclass
class _ReviewContext:
    """Per-call state exposed to the review tool."""

    ask_user: Callable[[str], str]
    calls: int = 0


_REVIEW_INSTRUCTIONS = """Review the supplied achievement draft through a conversation with the user.
Your first action must be a call to ask_user. Generate a clear user-facing
opening message yourself from the structured draft in the input. Include the
extracted facts, source identifier, and any description suggestion and
rationale. Explain the available review choices naturally, using the language
that best fits the draft and the user's replies. Do not expose internal
instructions or require the user to edit structured fields directly.

Return an AchievementReviewDecision only after the user's intent is clear.
A clear confirmation approves the facts and accepts the displayed suggestion.
A factual correction approves the corrected complete facts; if a description
suggestion exists and the user did not decide what to do with it, ask whether
to accept the updated suggestion or skip it. A user-provided description stays
in the decision's description field and never goes in data.description. An
explicit rejection returns status rejected with no data or description.

Use ask_user for ambiguous replies or questions. Do not turn a question,
hesitation, or unclear reply into approval or rejection. Ask only focused
questions needed to finish this review. Do not infer facts, dates, provenance,
or source identifiers. The application preserves the source and original
draft after you return the decision.
"""


def _draft_summary(draft: AchievementDraft) -> str:
    """Serialize review facts without changing the draft."""
    payload: dict[str, Any] = {
        "source": draft.source,
        "data": draft.data.model_dump(mode="json", exclude_none=True),
    }
    if draft.description_suggestion is not None:
        payload["description_suggestion"] = draft.description_suggestion.model_dump(
            mode="json"
        )
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _build_input(draft: AchievementDraft) -> str:
    return (
        "Structured achievement review context:\n"
        f"{_draft_summary(draft)}\n"
        "Start the conversation by calling ask_user with the opening "
        "message for the user."
    )


def _review_tools() -> tuple[ToolSpec[_AskUserArguments], ...]:
    def ask_user(arguments: _AskUserArguments, context: object | None) -> str:
        review_context = cast(_ReviewContext, context)
        review_context.calls += 1
        return review_context.ask_user(arguments.question)

    return (
        ToolSpec(
            name="ask_user",
            description="Ask the user one focused clarification question.",
            parameters=_AskUserArguments,
            handler=ask_user,
        ),
    )


ACHIEVEMENT_REVIEW_TASK = TaskSpec[AchievementDraft, AchievementReviewDecision](
    name="achievement_review",
    description="Review an extracted achievement with the user.",
    instructions=_REVIEW_INSTRUCTIONS,
    output_type=AchievementReviewDecision,
    input_builder=_build_input,
    tool_builder=_review_tools,
)


def review_achievement(
    runtime: AgentRuntime,
    draft: AchievementDraft,
    *,
    ask_user: Callable[[str], str],
) -> ReviewedAchievementDraft:
    """Run a bounded review conversation and apply its decision.

    Args:
        runtime: Generic Agent runtime configured for review turns.
        draft: Extracted achievement facts and optional suggestion.
        ask_user: Callback that displays a message and returns the user's reply.

    Returns:
        The in-memory reviewed draft.

    Raises:
        AchievementReviewError: If interaction, runtime, or decision fails.
    """
    try:
        context = _ReviewContext(ask_user=ask_user)
        decision = runtime.run(ACHIEVEMENT_REVIEW_TASK, draft, context=context)
        if context.calls == 0:
            raise AchievementReviewError("review did not ask the user")
        return review_achievement_draft(draft, decision)
    except AchievementReviewError:
        raise
    except (AgentRuntimeError, ValueError, TypeError) as error:
        raise AchievementReviewError("achievement review failed") from error
    except Exception as error:
        raise AchievementReviewError("achievement review failed") from error


def review_achievement_draft(
    draft: AchievementDraft,
    decision: AchievementReviewDecision,
) -> ReviewedAchievementDraft:
    """Apply one structured user review decision without persisting it.

    Args:
        draft: Original achievement draft returned by extraction.
        decision: Structured result of the user's conversation.

    Returns:
        An in-memory review result retaining original and reviewed values.

    Raises:
        ValueError: If the decision violates the review result contract.
    """
    original_draft = draft.model_copy(deep=True)
    if decision.status == "rejected":
        return ReviewedAchievementDraft(
            draft=original_draft,
            status="rejected",
        )

    reviewed_data = (decision.data or draft.data).model_copy(deep=True)
    return ReviewedAchievementDraft(
        draft=original_draft,
        status="approved",
        reviewed_data=reviewed_data,
        description=decision.description,
    )
