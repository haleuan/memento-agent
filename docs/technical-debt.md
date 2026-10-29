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

- **Status**: `accepted`
- **Location**: `src/mementoagent/workspace/discovery.py`, `WorkspacePaths.blocks_path`
- **Current state and impact**: The reserved parse path is fixed to `blocks.jsonl`, which encodes an old block-level snapshot assumption even though current evidence validation only requires source-level provenance.
- **Reason deferred**: Parser adapters and the parse snapshot format have not been designed yet.
- **Review trigger**: When the parse snapshot contract or the first parser adapter is implemented.
- **Completion criteria**: Parse snapshot paths represent the chosen snapshot contract, block data is optional, and no evidence validation depends on a block identifier.

## TD-004: Documentation Contract Drift

- **Status**: `accepted`
- **Location**: `README.md` and the historical sections of `AGENTS.md`
- **Current state and impact**: Some documentation still describes TOML records and block-level quote matching, while the implementation uses YAML front matter and source-level evidence validation. This can lead future contributors to implement the wrong contract.
- **Reason deferred**: The current work has focused on stabilizing the storage and validation code rather than revising project documentation.
- **Review trigger**: Before the next user-facing release or documentation update.
- **Completion criteria**: Documentation consistently describes YAML record files, source-level evidence, optional page/quote metadata, and the actual available commands.
