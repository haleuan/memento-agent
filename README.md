Principles:
1. Follow Occam's Razor: unnecessary code and unnecessary features will not exist. Reject technical debt in code. Developers friendly.
2. Trim the behavioral boundaries of the model, clarify requirements, and do not waste tokens doing things that are completely unnecessary.

## Core data layer

Phase 1 provides typed achievement records, workspace discovery, provenance
validation, and human verification seals. Python 3.12 or newer is required.

```sh
uv sync --dev
uv run memento check "/path/to/workspace/records/achievement/ach_<ULID>.toml"
uv run pytest
```

`mementoagent` is an alias for `memento`. The checker discovers the workspace by
walking upward from the record's directory until it finds `.memento/`. Workspace
creation, import, parsing, extraction, and interactive review are future phases;
the test fixtures contain complete example workspaces.

`check` reports `draft`, `verified`, or `tampered` without modifying any files.
Exit code `0` means verified with no issues requiring action, `1` means an error,
and `2` means warnings or pending human review. A duplicate source can produce a
warning even when the checked record has a valid seal.

Records are pure TOML with `schema = "achievement/1"`; timestamps must be quoted
strings. Put any optional `body` string before the first TOML table header. A
triple-single-quoted body cannot contain `'''`. Document records require evidence referencing an existing source,
parse snapshot, and block. Evidence quotes must be substrings of block text after
whitespace is collapsed. This checks the quoted text, while a human still reviews
the meaning of the extracted fields.

Seals hash the fields declared critical by the record type, including model
defaults and nulls. Canonicalization uses sorted JSON keys, compact separators,
unescaped Unicode, and UTF-8 bytes. For achievements the critical fields are
`data.kind`, `data.title`, `data.issuer`, `data.level_raw`, and `occurred`;
evidence is validated but excluded from the seal. The body and verification
metadata are excluded.
Seals record human review; the checker never creates them automatically.

Docstring and code-style check:

```sh
uv run ruff check src tests
```

Ruff enforces Google-style docstrings for source modules and tests.
