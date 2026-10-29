# Memento Agent

A provenance-backed personal memory system. Source files are stored by content hash, and structured records refer to their supporting source files through `evidence.source`.

## Workspace

Initialize a workspace with `init_workspace()`. Achievement records are structured TOML files stored as:

```text
records/<record-type>/<record-id>.toml
```

Original supporting documents are imported to `sources/<hash-prefix>/<sha256>.<extension>`. Parse snapshots are optional derived text artifacts stored under `.memento/parses/<source-digest>/<parse-id>/`:

```text
metadata.toml
content.md
```

Snapshot metadata and records are structured TOML. `content.md` preserves the parser's raw text output. Record evidence points directly to the original source file. Page and quote may be included as optional context, but validation only checks that the referenced source exists; it does not require parse snapshots or match quotes to parse blocks.

## Check a Record

From inside a workspace, validate one achievement record with:

```sh
uv run memento check records/achievement/ach_<ULID>.toml
```

The command prints `OK` and exits with status `0` for a valid record. It prints validation or loading errors to stderr and exits with status `1`. Argument errors exit with status `2`.

Run project checks with:

```sh
uv run pytest
uv run pyright
uv run ruff check .
uv run ruff format --check .
```
