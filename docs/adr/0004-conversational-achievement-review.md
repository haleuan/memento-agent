# ADR-0004: Let the Root Agent Handle Achievement Confirmation

## Status

Superseded by [ADR-0009](0009-agent-centered-application-harness.md)

## Context

Achievement extraction produces document-supported facts and may produce a
separate description suggestion. Users should be able to confirm, correct,
edit, or reject these values through natural language without a field-editing
UI.

The earlier implementation embedded an `ask_user` callback inside a dedicated
achievement review workflow. That made the review function the owner of the
conversation and encouraged a fixed sequence of extraction, review, and save.

## Decision

The root `MementoAgent` owns the conversation. It receives the structured
`AchievementDraft` returned by the extraction capability, explains the facts
and suggestion in its own words, asks focused questions when needed, and
submits a complete `AchievementItem` to the save capability only after clear
user confirmation.

The application does not hard-code a summary, menu, or language-specific
review prompt. Source identity and record provenance remain outside the model.
The materialization capability copies an accepted description into
`data.description`, preserves the original source hash, and keeps record-level
`document` provenance.

There is no separate `AchievementReviewDecision`, `ReviewedAchievementDraft`,
`AchievementReviewAgent`, or `ask_user` tool in the application path.

## Consequences

- User interaction is part of the general Agent conversation rather than a
  domain-specific callback loop.
- The Agent can stop after inspection or extraction and does not have to save a
  record.
- Deterministic materialization remains independent of natural-language
  interpretation.
- Persistent sessions, explicit approval state, richer provenance, and TUI
  presentation remain future work.
