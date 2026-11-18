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
- `AgentEvent` exposes synchronous progress notifications and visible text
  increments without storing events in replay history or exposing tool payloads.
- The CLI and Memento workflow remain outside the generic Agent package.

Each completed model response and its ordered tool outputs are committed as a
single replayable history unit. A failed later request preserves completed
units but does not record function calls whose tools were not executed.

## Streaming And Events

`Agent.run(..., stream=True, on_event=...)` consumes typed events from
`client.responses.create(..., stream=True)` and still returns the final response
text. The callback receives `model_request`, `text_delta`, `tool_call`, and
`tool_result` notifications. A returned tool result can contain an error;
`tool_result` does not indicate business success. Without streaming, the callback
still receives model-request and tool-stage notifications.

Only `response.output_text.delta` becomes visible text. The complete `Response`
comes from `response.completed`, so the runtime does not assemble argument
deltas or execute partial tool calls. Both request modes share the existing
budget check, sequential dispatch, and complete-prefix history commits.

Failed or incomplete streams raise an error without committing their partial
output. Text already displayed is provisional. SDK and callback exceptions
propagate, and tool side effects are not rolled back. Callbacks run synchronously;
there is no event bus or asynchronous executor.

The CLI renders text to stdout and progress to stderr. `memento chat` enables
streaming by default; `--no-stream` prints complete replies instead. Run failures
return to the input prompt without an automatic retry. Ctrl-C and EOF exit the
chat; this does not provide hard cancellation of synchronous tool operations.

Protocol references:

- [Streaming API responses](https://developers.openai.com/api/docs/guides/streaming-responses)
- [Responses streaming events](https://developers.openai.com/api/reference/resources/responses/streaming-events)

## Development Order

1. Streaming runtime events, separate from replay history: implemented.
2. Add persisted sessions and resume after the in-memory contract is stable.
3. Add context-window accounting and an explicit compaction boundary.
4. Add approval policies, subagents, handoffs, or asynchronous execution only
   when a concrete capability requires them.

Memento-specific capabilities, timeline views, and richer record behavior must
consume these generic boundaries rather than moving domain logic into
`agents/`.
