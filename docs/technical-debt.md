# Technical Debt Register

This register records deferred refactors, cleanup, and design work that has a
known reason to remain unfinished. It is not a list of speculative features.

Each entry must include:

- a stable debt ID and code or document location;
- the current state and its impact;
- why the work is deferred;
- a concrete review trigger;
- completion criteria;
- a status: `open`, `accepted`, `in-progress`, `done`, or `wont-fix`.

Architectural decisions and their rationale belong in ADRs. A local `TODO`
comment should be brief and reference the relevant debt ID.

## TD-001: JSON Source Lookup

- **Status**: `accepted`
- **Location**: `src/mementoagent/workspace/discovery.py`, `WorkspacePaths.find_source_file_by_hash`
- **Current state and impact**: Source lookup excludes files with a `.json` suffix. A legitimate JSON source imported into content-addressed storage cannot be found by its hash, and the suffix rule also couples source lookup to an assumed sidecar format.
- **Reason deferred**: The current source format does not define JSON sidecars or a JSON-specific source workflow.
- **Review trigger**: Before JSON documents or sidecar metadata are supported.
- **Completion criteria**: Source lookup distinguishes source files from metadata without rejecting a valid source extension, with tests for JSON sources and sidecars.

## TD-002: Split CLI Command Modules

- **Status**: `accepted`
- **Location**: `src/mementoagent/cli.py`
- **Current state and impact**: The CLI entry point currently contains parser construction and the complete `check` command flow. More commands would make the entry point harder to review and test in isolation.
- **Reason deferred**: The CLI currently exposes only one command, so extracting a command module would add structure without current benefit.
- **Review trigger**: Before adding the second CLI command.
- **Completion criteria**: `cli.py` remains the composition and dispatch entry point; each command has an independent module and tests; the public `mementoagent.cli:main` entry point remains stable.

## TD-003: Parse Snapshot Path Contract

- **Status**: `done`
- **Location**: `src/mementoagent/workspace/discovery.py`, `WorkspacePaths.blocks_path` (replaced by `parse_snapshot_dir`)
- **Current state and impact**: The previous path method assumed each snapshot was `blocks.jsonl`, which encoded a block-level contract that current evidence validation did not require.
- **Reason deferred**: It was deferred until the parse snapshot format was defined.
- **Review trigger**: Triggered when the parse snapshot contract was implemented.
- **Completion criteria**: Snapshot paths represent the chosen contract, block data is optional, and evidence validation does not depend on block identifiers.
- **Resolution**: Parse snapshots use `metadata.toml` and raw `content.md` under `.memento/parses/<source-digest>/<parse-id>/`; the old `blocks_path` method was replaced, with no block-level evidence requirement.

## TD-004: Documentation Contract Drift

- **Status**: `done`
- **Location**: `README.md` and the historical sections of `AGENTS.md`
- **Current state and impact**: The previous documentation described TOML records and block-level quote matching, which could lead contributors to implement a contract different from the code.
- **Reason deferred**: Documentation was deferred while storage and validation behavior was being stabilized.
- **Review trigger**: Triggered during the parse snapshot contract update.
- **Completion criteria**: Documentation consistently describes structured TOML records, source-level evidence, optional page/quote metadata, and the available commands.
- **Resolution**: README and AGENTS.md now describe pure TOML records, source-level evidence validation, TOML parse metadata with raw Markdown parse content, and the current command surface. The YAML front matter format was replaced as part of the structured-record redesign.

## TD-005: Preserve the Full MinerU Artifact Set

- **Status**: `accepted`
- **Location**: `src/mementoagent/parsers/mineru.py` and `src/mementoagent/workspace/parses.py`
- **Current state and impact**: The first MinerU integration preserves only the downloaded `full.md` output as the parse snapshot content. ZIP/JSON responses, images, tables, and layout metadata are not retained, so later consumers cannot reconstruct every parser result from the snapshot alone.
- **Reason deferred**: The first integration only needs readable text for source-level record extraction. Defining an artifact manifest and stable storage for every MinerU output would expand the snapshot contract before a concrete consumer requires it.
- **Review trigger**: When evidence or generated materials need page layout, images, tables, coordinates, raw MinerU responses, or parser replay/comparison.
- **Completion criteria**: The snapshot contract defines an artifact manifest and preserves the required MinerU ZIP/JSON/assets/layout outputs with content hashes, deterministic paths, and tests that load and verify the complete artifact set.

## TD-006: Review and Materialize Achievement Drafts

- **Status**: `accepted`
- **Location**: `src/mementoagent/agents/extraction.py`
- **Current state and impact**: Achievement extraction returns an in-memory draft with source provenance, but does not include occurrence dates, create a `RecordEnvelope`, generate record metadata, write evidence, or save a TOML record. Extracted data therefore needs a separate date-processing and approval path before entering the workspace.
- **Reason deferred**: The current scope isolates structured achievement extraction. The project requires date interpretation to be deterministic, and no date parser exists yet; record creation and human approval also need their own explicit contract.
- **Review trigger**: Before a user-facing workflow needs to approve, edit, date, or persist an extracted achievement.
- **Completion criteria**: Raw date text is passed through a deterministic parser into `PartialDate`; a deterministic draft-to-record conversion creates envelope metadata and source-level evidence, exposes an explicit approval boundary, and persists the approved record with tests.
