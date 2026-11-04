# ADR-0001: Use Pure TOML for Structured Records

## Status

Accepted

## Context

Memento records primarily contain structured facts, provenance, evidence, dates,
and optional typed descriptions. The previous format combined YAML front matter
with an optional Markdown body. That format is useful for documents that are
edited as prose, but record data is read and validated as a structured object.

The project also stores parser output separately. That output may be long,
unstructured text and should remain available as raw Markdown content.

## Decision

Persist records as pure TOML files at
`records/<record-type>/<record-id>.toml`. Remove the generic free-form record
body and keep long descriptions in type-specific structured fields.

Persist parse snapshot metadata as `metadata.toml`, while keeping parser output
as the separate raw `content.md` file.

Use Python's `tomllib` for reading and `tomli-w` for writing. Do not provide
backward-compatible loading for the previous YAML front matter format.

## Consequences

- Record I/O no longer needs front matter delimiter handling.
- The `.toml` extension matches the complete record format.
- TOML's lack of a null value means optional fields with `None` are omitted
  when writing and restored by model defaults when loading.
- Existing YAML records must be migrated before they can be loaded.
- Raw parser text remains independent from structured record metadata.
