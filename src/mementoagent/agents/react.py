from ..providers import OpenAIProvider


class ReActAgent:
    def __init__(self, provider: OpenAIProvider):
        self.provider = provider

    def run(self, prompt: str) -> str:
        # Use the provider to generate a response based on the prompt
        ...
