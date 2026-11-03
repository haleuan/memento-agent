"""Entry point for the Memento command-line interface."""

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from mementoagent.parsers import MineruParser
from mementoagent.schema import ACHIEVEMENT_SCHEMA_VERSION, AchievementItem
from mementoagent.validation import validate_record
from mementoagent.workflows.harness import MementoAgent
from mementoagent.workspace import find_workspace, init_workspace, load_record


def _run_init(path: Path) -> int:
    """Initialize a new Memento workspace."""
    try:
        workspace_root = init_workspace(path)
    except (FileExistsError, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(f"Initialized Memento workspace: {workspace_root}")
    return 0


def _run_chat(workspace_root: Path) -> int:
    """Run one line-oriented Memento conversation."""
    load_dotenv()
    if not (workspace_root / ".memento").is_dir():
        print(f"error: not a Memento workspace: {workspace_root}", file=sys.stderr)
        return 1

    model = os.environ["OPENAI_MODEL"]
    mineru_api_key = os.environ["MINERU_API_KEY"]

    with OpenAI() as client, MineruParser(mineru_api_key) as parser:
        agent = MementoAgent(
            client=client,
            model=model,
            workspace_root=workspace_root,
            parser=parser,
        )
        while True:
            try:
                user_input = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            if user_input.lower() in {"exit", "quit"}:
                return 0
            if user_input:
                print(f"Agent: {agent.send(user_input)}")


def main(argv: Sequence[str] | None = None) -> int:
    """Run a deterministic check or an interactive Agent conversation.

    Args:
        argv: Command-line arguments, or `None` to use the process arguments.

    Returns:
        Exit code: `0` when the selected command completes successfully, or
            `1` when validation or command setup fails.

    Raises:
        SystemExit: If the command-line arguments are invalid.
    """
    parser = argparse.ArgumentParser(prog="memento")
    subparsers = parser.add_subparsers(dest="command", required=True)
    init_parser = subparsers.add_parser("init", help="initialize a Memento workspace")
    init_parser.add_argument("path", type=Path)
    check_parser = subparsers.add_parser(
        "check", help="validate one achievement record"
    )
    check_parser.add_argument("record_path", type=Path)
    chat_parser = subparsers.add_parser(
        "chat", help="start an interactive Memento Agent conversation"
    )
    chat_parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args(argv)

    if args.command == "init":
        return _run_init(args.path.expanduser().resolve())
    if args.command == "chat":
        return _run_chat(args.workspace.expanduser().resolve())

    record_path = args.record_path.expanduser().resolve()
    try:
        workspace_root = find_workspace(record_path)
        record = load_record(record_path, AchievementItem)
        if record.schema_version != ACHIEVEMENT_SCHEMA_VERSION:
            raise ValueError(f"unsupported achievement schema: {record.schema_version}")
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    errors = validate_record(workspace_root, record)
    if errors:
        print(f"error: {'; '.join(errors)}", file=sys.stderr)
        return 1

    print("OK")
    return 0
