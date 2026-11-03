# ADR-0006: Own the Agent Runtime on the OpenAI Python SDK

## Status

Accepted; the manually implemented loop and replay-history policy below are
superseded by the manual Responses API loop and explicit Conversation policy in
[ADR-0010](0010-agent-first-runtime-foundation.md). The current directory
layout and public interfaces are defined by ADR-0010.

## Context

Memento is intended to be a usable Agent system and an inspectable example of
Agent runtime engineering. The project therefore uses the official `openai`
Python SDK for transport and Responses API types while keeping the execution
loop and application boundaries in the repository.

The earlier Runtime combined structured tasks, conversations, streaming,
subagents, context injection, and client lifecycle management. Its overlapping
protocols and adapters obscured the basic tool loop. The current priority is to
make the complete implementation understandable before adding capabilities.

## Decision

The original decision was to own a small manual Responses API loop rather than
adopt a second orchestration framework. Its concrete current interfaces,
including layered `runtime/` and `conversation/` packages, explicit
`Conversation` history, model-visible tool failures, and commit-on-completed
turn semantics, are superseded by [ADR-0010](0010-agent-first-runtime-foundation.md).

The historical transport boundary remains: the caller creates and closes the
OpenAI client, while Agent code does not construct clients, read credentials,
or own transport configuration.

## Consequences

- The model controls the order in which application capabilities run.
- The complete execution path is readable in `Tool`, `Conversation`, and
  `Agent.run()`.
- Existing Memento extraction and application integration are retained but
  paused; they still reference deleted APIs. Package initializers no longer
  import those modules automatically.
- Deterministic materialization, workspace I/O, parsers, validation, and the
  check CLI remain independent and usable.
- The project depends on the official OpenAI Python SDK rather than adopting a
  second Agent orchestration framework.
- Domain provenance remains the responsibility of later integration, not the
  generic Agent loop.

## Rejected alternative

Using the OpenAI Agents SDK as the core runtime would provide mature loop and
tool abstractions, but would move the implementation of those mechanisms out
of this project. It remains a reference for design, not a runtime dependency.

## Future trigger

Add features individually when the minimal loop is understood and a concrete
use requires them. New or expanded tests require explicit user approval.
