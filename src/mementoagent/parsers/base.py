"""Provider-neutral interface for document parsers.

Every parser must return normalized blocks: page indexes are zero-based;
bounding boxes are `[x0, y0, x1, y1]` in relative 0..1 coordinates with a
top-left origin, or null; confidence is nullable; and block IDs are unique only
within one parse snapshot.

Concrete engines (e.g. MinerU, PaddleOCR) are implemented later as separate
modules; their output formats must be verified against official docs and real
sample output.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from mementoagent.schema import ParseMeta, ParsedBlock


@dataclass
class ParseResult:
    """Metadata and normalized blocks from one parse snapshot."""

    meta: ParseMeta
    blocks: list[ParsedBlock]


class DocumentParser(Protocol):
    """Interface implemented by future concrete document parsers."""

    def parse(self, source_path: Path) -> ParseResult:
        """Parse a source file into normalized metadata and blocks."""
        ...
