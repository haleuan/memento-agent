"""Tests for the conversational achievement review Agent."""

import json
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from openai import OpenAI

from mementoagent.agents import (
    AchievementDraft,
    AchievementReviewAgent,
    AchievementReviewDecision,
    AchievementReviewError,
    AgentRuntime,
    AgentRuntimeError,
    DescriptionSuggestion,
)
from mementoagent.schema import AchievementItem

SOURCE = "sha256:" + "a" * 64


def make_draft(*, suggestion: DescriptionSuggestion | None = None) -> AchievementDraft:
    """Build a review draft for the tests."""
    return AchievementDraft(
        data=AchievementItem(
            kind="award",
            title="Graduate Scholarship",
            organization="Example University",
            level_raw="First Prize",
        ),
        source=SOURCE,
        description_suggestion=suggestion,
    )


class FakeRuntime:
    """Run a review by invoking the Agent's user tool once."""

    def __init__(
        self,
        decision: AchievementReviewDecision | None = None,
        *,
        invoke_ask_user: bool = True,
    ) -> None:
        """Initialize the configured fake runtime."""
        self.decision = decision
        self.invoke_ask_user = invoke_ask_user
        self.agent: Any = None
        self.value: Any = None
        self.context: object | None = None
        self.questions: list[str] = []
        self.answers: list[str] = []
        self.error: Exception | None = None

    def run(self, agent: Any, value: Any, *, context: object | None = None) -> Any:
        """Record the invocation and execute the generated user question."""
        self.agent = agent
        self.value = value
        self.context = context
        if self.error is not None:
            raise self.error
        if self.invoke_ask_user:
            tool = agent.tools()[0]
            question = (
                "Please review the extracted achievement "
                f"'{value.draft.data.title}' and confirm it."
            )
            self.questions.append(question)
            arguments = tool.parameters(question=question)
            self.answers.append(tool.handler(arguments, context))
        return self.decision


def test_review_asks_user_with_generated_question_and_approves() -> None:
    """Ask the user through the tool before returning an approval."""
    suggestion = DescriptionSuggestion(
        text="Received the graduate scholarship.",
        rationale="Restates the documented award and level.",
    )
    runtime = FakeRuntime(
        AchievementReviewDecision(status="approved", description=suggestion.text)
    )
    messages: list[str] = []

    result = AchievementReviewAgent(runtime).review(
        make_draft(suggestion=suggestion),
        ask_user=lambda question: messages.append(question) or "approve",
    )

    assert len(messages) == 1
    assert messages[0] == runtime.questions[0]
    assert "Graduate Scholarship" in messages[0]
    assert result.status == "approved"
    assert result.description == suggestion.text
    assert result.reviewed_data is not None
    assert result.reviewed_data.description is None
    assert runtime.answers == ["approve"]


def test_review_preserves_source_and_original_draft_when_facts_change() -> None:
    """Keep the extracted draft and source separate from corrected facts."""
    draft = make_draft()
    corrected = draft.data.model_copy(update={"organization": "Graduate School"})
    runtime = FakeRuntime(AchievementReviewDecision(status="approved", data=corrected))

    result = AchievementReviewAgent(runtime).review(
        draft, ask_user=lambda _question: "correct the organization"
    )

    assert result.status == "approved"
    assert result.reviewed_data is not None
    assert result.reviewed_data.organization == "Graduate School"
    assert result.draft.data.organization == "Example University"
    assert result.draft.source == SOURCE
    assert result.description is None


def test_review_returns_rejection_without_reviewed_data() -> None:
    """Apply an explicit rejection while retaining the original source."""
    runtime = FakeRuntime(AchievementReviewDecision(status="rejected"))

    result = AchievementReviewAgent(runtime).review(
        make_draft(), ask_user=lambda _question: "reject this achievement"
    )

    assert result.status == "rejected"
    assert result.reviewed_data is None
    assert result.description is None
    assert result.draft.source == SOURCE


def test_review_wraps_callback_and_runtime_errors() -> None:
    """Expose one domain error boundary for callback and runtime failures."""
    with pytest.raises(AchievementReviewError, match="achievement review failed"):
        AchievementReviewAgent(FakeRuntime()).review(
            make_draft(),
            ask_user=lambda _question: (_ for _ in ()).throw(
                RuntimeError("callback failed")
            ),
        )

    runtime = FakeRuntime()
    runtime.error = AgentRuntimeError("runtime failed")
    with pytest.raises(AchievementReviewError, match="achievement review failed"):
        AchievementReviewAgent(runtime).review(
            make_draft(), ask_user=lambda _question: "approve"
        )


def test_review_requires_an_ask_user_call() -> None:
    """Reject runtimes that return a decision without contacting the user."""
    runtime = FakeRuntime(
        AchievementReviewDecision(status="approved"), invoke_ask_user=False
    )

    with pytest.raises(AchievementReviewError, match="review did not ask the user"):
        AchievementReviewAgent(runtime).review(
            make_draft(), ask_user=lambda _question: "approve"
        )


@pytest.fixture
def mocked_client() -> Iterator[tuple[OpenAI, list[dict[str, Any]]]]:
    """Create an OpenAI client backed by an HTTP mock transport."""
    requests: list[dict[str, Any]] = []
    responses = [
        {
            "id": "resp_1",
            "object": "response",
            "created_at": 1,
            "model": "test-model",
            "status": "completed",
            "output": [
                {
                    "id": "fc_1",
                    "type": "function_call",
                    "name": "ask_user",
                    "arguments": json.dumps(
                        {"question": "Please confirm whether to approve this award."}
                    ),
                    "call_id": "call_1",
                    "status": "completed",
                }
            ],
        },
        {
            "id": "resp_2",
            "object": "response",
            "created_at": 2,
            "model": "test-model",
            "status": "completed",
            "output": [
                {
                    "id": "msg_2",
                    "type": "message",
                    "role": "assistant",
                    "status": "completed",
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps({"status": "approved"}),
                            "annotations": [],
                        }
                    ],
                }
            ],
        },
    ]

    def handle(request: httpx.Request) -> httpx.Response:
        """Return the next canned Responses API response."""
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=responses.pop(0))

    client = OpenAI(
        api_key="test-key",
        base_url="https://model.example/v1",
        http_client=httpx.Client(transport=httpx.MockTransport(handle)),
        max_retries=0,
    )
    try:
        yield client, requests
    finally:
        client.close()


def test_review_runs_first_function_call_then_structured_output(mocked_client) -> None:
    """Exercise ask_user through the SDK before parsing final structured output."""
    client, requests = mocked_client
    runtime = AgentRuntime("test-model", client=client, max_turns=4, max_tool_calls=3)
    questions: list[str] = []

    result = AchievementReviewAgent(runtime).review(
        make_draft(),
        ask_user=lambda question: questions.append(question) or "approve",
    )

    assert result.status == "approved"
    assert result.description is None
    assert questions == ["Please confirm whether to approve this award."]
    assert len(requests) == 2
    assert requests[0]["tools"][0]["name"] == "ask_user"
    assert requests[1]["input"][-1]["type"] == "function_call_output"
    assert requests[1]["input"][-1]["output"] == '"approve"'
