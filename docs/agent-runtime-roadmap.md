# Agent Runtime Roadmap

This document records the data-modeling patterns that Memento can borrow from
production coding agents without adopting their full complexity.

## Patterns To Borrow

### Separate the data lifecycles

- A `Tool` is a static capability declaration and local executor.
- A `FunctionCall` is one model proposal, identified by `call_id`.
- A `FunctionCallOutput` is the result returned for that call.
- Conversation history stores replayable Responses input items.
- Runtime events are a separate projection for CLI and TUI clients.
- A session owns history and configuration; a turn owns one user request and
  its temporary model/tool counters.

Codex models Responses items as tagged protocol variants, keeps input items
replayable, and exposes a separate event queue to clients:

- [Codex Responses item models](https://github.com/openai/codex/blob/main/codex-rs/protocol/src/models.rs)
- [Codex protocol queues](https://github.com/openai/codex/blob/main/codex-rs/docs/protocol_v1.md)
- [Codex agent loop](https://openai.com/index/unrolling-the-codex-agent-loop/)

Claude Code exposes the same boundaries through persisted transcripts and
structured lifecycle hooks. Its public session contract restores messages,
tool calls, results, and session state; its hooks receive structured tool and
session data independently of the transcript:

- [Claude Code sessions](https://code.claude.com/docs/en/sessions)
- [Claude Code hooks](https://code.claude.com/docs/en/hooks)
- [Claude Code subagents](https://code.claude.com/docs/en/sub-agents)

## Current Memento Boundary

The current implementation keeps the synchronous tool loop intentionally
small:

- `Tool` owns schema generation, argument validation, handler execution, and
  result serialization.
- `Conversation` owns replay history and exposes snapshots rather than its
  private storage.
- `Agent.run()` owns model requests, tool dispatch, `call_id` pairing, and the
  per-call request limit.
- The CLI and Memento workflow remain outside the generic Agent package.

Each completed model response and its ordered tool outputs are committed as a
single replayable history unit. A failed later request preserves completed
units but does not record function calls whose tools were not executed.

## Development Order

1. Add streaming runtime events without mixing events into replay history.
2. Add context-window accounting and an explicit compaction boundary.
3. Add persisted sessions and resume after the in-memory contract is stable.
4. Add approval policies, subagents, handoffs, or asynchronous execution only
   when a concrete capability requires them.

Memento-specific capabilities, timeline views, and richer record behavior must
consume these generic boundaries rather than moving domain logic into
`agents/`.
