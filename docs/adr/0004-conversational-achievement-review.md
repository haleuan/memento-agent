# ADR-0004: Keep Achievement Review Conversational and Structured at the Boundary

## Status

Accepted

## Context

Memento should minimize the amount of information users have to type. The
user-facing workflow is a conversation with an Agent, while a CLI may present
more context than a chat web interface. Requiring users to edit individual
fields through a form or a sequence of UI controls would make the review flow
more complicated than the task requires.

The Agent can understand replies such as confirmation, a correction to an
organization name, a revised description, or rejection. The application still
needs a deterministic boundary that validates the resulting decision and keeps
document-supported values separate from user corrections.

## Decision

The review boundary accepts a structured `AchievementReviewDecision` produced
by the Agent conversation. It does not parse natural language and does not
provide a CLI or UI interaction loop.

An approved decision may reuse the extracted `AchievementItem` or provide a
complete user-corrected value. The resulting in-memory reviewed draft keeps the
original `AchievementDraft` alongside the reviewed value. A description remains
separate from `AchievementItem.description` until a future materialization step
decides how user-authored content enters a record.

A rejected decision returns a rejected in-memory result and cannot produce
reviewed data. The source hash is always retained from the original draft and
cannot be supplied by the Agent.

## Consequences

- Users can confirm, correct, or reject a draft in one natural-language turn.
- The review module stays small, deterministic, and testable without a chat
  provider or interactive UI.
- User-corrected facts are not silently treated as document-supported facts.
- A future record conversion must define provenance and evidence semantics for
  corrections before saving a TOML record.

## Future trigger

Add a conversation adapter or CLI presentation when a user-facing workflow
needs to render drafts and translate replies into
`AchievementReviewDecision`. Add record materialization only after date parsing,
provenance, evidence, and persistence contracts are defined.
