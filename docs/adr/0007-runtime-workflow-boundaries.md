# ADR-0007: Separate Generic Runtime, Capability Code, and Agent Harness

## Status

Superseded by [ADR-0009](0009-agent-centered-application-harness.md)

## Context

The previous design put achievement extraction, conversational review, and a
fixed source-to-record pipeline in a workflow package. Although generic Runtime
code stayed separate, the workflow still owned the order of operations and
reduced the model to a participant inside a scripted process.

Memento needs the model to control user-facing tool selection while keeping
workspace mutation, schema validation, and record materialization deterministic.

## Decision

The architecture has three separate layers:

- `agents/` contains generic Runtime infrastructure, task declarations,
  sessions, and tool protocols. It must not import domain capabilities.
- `capabilities/achievement/` contains achievement schemas used only during
  extraction and deterministic materialization. It provides operations that an
  Agent may call; it does not own a user conversation.
- `workflows/harness.py` assembles the root `MementoAgent`, per-conversation
  context, and semantic capability tools. It is an application harness, not a
  fixed source-to-record pipeline.

The root Agent decides whether to inspect the inbox, prepare a source, extract
facts, ask for clarification, or save a confirmed record. There is no generic
`run_achievement_workflow()` coordinator and no achievement-specific Agent
class.

A future TUI remains an outer adapter. Slash commands such as `/init` and
`/check` are dispatched deterministically; ordinary natural-language input is
sent to the Agent session.

## Consequences

- Adding a second domain can reuse the Runtime and session without adding a
  specialized class to `agents/`.
- Deterministic capability functions remain easy to test independently from
  model behavior.
- The model can stop after inspection or extraction instead of always creating
  a record.
- Persistent sessions, handoffs, concrete subagents, and additional workflow
  composition remain deferred until a concrete use case requires them.
