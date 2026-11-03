"""Extract achievement facts through the generic Agent API."""

from mementoagent.agents import Agent
from mementoagent.schema import ParseSnapshot

from .models import AchievementDraft, AchievementExtraction


class AchievementExtractionError(ValueError):
    """Raised when an Agent response cannot produce an achievement draft."""


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


def extract_achievement(
    agent: Agent,
    snapshot: ParseSnapshot,
) -> AchievementDraft:
    """Extract an in-memory achievement draft from a parse snapshot.

    Args:
        agent: Agent configured with the extraction instructions and model.
        snapshot: Parsed source content and source hash metadata.

    Returns:
        An unpersisted draft whose source is copied from the snapshot.

    Raises:
        AchievementExtractionError: If the Agent cannot produce a usable
            structured achievement.
    """
    try:
        extraction = agent.run_structured(
            snapshot.content,
            output_type=AchievementExtraction,
            instructions=_EXTRACTION_INSTRUCTIONS,
        )
    except (RuntimeError, ValueError) as error:
        raise AchievementExtractionError("achievement extraction failed") from error

    return AchievementDraft(
        data=extraction.data,
        source=snapshot.metadata.source,
        description_suggestion=extraction.description_suggestion,
    )
