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

## Agent Runtime and Application Harness

The project uses the official OpenAI Python SDK behind a project-owned Agent
Runtime. `TaskSpec` declares one-shot structured tasks such as achievement
extraction. `AgentSession` and `run_turn()` provide local in-memory replay for
the user-facing conversational Agent. The Runtime owns the Responses request
loop, tool dispatch, execution limits, and error boundaries; it does not expose
SDK response objects, usage, or credentials to application code.

`workflows/harness.py` assembles the root `MementoAgent`, its workspace context,
and semantic capability tools. The model decides which capability to call and
when to stop. `capabilities/achievement/` contains deterministic domain
operations and the structured extraction task; it does not own the user
conversation or a fixed source-to-record sequence.

The same Agent can read existing memory through the read-only `list_records`
and `get_record` tools. Lists contain generic envelope metadata and
type-specific summaries; a single-record lookup returns the complete raw TOML
structure, including records whose payload schema is not implemented yet. Read
operations do not load parse content or source files and do not modify the
workspace.

Tools use explicit `ToolSpec` declarations. Bounded subagents remain a future
composition point. Persistent sessions, handoffs, ReAct orchestration,
asynchronous execution, and concrete subagent implementations are not part of
the current implementation.

Use `AgentRuntime` as a context manager when it creates its own OpenAI client:

```python
from mementoagent.agents import AgentRuntime
from mementoagent.capabilities.achievement import extract_achievement

with AgentRuntime(model=model, api_key=api_key) as runtime:
    draft = extract_achievement(runtime, snapshot)
```

Create one `MementoAgent` for a user conversation. It receives ordinary user
messages, chooses capability tools, and can stop after inspection or extraction
without creating a record. The application does not prescribe a fixed
source-to-record sequence.

```python
from mementoagent.agents import AgentRuntime
from mementoagent.workflows import MementoAgent

with AgentRuntime(model=model, api_key=api_key) as runtime:
    agent = MementoAgent(
        workspace_root,
        parser,
        runtime,
    )
    turn = agent.send("Process the certificate in my inbox.")
    print(turn.text)
```

The extraction capability reads a `ParseSnapshot` and returns an in-memory
`AchievementDraft`. Document-supported facts are validated with the
`AchievementItem` schema, and the source hash comes from snapshot metadata. A
draft may contain one optional `description_suggestion`; it is an unconfirmed
proposal and must not invent personal responsibilities, impact, or metrics.
Organization is optional because some credentials do not need a useful issuer
value. Event dates are not included yet because date interpretation belongs in
deterministic code.

When the user explicitly confirms a complete `AchievementItem`, the Agent can
call the achievement save capability. Materialization preserves record-level
`document` provenance, uses the original source hash as evidence with an empty
`supports` list, and writes the accepted description into `data.description`.
The capability then reuses `validate_record()` and `save_record()`.

Future TUI input will keep slash commands such as `/init` and `/check` in a
deterministic outer command layer. Ordinary natural-language input will be
forwarded to `MementoAgent.send()`; the Runtime does not depend on terminal
rendering.

Timeline views are intentionally deferred. Record reads preserve `occurred`
and `created_at`, while event ordering and fallback behavior remain undefined
until deterministic date handling is implemented.

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
