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

## Achievement Extraction

`AchievementExtractor` runs as the first task through the local Agent Harness. It reads a `ParseSnapshot` and returns an in-memory structured achievement draft. Document-supported facts are validated with the `AchievementItem` schema, and the source hash comes from snapshot metadata. The draft may also contain one optional `description_suggestion` with candidate text and a rationale. This is an unconfirmed proposal, separate from `data.description`; it must not invent personal responsibilities, impact, or metrics. Event dates are not included yet because date interpretation belongs in deterministic code. The extractor does not create or save a record; approval and record materialization are separate steps.

## Agent Harness

The project uses the OpenAI Agents SDK as its runtime, behind a small local Harness. A task Agent declares its instructions, structured output type, input conversion, and optional subagents. The Harness owns one synchronous model run, output validation, error boundaries, and runtime configuration, then returns only the task's typed output. It does not expose the SDK run result to domain code.

Subagents are reserved for future bounded specialist tasks. The planned manager pattern keeps the user-facing Agent in control and exposes specialists through `agents-as-tools`; handoffs, ReAct loops, sessions, and concrete subagent implementations are not part of the current implementation.

## Achievement Draft Review

The user reviews a draft through the Agent conversation. The Agent turns a natural-language reply such as confirmation, a field correction, a description edit, or rejection into a structured `AchievementReviewDecision`. The review module validates that decision and returns an in-memory reviewed draft while preserving the original extracted draft. User corrections remain separate from source-supported facts, and the review module does not create or save a record. Natural-language interpretation, CLI presentation, and draft-to-record conversion remain separate work.

## MinerU Parser Configuration

The MinerU parser accepts an API key and an optional API base URL from its caller. The base URL is resolved in this order:

```text
explicit api_base_url argument
    > MEMENTO_MINERU_API_BASE_URL
    > https://mineru.net/api/v4
```

Set `MEMENTO_MINERU_API_BASE_URL` when using a private MinerU deployment or a different endpoint. The application entry point may call `load_dotenv()` before constructing the parser; the parser library itself does not load `.env` files. The HTTP transport only sends requests, while the MinerU adapter owns authentication, polling states, signed upload URLs, and result handling.

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
