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

The achievement workflow runs a declared extraction task through the project's local Agent Runtime. It reads a `ParseSnapshot` and returns an in-memory structured achievement draft. Document-supported facts are validated with the `AchievementItem` schema, and the source hash comes from snapshot metadata. The draft may also contain one optional `description_suggestion` with candidate text and a rationale. This is an unconfirmed proposal, separate from `data.description`; it must not invent personal responsibilities, impact, or metrics. Event dates are not included yet because date interpretation belongs in deterministic code. The workflow does not create or save a record; approval and record materialization are separate steps.

## Agent Runtime

The project uses the official OpenAI Python SDK behind a small local Runtime. A generic `TaskSpec` declares instructions, structured output type, input conversion, and optional tools or subagents. The SDK adapts Pydantic schemas and parses structured responses; the Runtime owns the synchronous request loop, in-memory run state, tool dispatch, execution limits, and error boundaries. It returns only the task's typed output and does not expose SDK response objects, usage, or credentials to workflow code.

Tools use explicit `ToolSpec` declarations. A manager can compose future bounded subagents as internal tools, while the manager retains control of the conversation. Session persistence, handoffs, ReAct orchestration, asynchronous execution, and concrete subagent implementations are not part of the current implementation.

Use `AgentRuntime` as a context manager when it creates its own OpenAI client:

```python
from mementoagent.agents import AgentRuntime
from mementoagent.workflows.achievement import extract_achievement

with AgentRuntime(model=model, api_key=api_key) as runtime:
    draft = extract_achievement(runtime, snapshot)
```

## Achievement Draft Review

The achievement review workflow gives the model a structured draft containing the extracted facts, source identifier, and any description suggestion. The model must use the `ask_user` tool to generate the opening summary and review prompt, then can ask focused follow-up questions when the reply is ambiguous. It accepts natural-language confirmation, field corrections, description edits, or rejection. The workflow returns a structured `AchievementReviewDecision`; deterministic review logic applies it and returns an in-memory reviewed draft while preserving the original extracted draft. User corrections and description text remain separate from source-supported facts. This step does not create or save a record, and it is a conversation boundary rather than a CLI or UI workflow.

## MinerU Parser Configuration

The MinerU parser accepts an API key and an optional API base URL from its caller. The base URL is resolved in this order:

```text
explicit api_base_url argument
    > MEMENTO_MINERU_API_BASE_URL
    > https://mineru.net/api/v4
```

Set `MEMENTO_MINERU_API_BASE_URL` when using a private MinerU deployment or a different endpoint. The application entry point may call `load_dotenv()` before constructing the parser; the parser library itself does not load `.env` files. The HTTP transport only sends requests, while the MinerU adapter owns authentication, polling states, signed upload URLs, and result handling.

```python
from mementoagent.parsers import MineruParser

with MineruParser(api_key=api_key) as parser:
    content = parser.parse(source_path)
```

`AgentRuntime`, `MineruParser`, and `HttpxTransport` provide `close()` and context managers. Each closes only the resources it creates. The caller remains responsible for closing an injected client or transport; a parser or runtime can reuse its connections across multiple calls inside the context.

MinerU's `timeout` is a time budget checked between stages and before returning a successful result. Requests use the remaining budget for their waiting time, capped by the adapter's per-request timeout. This does not forcibly interrupt an in-flight synchronous request; a stage that finishes after the deadline is rejected rather than returned as a success.

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

Pyright currently uses `standard` mode. Ruff checks docstrings, basic errors, unused imports, and import ordering (`D`, `E4`, `E7`, `E9`, `F`, and `I`).
