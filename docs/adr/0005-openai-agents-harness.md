# ADR-0005: Use a Local Harness Around the OpenAI Agents SDK

## Status

Superseded by [ADR-0006](0006-self-hosted-openai-runtime.md)

## Context

Memento needs a stable execution boundary for Agent tasks before it adds
multiple tasks or subagents. The current achievement extraction task already
has a typed Pydantic output and source-level post-processing, but the project
does not need to implement its own model runner, tool protocol, or multi-agent
loop.

The OpenAI Agents SDK separates an Agent's task declaration from the Runner
that executes it. It also supports exposing bounded specialist Agents as
tools to a manager Agent. Memento needs those capabilities eventually, while
retaining control over source provenance and the domain models returned to the
rest of the application.

## Decision (superseded)

Use the OpenAI Agents SDK as the Agent runtime behind a local Memento Harness.

The local `BaseAgent` declares a task's name, instructions, structured output
type, input conversion, optional model override, and optional child Agents.
`AgentHarness` constructs the SDK Agent and runs one synchronous turn with a
turn limit of one. It validates the structured output and returns only the
task's typed result; SDK run results, usage, and traces are not part of the
Memento public contract.

Child Agents are composed by the parent task and exposed through the SDK's
`agents-as-tools` pattern. The manager retains control of the user-facing
conversation. Handoffs, ReAct loops, sessions, durable run state, and concrete
subagent implementations remain outside this stage.

Tracing is disabled by default because parse snapshots and achievement data
may contain personal documents. Runtime configuration receives credentials and
optional endpoints from the caller; the library does not load `.env` files.

The unused custom provider base and provider wrappers are removed rather than
maintained as a second model execution path.

## Consequences

- Achievement extraction can reuse a mature Agent runtime without exposing
  SDK-specific results to workspace and schema code.
- Future tasks can be added by declaring a typed `BaseAgent` and composing
  bounded subagents without introducing a global mutable registry.
- The first Harness remains small and deterministic, which keeps its behavior
  testable with a fake SDK model.
- A future runtime expansion must define state, handoff, observability, and
  sensitive-data policies before adding those capabilities.

## Future trigger

Add sessions, handoffs, durable execution, or concrete subagents only when a
second task demonstrates that one-turn manager execution cannot express the
required workflow.
