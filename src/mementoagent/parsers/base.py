"""Provider-neutral parser interface."""

from pathlib import Path
from typing import Protocol


class Parser(Protocol):
    """Parse a local source file into Markdown text."""

    name: str

    @property
    def version(self) -> str:
        """Return the parser version recorded in a snapshot."""
        ...

    def parse(self, source_path: Path) -> str:
        """Return the parser's complete Markdown output.

        Args:
            source_path: Path to the source file to parse.

        Returns:
            Complete Markdown output from the parser.
        """
        ...
