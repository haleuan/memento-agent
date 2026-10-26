"""Provenance-backed personal memory assistant."""


def main() -> None:
    """Run the Memento command-line application."""
    from .cli import main as cli_main

    cli_main()
