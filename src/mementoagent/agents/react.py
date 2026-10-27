"""ReAct-style agent scaffolding."""

from ..providers import OpenAIProvider


class ReActAgent:
    """Run prompts through a language-model provider."""

    def __init__(self, provider: OpenAIProvider):
        """Initialize the agent with its provider.

        Args:
            provider: Provider used to generate model responses.
        """
        self.provider = provider

    def run(self, prompt: str) -> str:
        """Generate a response to a prompt.

        Args:
            prompt: User prompt to send to the provider.

        Returns:
            The generated response text.
        """
        ...
