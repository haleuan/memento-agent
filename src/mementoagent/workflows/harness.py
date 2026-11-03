"""Application harness for the Memento Agent."""

from pathlib import Path

from openai import OpenAI

from mementoagent.agents import Agent, Conversation
from mementoagent.parsers import Parser

from .tools import MementoContext, MementoToolset

_MEMENTO_INSTRUCTIONS = """You are the Memento personal memory assistant.
Understand the user's intent and choose tools when workspace actions are needed.
Do not claim an action succeeded before its tool returns successfully. Explain
extracted facts and suggestions in natural language. Ask for explicit user
confirmation before saving a record. When the user corrects facts or provides
a description, submit the complete corrected AchievementItem to the save tool.
Do not invent facts absent from the document, and do not modify source,
provenance, or evidence. A prepared inbox file is moved into source storage.
The user may inspect a document without saving it.
"""


class MementoAgent:
    """Compose the root conversational Agent and Memento tools."""

    def __init__(
        self,
        client: OpenAI,
        model: str,
        workspace_root: Path,
        parser: Parser,
    ) -> None:
        """Create one isolated Memento conversation."""
        extraction_agent = Agent(
            client=client,
            model=model,
            instructions="Return the structured achievement requested by the capability.",
        )
        context = MementoContext(
            workspace_root=workspace_root,
            parser=parser,
            extraction_agent=extraction_agent,
        )
        self._conversation = Conversation()
        self._agent = Agent(
            client=client,
            model=model,
            instructions=_MEMENTO_INSTRUCTIONS,
            tools=MementoToolset(context).tools(),
        )

    def send(self, user_input: str) -> str:
        """Send one user message and return the final Agent response."""
        return self._agent.run(user_input, conversation=self._conversation)
