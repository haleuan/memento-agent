# ADR-0008: Materialize Confirmed Achievements with Source-Level Provenance

## Status

Accepted

## Context

Achievement extraction returns an in-memory `AchievementDraft`. The root Agent
may edit the facts or add a user-authored description during conversation. The
workspace stores typed TOML records and validates that evidence sources exist,
but the conversion from a confirmed Agent result to a record must remain
deterministic.

Some documents do not provide a useful organization. User corrections may
repair OCR or parsing errors, while descriptions contain user-authored context.
The current envelope has record-level provenance and does not model field-level
provenance.

## Decision

`materialize_achievement()` accepts the original `AchievementDraft` and a
complete confirmed `AchievementItem`. It generates a type-prefixed ULID and a
timezone-aware creation timestamp, preserves `document` provenance, and adds
one evidence item containing the original source hash with an empty
`supports` list.

The empty list means that the record is source-traceable but does not claim
page, quote, or field-level grounding. The source hash always comes from the
original draft; the Agent cannot replace it. An accepted description is stored
in `data.description`, and `organization` may remain `None`.

The converter is pure and in memory. The save capability explicitly invokes
`validate_record()` and `save_record()`. Materialization does not parse dates,
interact with users, or add a field-level provenance model.

## Consequences

- Confirmed Agent output can enter the existing TOML record pipeline.
- Records remain traceable to their original source without invented evidence.
- User-facing output can omit or rename low-value fields such as organization.
- Date parsing, page/quote evidence, and detailed claim provenance remain
  explicit future work.
