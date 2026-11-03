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
- **Current state and impact**: The CLI entry point contains parser construction, deterministic `init` and `check` commands, and the thin line-oriented `chat` adapter. Additional commands would make the entry point harder to review and test in isolation.
- **Reason deferred**: The current two-command surface is still small enough to keep as one composition entry point.
- **Review trigger**: Before adding a third command or a slash-command dispatcher.
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
- **Current state and impact**: Achievement extraction and the Memento harness now use the minimal Agent API, and the first vertical slice is available through a line-oriented `memento chat` adapter. Occurrence dates remain unset and evidence has no page, quote, or field-level supports.
- **Reason deferred**: Date interpretation and fine-grained claim mapping require concrete consumers and contracts beyond the first usable slice.
- **Review trigger**: Before a workflow needs event dates or evidence more precise than source-level traceability.
- **Completion criteria**: Extraction and application tools use the new Agent API without compatibility shims, preserving approval and source boundaries. When required, a deterministic date parser produces `PartialDate`, evidence identifies supported claims at the required precision, and provenance distinguishes source facts, OCR corrections, and user additions.

## TD-011: Cross-Domain Capability Composition

- **Status**: `accepted`
- **Location**: `src/mementoagent/workflows/` and `src/mementoagent/capabilities/`
- **Current state and impact**: The Memento harness and semantic tools compose the first achievement domain around the minimal Agent. There is still no capability registry, generic context, or coordinator.
- **Reason deferred**: A second domain has not demonstrated a shared composition requirement; introducing a generic coordinator now would add unnecessary abstraction.
- **Review trigger**: When a second domain requires shared approval, dependency, or materialization behavior.
- **Completion criteria**: Concrete domains compose tools through the minimal Agent without domain imports in `agents/`; any shared abstraction addresses demonstrated reuse and defines ownership and failure behavior.

## TD-007: Grow the Minimal Agent Incrementally

- **Status**: `in-progress`
- **Location**: `src/mementoagent/agents/`
- **Current state and impact**: `Agent.run()` owns a bounded synchronous Responses API tool loop and uses an explicit in-memory `Conversation` for complete replay history. `Agent.run_structured()` provides one-shot Pydantic extraction. `Tool` uses the SDK Pydantic helper for declarations, validates arguments, and returns model-visible error outputs for validation and handler failures. The first achievement vertical slice is available through the application harness and line-oriented `memento chat`. A failed turn is not committed, even if a prior tool side effect succeeded, so callers can lose the conversational trace of an operation that already changed external state and may duplicate it if they retry blindly. Streaming, persistence, resume, context compression, cancellation, async execution, handoffs, nested budgets, and observability remain absent.
- **Reason deferred**: The user requested a substantially smaller implementation to understand before adding features. No advanced capability or test migration should be restored merely for compatibility.
- **Review trigger**: Before integrating non-idempotent tools that can run before a later model/API failure; and when a concrete use requires streaming, persistence/resume, context compression, cancellation, async execution, handoffs, nested budgets, or observability.
- **Completion criteria**: Each approved extension is introduced independently with a readable contract. Before non-idempotent application tools are integrated, failed-turn recovery or idempotency is defined so retries cannot silently duplicate side effects. Obsolete tests are migrated or replaced only with explicit user approval, and full-project checks become meaningful again after paused integrations are addressed. No compatibility wrappers recreate the deleted framework.

## TD-012: TUI and Slash Command Adapter

- **Status**: `accepted`
- **Location**: `src/mementoagent/cli.py` and the future TUI adapter
- **Current state and impact**: The repository exposes deterministic
  `memento check` and a thin line-oriented `memento chat --workspace` adapter.
  There is no terminal renderer, streaming output, or slash command dispatcher.
- **Reason deferred**: TUI rendering and slash commands require a concrete
  interaction design; the current chat adapter is intentionally minimal.
- **Review trigger**: When users need `/init`, `/check`, streaming rendering,
  or a persistent terminal conversation.
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
