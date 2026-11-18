"""Entry point for the Memento command-line interface."""

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

from mementoagent.agents import AgentEvent
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


def _run_chat(workspace_root: Path, *, stream: bool = True) -> int:
    """Run one line-oriented Memento conversation."""
    load_dotenv()
    if not (workspace_root / ".memento").is_dir():
        print(f"error: not a Memento workspace: {workspace_root}", file=sys.stderr)
        return 1

    model = os.environ["OPENAI_MODEL"]
    mineru_api_key = os.environ["MINERU_API_KEY"]

    text_line_open = False

    def render_event(event: AgentEvent) -> None:
        """Write visible text to stdout and stage notifications to stderr."""
        nonlocal text_line_open
        if event.kind == "text_delta":
            if not text_line_open:
                print("Agent: ", end="", flush=True)
            print(event.delta, end="", flush=True)
            text_line_open = True
            return

        if text_line_open:
            print(flush=True)
            text_line_open = False
        if event.kind == "model_request":
            print("[model] requesting", file=sys.stderr, flush=True)
        elif event.kind == "tool_call":
            print(f"[tool] {event.tool_name}: started", file=sys.stderr, flush=True)
        elif event.kind == "tool_result":
            print(f"[tool] {event.tool_name}: returned", file=sys.stderr, flush=True)

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
                if user_input.lower() in {"exit", "quit"}:
                    return 0
                if not user_input:
                    continue
                reply = agent.send(user_input, stream=stream, on_event=render_event)
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            except (OpenAIError, RuntimeError):
                if text_line_open:
                    print(flush=True)
                print(
                    "error: Agent run failed. Completed steps remain in this session.",
                    file=sys.stderr,
                    flush=True,
                )
            else:
                if text_line_open:
                    print(flush=True)
                if not stream:
                    print(f"Agent: {reply}")
            text_line_open = False


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
    chat_parser.add_argument(
        "--no-stream",
        action="store_true",
        help="print complete replies without streaming",
    )
    args = parser.parse_args(argv)

    if args.command == "init":
        return _run_init(args.path.expanduser().resolve())
    if args.command == "chat":
        return _run_chat(
            args.workspace.expanduser().resolve(), stream=not args.no_stream
        )

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
