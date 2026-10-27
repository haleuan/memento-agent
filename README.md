# Memento Agent v0.1

A small provenance-backed record checker. Records are strict TOML with typed
achievement data. For document-derived records, `memento check` verifies that
each evidence quote appears in the referenced source parse block after
whitespace normalization. User-provided records may omit evidence.

```sh
uv sync --dev
uv run memento check records/achievement/ach_<ULID>.toml
uv run ruff check src tests
uv run pyright
```

The checker prints `OK` and exits `0` for valid records. It prints readable
errors and exits `1` otherwise. It does not write to the workspace.

Python 3.11+, Pydantic v2, and pytest are used. The `mementoagent` command is an
alias for `memento`. Concrete OCR engines, verification seals, extraction,
review, and generation are outside v0.1.
