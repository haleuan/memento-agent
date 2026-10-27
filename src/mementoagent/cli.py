"""Command-line interface for Memento workspaces."""

import typer

from .commands.check import check

app = typer.Typer(no_args_is_help=True, help="Validate provenance-backed TOML records.")
app.command()(check)


@app.callback()
def _root() -> None:
    """Manage a Memento workspace."""


def main() -> None:
    """Run the Memento CLI application."""
    app()


if __name__ == "__main__":
    main()
