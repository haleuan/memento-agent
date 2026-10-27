Do not add features, modules or dependencies beyond what this file describes. If something seems missing, ask.

# Memento Agent v0.1

Memento is a small provenance-backed personal memory store. Every document-derived claim must point to a source document block and include a quote found in that block. Never fabricate facts.

## Workspace

```text
workspace/                 # User-owned, portable data
├── inbox/
├── sources/<hash-prefix>/<sha256>.<ext>
├── records/<type>/<id>.toml
├── outputs/
└── .memento/
    ├── parses/<source-hash>/<parse-id>/{meta.json,blocks.jsonl}
    └── cache/              # Rebuildable and git-ignored
user config                # Machine-specific secrets and defaults; never committed
```

The `.memento/` directory marks a workspace. Discover it by walking upward from the record path. Store workspace-relative paths only.

## Records

Records are pure TOML. Keep top-level keys, including optional `body`, before any table header. Quote timestamps so TOML does not parse them as datetime values.

```toml
id = "ach_01JBX7Q3M8K2N5R9V4W6Y0ZDEF"
schema = "achievement/1"
provenance = "document" # document | user | agent
created_at = "2025-01-12T09:30:00+08:00"
body = "Optional user narrative"

[data]
kind = "award"
title = "Award title"
issuer = "Awarding organization"
level_raw = "Raw source wording"

[[evidence]]
source = "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
parse = "p_20250112_093045"
block = "p0-b07"
quote = "Text copied from the source block"
```

| Field | Meaning |
| --- | --- |
| `id`, `schema` | Stable typed record identifier and schema version |
| `provenance` | `document`, `user`, or `agent` claim origin |
| `created_at`, `occurred` | Quoted creation timestamp and optional event date range |
| `data` | Strict type-specific payload; achievement text stays unnormalized |
| `evidence` | Source hash, parse ID, block ID, and matching quote |
| `verification` | Optional placeholder only; `sealed` is never computed or checked |

## Parse contract

`ParseMeta` contains `parse_id`, `source`, free-string `engine` and `version`, `params`, and `parsed_at`. A `ParsedBlock` has a zero-based page, text, type, nullable confidence, and `bbox` as `[x0, y0, x1, y1]` in relative 0..1 coordinates with top-left origin, or null. Block IDs are unique only within one parse snapshot.

`DocumentParser.parse(source_path: Path) -> ParseResult` returns metadata and normalized blocks. Concrete engines (such as MinerU or PaddleOCR) come later in separate modules; verify their formats against official documentation and real sample output first.

## Check

`memento check <record.toml>` loads TOML, validates strict Pydantic shapes, and checks document evidence: evidence is required, source file/parse snapshot/block must exist, and the quote must occur in block text after whitespace normalization. It prints `OK` and exits 0 when valid; otherwise it prints errors and exits 1. It never modifies records.

## Non-goals

Seals, tamper detection, derived status, review flags or UI, extraction, generation, and concrete OCR engines are out of scope.

Later: workspace initialization; source import; concrete parser adapters; interactive review; generated outputs.

## Development rules

- Python 3.11+, `uv`, Pydantic v2, and pytest.
- Keep Pydantic models strict with `extra="forbid"`.
- Keep changes small and behavior within this document.
- Test with `uv run pytest`; check style and types with Ruff and Pyright.
