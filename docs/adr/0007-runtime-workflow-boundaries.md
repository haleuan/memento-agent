# ADR-0007: Separate Generic Agent Runtime from Domain Workflows

## Status

Accepted

## Context

The `agents` package previously contained both generic Runtime infrastructure
and achievement-specific extraction and review classes. This made domain task
code appear to be reusable Agent infrastructure and encouraged adding another
specialized Agent class for every new task.

The project needs a reusable execution mechanism, while task-specific prompts,
schemas, user conversations, and deterministic post-processing belong to the
workflow that owns the domain semantics.

## Decision

Keep `agents` limited to the generic `AgentTask` protocol, immutable `TaskSpec`,
`AgentRuntime`, and `ToolSpec`. A Runtime may execute any task satisfying the
protocol and must not import workflow modules.

Move achievement extraction and conversational review into
`workflows/achievement/`. They expose workflow functions and module-level task
specifications instead of `AchievementExtractor` or `AchievementReviewAgent`
classes. Their transient Pydantic models remain workflow contracts and stay
separate from persisted models in `schema/`.

The project makes this migration directly without compatibility re-exports for
the removed achievement Agent classes. Internal callers and tests use the new
workflow APIs.

## Consequences

- The generic Runtime can be reused by future domains without importing their
  schemas or orchestration rules.
- Achievement-specific prompts, tools, and post-processing remain cohesive in
  one workflow package.
- Adding a new domain requires a task specification and workflow function,
  rather than another class in the generic `agents` package.
- A general cross-domain workflow coordinator remains deferred until a second
  domain demonstrates the need.
