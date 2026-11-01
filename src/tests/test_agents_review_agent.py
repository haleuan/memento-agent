"""Tests for the conversational achievement review Agent."""

import json
from collections.abc import Callable, Iterator
from typing import Any

import httpx
import pytest
from openai import OpenAI

from mementoagent.agents import AgentRuntime, AgentRuntimeError
from mementoagent.schema import AchievementItem
from mementoagent.workflows.achievement import (
    AchievementDraft,
    AchievementReviewDecision,
    AchievementReviewError,
    DescriptionSuggestion,
    review_achievement,
)

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
                f"'{value.data.title}' and confirm it."
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

    result = review_achievement(
        runtime,
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

    result = review_achievement(
        runtime, draft, ask_user=lambda _question: "correct the organization"
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

    result = review_achievement(
        runtime, make_draft(), ask_user=lambda _question: "reject this achievement"
    )

    assert result.status == "rejected"
    assert result.reviewed_data is None
    assert result.description is None
    assert result.draft.source == SOURCE


def test_review_wraps_callback_and_runtime_errors() -> None:
    """Expose one domain error boundary for callback and runtime failures."""
    with pytest.raises(AchievementReviewError, match="achievement review failed"):
        review_achievement(
            FakeRuntime(),
            make_draft(),
            ask_user=lambda _question: (_ for _ in ()).throw(
                RuntimeError("callback failed")
            ),
        )

    runtime = FakeRuntime()
    runtime.error = AgentRuntimeError("runtime failed")
    with pytest.raises(AchievementReviewError, match="achievement review failed"):
        review_achievement(runtime, make_draft(), ask_user=lambda _question: "approve")


def test_review_requires_an_ask_user_call() -> None:
    """Reject runtimes that return a decision without contacting the user."""
    runtime = FakeRuntime(
        AchievementReviewDecision(status="approved"), invoke_ask_user=False
    )

    with pytest.raises(AchievementReviewError, match="review did not ask the user"):
        review_achievement(runtime, make_draft(), ask_user=lambda _question: "approve")


def model_response(item: dict[str, Any]) -> dict[str, Any]:
    """Wrap a canned output item in a Responses API response."""
    return {
        "id": "resp_test",
        "object": "response",
        "created_at": 1,
        "model": "test-model",
        "status": "completed",
        "output": [item],
    }


def user_question(question: str, call_id: str) -> dict[str, Any]:
    """Build a model-generated question exposed through the user tool."""
    return model_response(
        {
            "id": f"fc_{call_id}",
            "type": "function_call",
            "name": "ask_user",
            "arguments": json.dumps({"question": question}),
            "call_id": call_id,
            "status": "completed",
        }
    )


def final_decision(decision: AchievementReviewDecision) -> dict[str, Any]:
    """Build a final structured review decision returned by the model."""
    return model_response(
        {
            "id": "msg_final",
            "type": "message",
            "role": "assistant",
            "status": "completed",
            "content": [
                {
                    "type": "output_text",
                    "text": decision.model_dump_json(),
                    "annotations": [],
                }
            ],
        }
    )


ClientFactory = Callable[[list[dict[str, Any]]], tuple[OpenAI, list[dict[str, Any]]]]


@pytest.fixture
def client_factory() -> Iterator[ClientFactory]:
    """Create and close SDK clients backed exclusively by HTTP mocks."""
    clients: list[OpenAI] = []

    def make_client(
        responses: list[dict[str, Any]],
    ) -> tuple[OpenAI, list[dict[str, Any]]]:
        requests: list[dict[str, Any]] = []

        def handle(request: httpx.Request) -> httpx.Response:
            requests.append(json.loads(request.content))
            return httpx.Response(200, json=responses.pop(0))

        client = OpenAI(
            api_key="test-key",
            base_url="https://model.example/v1",
            http_client=httpx.Client(transport=httpx.MockTransport(handle)),
            max_retries=0,
        )
        clients.append(client)
        return client, requests

    yield make_client
    for client in clients:
        client.close()


def test_review_runs_first_function_call_then_structured_output(client_factory) -> None:
    """Exercise ask_user through the SDK before parsing final structured output."""
    client, requests = client_factory(
        [
            user_question("Please confirm whether to approve this award.", "opening"),
            final_decision(AchievementReviewDecision(status="approved")),
        ]
    )
    runtime = AgentRuntime("test-model", client=client, max_turns=4, max_tool_calls=3)
    questions: list[str] = []

    result = review_achievement(
        runtime,
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


@pytest.mark.parametrize(
    ("first_reply", "follow_up", "organization"),
    [
        (
            "What does First Prize mean?",
            "First Prize is the level stated in the certificate. Approve or reject?",
            "Example University",
        ),
        (
            "Change the organization to Graduate School.",
            "The organization is corrected. Accept the description or skip it?",
            "Graduate School",
        ),
    ],
)
def test_review_round_trips_follow_up_before_final_decision(
    client_factory, first_reply: str, follow_up: str, organization: str
) -> None:
    """Relay canned ambiguity or correction through two user-tool exchanges."""
    suggestion = DescriptionSuggestion(
        text="Received the graduate scholarship.",
        rationale="Restates the documented award.",
    )
    draft = make_draft(suggestion=suggestion)
    original = draft.model_copy(deep=True)
    corrected = draft.data.model_copy(update={"organization": organization})
    opening = (
        f"Review {draft.data.title} from {draft.data.organization}; "
        f"source {draft.source}. Suggested description: {suggestion.text} "
        f"Reason: {suggestion.rationale}"
    )
    client, requests = client_factory(
        [
            user_question(opening, "opening"),
            user_question(follow_up, "follow_up"),
            final_decision(
                AchievementReviewDecision(status="approved", data=corrected)
            ),
        ]
    )
    runtime = AgentRuntime("test-model", client=client, max_turns=4, max_tool_calls=3)
    questions: list[str] = []
    replies = iter([first_reply, "Approve the facts and skip the description."])

    def ask_user(question: str) -> str:
        """Record each model question and supply the next scripted reply."""
        questions.append(question)
        return next(replies)

    result = review_achievement(runtime, draft, ask_user=ask_user)

    assert questions == [opening, follow_up]
    assert len(requests) == 3
    first_output = requests[1]["input"][-1]
    assert first_output["call_id"] == "opening"
    assert json.loads(first_output["output"]) == first_reply
    second_output = requests[2]["input"][-1]
    assert second_output["call_id"] == "follow_up"
    assert (
        json.loads(second_output["output"])
        == "Approve the facts and skip the description."
    )
    assert draft == original
    assert result.draft == original
    assert result.draft.source == SOURCE
    assert result.draft.description_suggestion == suggestion
    assert result.reviewed_data == corrected
    assert result.reviewed_data.description is None
    assert result.description is None


def test_review_reuses_task_with_independent_callback_contexts() -> None:
    """Keep callbacks and interaction counts local to each workflow call."""
    runtime = FakeRuntime(AchievementReviewDecision(status="approved"))
    draft = make_draft()
    first_questions: list[str] = []
    second_questions: list[str] = []

    review_achievement(
        runtime,
        draft,
        ask_user=lambda question: first_questions.append(question) or "first reply",
    )
    first_task, first_context = runtime.agent, runtime.context
    review_achievement(
        runtime,
        draft,
        ask_user=lambda question: second_questions.append(question) or "second reply",
    )

    assert runtime.agent is first_task
    assert runtime.context is not first_context
    assert len(first_questions) == len(second_questions) == 1
    assert runtime.answers == ["first reply", "second reply"]

    runtime.invoke_ask_user = False
    with pytest.raises(AchievementReviewError, match="review did not ask the user"):
        review_achievement(runtime, draft, ask_user=lambda _question: "unused")
    assert len(first_questions) == len(second_questions) == 1


@pytest.mark.parametrize(
    ("max_turns", "max_tool_calls", "cause_message"),
    [(2, 3, "final output"), (4, 1, "tool call limit")],
)
def test_review_budget_exhaustion_returns_no_partial_result(
    client_factory, max_turns: int, max_tool_calls: int, cause_message: str
) -> None:
    """Map actual Runtime limits to a domain failure after an ambiguous reply."""
    draft = make_draft(
        suggestion=DescriptionSuggestion(
            text="Suggested text", rationale="Source facts"
        )
    )
    original = draft.model_copy(deep=True)
    client, requests = client_factory(
        [
            user_question("Review this scholarship.", "opening"),
            user_question("Which part should be corrected?", "follow_up"),
        ]
    )
    runtime = AgentRuntime(
        "test-model", client=client, max_turns=max_turns, max_tool_calls=max_tool_calls
    )
    questions: list[str] = []

    with pytest.raises(
        AchievementReviewError, match="achievement review failed"
    ) as error:
        review_achievement(
            runtime,
            draft,
            ask_user=lambda question: (
                questions.append(question) or "Something is wrong."
            ),
        )

    assert isinstance(error.value.__cause__, AgentRuntimeError)
    assert cause_message in str(error.value.__cause__)
    assert questions == ["Review this scholarship."]
    assert len(requests) == 2
    assert draft == original
