"""Entry point for the Memento command-line interface."""

import argparse
from pathlib import Path
import sys
from collections.abc import Sequence

from mementoagent.schema import AchievementItem
from mementoagent.validation import validate_record
from mementoagent.workspace import find_workspace, load_record


def main(argv: Sequence[str] | None = None) -> int:
    """Check one achievement record against its workspace sources.

    Args:
        argv: Command-line arguments, or `None` to use the process arguments.

    Returns:
        Exit code: `0` when the record is valid, or `1` when it is invalid.

    Raises:
        SystemExit: If the command-line arguments are invalid.
    """
    parser = argparse.ArgumentParser(prog="memento")
    subparsers = parser.add_subparsers(dest="command", required=True)
    check_parser = subparsers.add_parser(
        "check", help="validate one achievement record"
    )
    check_parser.add_argument("record_path", type=Path)
    args = parser.parse_args(argv)

    record_path = args.record_path.expanduser().resolve()
    try:
        workspace_root = find_workspace(record_path)
        record = load_record(record_path, AchievementItem)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    errors = validate_record(workspace_root, record)
    if errors:
        print(f"error: {'; '.join(errors)}", file=sys.stderr)
        return 1

    print("OK")
    return 0
