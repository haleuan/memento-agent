"""Command-line entry point for the v0.1 record checker."""

import argparse
from pathlib import Path
import sys

from .validation.invariants import validate_record
from .validation.shape import RecordLoadError, RecordSyntaxError, load_record_file
from .workspace import WorkspaceNotFoundError, find_workspace


def check(record_path: Path) -> int:
    """Check one TOML record and return its process exit code."""
    if record_path.suffix.lower() != ".toml":
        print("ERROR: record path must end with .toml")
        return 1
    try:
        path = record_path.resolve()
        workspace = find_workspace(path.parent)
        record = load_record_file(path).record
        errors = validate_record(record, workspace)
    except (RecordLoadError, WorkspaceNotFoundError, OSError, ValueError) as error:
        code = "toml_syntax" if isinstance(error, RecordSyntaxError) else "shape"
        print(f"ERROR: {code}: {error}")
        return 1
    if errors:
        for error in errors:
            print(f"ERROR: evidence: {error}")
        return 1
    print("OK")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Parse command-line arguments and run the selected command."""
    parser = argparse.ArgumentParser(prog="memento")
    subparsers = parser.add_subparsers(dest="command", required=True)
    check_parser = subparsers.add_parser("check", help="check one TOML record")
    check_parser.add_argument("record_path", type=Path)
    args = parser.parse_args(argv)
    if args.command == "check":
        return check(args.record_path)
    return 1


if __name__ == "__main__":
    sys.exit(main())
