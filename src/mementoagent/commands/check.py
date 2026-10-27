"""Read-only validation of one memory record."""

from pathlib import Path

import typer

from ..validation.invariants import validate_record
from ..validation.shape import RecordLoadError, RecordSyntaxError, load_record_file
from ..workspace.discovery import WorkspaceNotFoundError, find_workspace


def check(record_path: Path) -> None:
    """Check a TOML record against its workspace and verification seal."""
    if record_path.suffix.lower() != ".toml":
        typer.echo("Status: draft")
        typer.echo("Issues:")
        typer.echo("  - [ERROR] shape: Record path must end with .toml")
        raise typer.Exit(1)
    try:
        path = record_path.resolve()
        workspace = find_workspace(path.parent)
        loaded = load_record_file(path)
        result = validate_record(loaded.record, workspace)
    except (RecordLoadError, WorkspaceNotFoundError, OSError, ValueError) as error:
        typer.echo("Status: draft")
        typer.echo("Issues:")
        code = "toml_syntax" if isinstance(error, RecordSyntaxError) else "shape"
        typer.echo(f"  - [ERROR] {code}: {error}")
        raise typer.Exit(1) from None

    typer.echo(f"Status: {result.status}")
    typer.echo("Issues:")
    severity_order = {"ERROR": 0, "WARN": 1, "INFO": 2}
    for issue in sorted(result.issues, key=lambda item: severity_order[item.severity]):
        typer.echo(f"  - [{issue.severity}] {issue.code}: {issue.message}")
    raise typer.Exit(result.exit_code)
