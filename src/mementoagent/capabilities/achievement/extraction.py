"""Extract achievement facts through the generic Agent runtime."""

from mementoagent.agents import AgentRuntime, AgentRuntimeError, TaskSpec
from mementoagent.schema import ParseSnapshot

from .models import AchievementDraft, AchievementExtraction


class AchievementExtractionError(ValueError):
    """Raised when a runtime response cannot produce an achievement draft."""


_EXTRACTION_INSTRUCTIONS = """Extract one achievement from the supplied parsed document.
Use only facts explicitly supported by the document. Preserve names, titles,
organizations, levels, and certificate numbers as written. Leave optional
fields null when the document does not state them. Do not infer missing facts.
Leave data.description null because it is written by the user later.
If a concise description draft can be safely based on the document facts,
return it as description_suggestion with a rationale that identifies what the
user still needs to confirm. Do not invent personal responsibilities, impact,
metrics, or other facts. Return null when no safe suggestion is possible.
"""


def _build_input(snapshot: ParseSnapshot) -> str:
    return snapshot.content


ACHIEVEMENT_EXTRACTION_TASK = TaskSpec[ParseSnapshot, AchievementExtraction](
    name="achievement_extraction",
    description="Extract one document-supported achievement.",
    instructions=_EXTRACTION_INSTRUCTIONS,
    output_type=AchievementExtraction,
    input_builder=_build_input,
)


def extract_achievement(
    runtime: AgentRuntime,
    snapshot: ParseSnapshot,
) -> AchievementDraft:
    """Extract an in-memory achievement draft from a parse snapshot.

    Args:
        runtime: Generic Agent runtime used to execute the task.
        snapshot: Parsed source content and source hash metadata.

    Returns:
        An unpersisted draft whose source is copied from the snapshot.

    Raises:
        AchievementExtractionError: If the runtime cannot produce a usable
            structured achievement.
    """
    try:
        extraction = runtime.run(ACHIEVEMENT_EXTRACTION_TASK, snapshot)
    except AgentRuntimeError as error:
        raise AchievementExtractionError(str(error)) from error

    return AchievementDraft(
        data=extraction.data,
        source=snapshot.metadata.source,
        description_suggestion=extraction.description_suggestion,
    )
