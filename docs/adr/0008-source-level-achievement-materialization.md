# ADR-0008: Materialize Approved Achievements with Source-Level Provenance

## Status

Accepted

## Context

Achievement extraction and conversational review produce an in-memory
`ReviewedAchievementDraft`. The workspace already stores typed TOML records and
validates that evidence sources exist, but the workflow needs a deterministic
boundary before persistence.

Some documents do not provide a useful organization for the user's intended
use. User corrections may repair OCR or parsing errors, while a description is
user-authored content. The current envelope has record-level provenance and
does not model field-level provenance.

## Decision

`materialize_achievement()` converts an approved reviewed draft into an
`achievement/1` `RecordEnvelope`. It generates a type-prefixed ULID and a
timezone-aware creation timestamp, preserves `document` provenance, and adds
one evidence item containing the original source hash with an empty
`supports` list. The empty list means that the record is source-traceable but
does not claim page, quote, or field-level grounding.

An accepted review description is copied into `data.description`; organization
may remain `None`. OCR corrections remain source-derived corrections and do
not change record provenance. Materialization does not infer whether a changed
field was corrected or supplemented.

The converter is pure and in memory. Callers explicitly invoke existing
`validate_record()` and `save_record()` functions. It does not parse dates,
interact with users, or add a field-level provenance model.

## Consequences

- Approved drafts can enter the existing TOML record pipeline.
- Records remain traceable to their original source without invented evidence.
- User-facing output can omit or rename low-value fields such as organization.
- Date parsing, page/quote evidence, and detailed claim provenance remain
  explicit future work.
