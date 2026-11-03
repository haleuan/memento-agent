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

## TD-006: Achievement Capability Depth

- **Status**: `accepted`
- **Location**: `src/mementoagent/capabilities/achievement/`
- **Current state and impact**: Models, deterministic materialization, source validation, and TOML persistence remain available. Extraction and the old root `MementoAgent` integration are retained but paused because they depend on removed Runtime APIs. Automatic source-to-record interaction is unavailable. Occurrence dates also remain unset and evidence has no page, quote, or field-level supports.
- **Reason deferred**: The user approved prioritizing an understandable minimal Agent over preserving the old integration. Date interpretation and fine-grained claim mapping still require concrete consumers and contracts.
- **Review trigger**: After the minimal Agent loop is understood, before restoring Memento interaction; review date and evidence depth when an output requires them.
- **Completion criteria**: Extraction and application tools use the new Agent API without compatibility shims, preserving approval and source boundaries. When required, a deterministic date parser produces `PartialDate`, evidence identifies supported claims at the required precision, and provenance distinguishes source facts, OCR corrections, and user additions.

## TD-011: Cross-Domain Capability Composition

- **Status**: `accepted`
- **Location**: `src/mementoagent/workflows/` and `src/mementoagent/capabilities/`
- **Current state and impact**: The retained workflow harness and semantic tools target the removed Runtime and are temporarily unavailable. The minimal Agent has no capability registry, generic context, or coordinator. There is currently no active application composition layer.
- **Reason deferred**: Reconnecting one domain follows understanding the minimal Agent. A second domain has not demonstrated a shared composition requirement; introducing a generic coordinator now would add unnecessary abstraction.
- **Review trigger**: After restoring the first domain, when a second domain requires shared approval, dependency, or materialization behavior.
- **Completion criteria**: Concrete domains compose tools through the minimal Agent without domain imports in `agents/`; any shared abstraction addresses demonstrated reuse and defines ownership and failure behavior.

## TD-007: Grow the Minimal Agent Incrementally

- **Status**: `in-progress`
- **Location**: `src/mementoagent/agents/`
- **Current state and impact**: `Agent.run()` owns a bounded synchronous Responses API tool loop and preserves model output items and tool results in instance-local replay history. `Tool` uses the SDK Pydantic helper for declarations and locally validates, invokes, and serializes handlers. The old Runtime/task protocols, structured output adapter, Session/events, streaming, subagents, and context injection are removed. The SDK `ResponsesToolRunner` was removed after it rejected a response during its additional native reasoning validation. Old Agent and integration tests still target deleted APIs, so full pytest and full-project Pyright are not currently valid acceptance checks.
- **Reason deferred**: The user requested a substantially smaller implementation to understand before adding features. No advanced capability or test migration should be restored merely for compatibility.
- **Review trigger**: Once the minimal loop is understood and a concrete use requires structured output, streaming, persistence/resume, context compression, cancellation, async execution, handoffs, nested budgets, or observability.
- **Completion criteria**: Each approved extension is introduced independently with a readable contract. Obsolete tests are migrated or replaced only with explicit user approval, and full-project checks become meaningful again after paused integrations are addressed. No compatibility wrappers recreate the deleted framework.

## TD-012: TUI and Slash Command Adapter

- **Status**: `accepted`
- **Location**: `src/mementoagent/cli.py` and the future TUI adapter
- **Current state and impact**: The repository exposes the deterministic
  `memento check` command and a minimal text-returning Agent API. There is no
  terminal renderer, interactive CLI session loop, or slash command dispatcher.
- **Reason deferred**: The Agent must first remain understandable independently
  of terminal rendering. The minimal foundation deliberately omits streaming
  and lifecycle events; an outer adapter can be designed when needed.
- **Review trigger**: After the generic Runtime foundation is complete and
  users need an interactive terminal conversation or commands such as `/init`
  and `/check` inside the TUI.
- **Completion criteria**: The adapter renders Agent text and any explicitly
  approved future streaming contract; slash commands are dispatched
  deterministically before ordinary text is sent to the Agent; and the Agent
  remains independent of terminal rendering.

## TD-008: Evaluate Strict Static Type Checking

- **Status**: `accepted`
- **Location**: `pyproject.toml`, `AGENTS.md`, and production Python annotations
- **Current state and impact**: Pyright currently uses `standard` mode, and the contributor documentation now states that actual baseline. Some unknown or partially annotated types that strict mode would report remain outside the enabled checks.
- **Reason deferred**: This repair keeps the existing type-checking baseline while fixing concrete protocol and data-contract defects. A project-wide strict migration could require unrelated annotation changes and deserves a separate review.
- **Review trigger**: Before broadening the public Runtime/tool interfaces or declaring the project strict-type-checked.
- **Completion criteria**: Strict diagnostics have been assessed, useful annotation gaps are resolved without broad suppression or unnecessary casts, and the chosen mode passes Pyright with matching documentation.

## TD-009: Hard Wall-Clock Deadlines for Parser Requests

- **Status**: `accepted`
- **Location**: `src/mementoagent/parsers/mineru.py` and `src/mementoagent/http.py`
- **Current state and impact**: MinerU checks its time budget before requests and before returning success, and bounds request waits by the remaining budget. HTTPX timeouts apply to individual waiting phases, so an in-flight synchronous upload or download can run past the deadline while continuing to make progress. The final check rejects that late result but cannot interrupt the request at the deadline.
- **Reason deferred**: The current synchronous parser needs bounded polling and honest timeout semantics. Cancellable or streaming requests would expand the transport contract beyond this repair.
- **Review trigger**: When a user-facing workflow requires a hard elapsed-time guarantee or cancellation of slow uploads/downloads.
- **Completion criteria**: The transport and parser define interruption and resource-cleanup behavior, enforce the required elapsed-time bound during active I/O, and have offline tests for slow-progress requests and cancellation without partial-success snapshots.

## TD-010: Repository-Wide English Source and Documentation

- **Status**: `accepted`
- **Location**: Existing Python fixtures and schema examples under `src/`, plus any legacy project documentation containing non-English text
- **Current state and impact**: The Agent Runtime, root MementoAgent, and their directly updated documentation use English, but older test fixtures and schema examples still contain Chinese text. This makes the repository language convention inconsistent and can obscure whether non-English text is test data or an application message.
- **Reason deferred**: The current change is limited to the Agent-centered application boundary. A repository-wide text migration would touch unrelated fixtures and examples without changing runtime behavior.
- **Review trigger**: Before publishing the repository as an English-only reference implementation or when another broad documentation/code cleanup is scheduled.
- **Completion criteria**: All Python source, tests, Markdown documentation, and schema example strings are English, while user-provided sample documents remain explicitly marked as data or excluded from the source-language policy; scans enforce the chosen boundary.
