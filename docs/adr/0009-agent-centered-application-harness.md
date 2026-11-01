# ADR-0009: Give the Root Agent Control of Application Workflows

## Status

Accepted

## Context

Memento previously exposed a fixed achievement pipeline that imported a source,
parsed it, extracted an achievement, reviewed it, materialized a record, and
saved it in one Python function. That flow was useful for testing the individual
steps, but it did not provide a user-facing Agent that could interpret intent,
choose tools, pause for confirmation, or stop after inspection.

The project may later expose the same Agent through a TUI. The interaction
adapter must therefore remain separate from the model loop and workspace
capabilities.

## Decision

Use a root `MementoAgent` as the application control layer. The Agent receives
ordinary user messages through an in-memory `AgentSession` and chooses semantic
capability tools. The Runtime owns the Responses API loop, tool execution,
conversation history, limits, and safe events.

Achievement extraction remains a one-shot structured capability. Materialization
and saving remain deterministic capability operations. The root Agent submits a
complete confirmed `AchievementItem`; source identity, provenance, evidence, and
record identity are supplied or validated by application code.

The root Agent also exposes read-only `list_records` and `get_record` tools.
`list_records` returns generic envelope metadata plus a small projection for
known record types. `get_record` returns the raw TOML structure so records with
future or unknown payload schemas remain inspectable without weakening the
typed loading contract used by known application code. These tools do not read
parse snapshots or source files and do not mutate the workspace.

The `workflows/` package contains the application harness that composes the
Agent and its context. Domain operations live under `capabilities/`. A fixed
`run_achievement_workflow()` entry point is removed so Python does not prescribe
an order that the Agent should control.

TUI and CLI adapters remain outside the Agent Runtime. A future TUI dispatches
slash commands such as `/init` and `/check` directly to deterministic command
handlers and forwards ordinary text to `MementoAgent.send()`.

## Consequences

- The Agent can inspect, extract, clarify, save, or stop according to user
  intent.
- Existing records can be listed and inspected without requiring a second
  payload schema or a separate read-only Agent.
- Domain capabilities remain reusable and deterministic without becoming
  specialized Agent classes.
- The first session implementation is process-local and non-persistent.
- Tool failures are reported to the model through sanitized results so it can
  explain the problem or ask for another input; no automatic retry policy is
  added.
- TUI rendering, slash command registration, persistent sessions, handoffs,
  subagent orchestration, and asynchronous execution remain future work.
- Timeline views remain future work. Record summaries preserve `occurred` and
  `created_at`, but this decision does not define event ordering or fallback
  behavior when `occurred` is absent.
