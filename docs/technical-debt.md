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
- **Location**: `src/mementoagent/workflows/achievement/`
- **Current state and impact**: Achievement extraction returns an in-memory draft with source provenance and an optional description suggestion. The achievement review workflow starts a bounded natural-language review conversation, asks for clarification when needed, and produces a structured decision. The deterministic review function preserves original and reviewed values, but the flow still does not include occurrence dates, create a `RecordEnvelope`, generate record metadata, write evidence, or save a TOML record. Reviewed data therefore still needs a separate materialization path before entering the workspace.
- **Reason deferred**: Conversational interpretation and deterministic application are now isolated from persistence. Date interpretation must remain deterministic, and draft-to-record conversion, provenance for user corrections, evidence generation, and saving need their own explicit contract.
- **Review trigger**: Before a user-facing workflow needs to date or persist an approved reviewed achievement.
- **Completion criteria**: Raw date text is passed through a deterministic parser into `PartialDate`; a deterministic draft-to-record conversion distinguishes source-supported values from user corrections, creates envelope metadata and source-level evidence, and persists only an approved record, with tests.

## TD-011: General Workflow Orchestration

- **Status**: `accepted`
- **Location**: `src/mementoagent/workflows/` and `src/mementoagent/agents/`
- **Current state and impact**: The generic Runtime executes declarative task specifications, while achievement extraction and review live in a workflow package. There is no general workflow coordinator for composing multiple domain tasks, managing shared user conversations, or materializing results across record types.
- **Reason deferred**: Only the achievement workflow currently exists. A coordinator abstraction would be speculative until a second domain workflow demonstrates shared sequencing or state requirements.
- **Review trigger**: When a second domain workflow needs to compose extraction, user review, provenance handling, or record materialization with the achievement workflow.
- **Completion criteria**: A workflow coordinator has an explicit input, state, error, and ownership contract; generic Runtime code remains independent of workflow modules; and at least two workflows exercise the shared orchestration through offline tests.

## TD-007: Expand the Agent Runtime Beyond One Structured Turn

- **Status**: `accepted`
- **Location**: `src/mementoagent/agents/task.py`, `src/mementoagent/agents/runtime.py`, and `src/mementoagent/agents/tools.py`
- **Current state and impact**: The project-owned Runtime uses the OpenAI Python SDK for Pydantic schema adaptation and structured response parsing, while owning the synchronous Responses request loop, in-memory state, and bounded function-tool execution. Subagent tools accept string input, but no concrete subagent workflow exists. It does not persist sessions, resume interrupted runs, compress long contexts, perform handoffs, expose production observability, or define shared execution budgets for nested runs.
- **Reason deferred**: The current extraction task only needs a bounded synchronous run. Durable state, richer context management, handoffs, and asynchronous execution would enlarge the runtime contract before a concrete workflow requires them.
- **Review trigger**: When a task needs a real subagent, multi-turn conversation state, human interruption/resume, long-context management, handoff ownership, asynchronous execution, or production run observability.
- **Completion criteria**: Each required capability has an explicit state and failure contract, and an end-to-end task has offline tests for execution limits, nested run budgets, resumption, subagent boundaries, context management, and sensitive-data handling.

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
- **Current state and impact**: The review Agent implementation and its directly updated documentation use English, but older test fixtures and schema examples still contain Chinese text. This makes the repository language convention inconsistent and can obscure whether non-English text is test data or an application message.
- **Reason deferred**: The current change is limited to the review Agent's conversation boundary. A repository-wide text migration would touch unrelated fixtures and examples without changing runtime behavior.
- **Review trigger**: Before publishing the repository as an English-only reference implementation or when another broad documentation/code cleanup is scheduled.
- **Completion criteria**: All Python source, tests, Markdown documentation, and schema example strings are English, while user-provided sample documents remain explicitly marked as data or excluded from the source-language policy; scans enforce the chosen boundary.
