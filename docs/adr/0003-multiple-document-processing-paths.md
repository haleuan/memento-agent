# ADR-0003: Support Multiple Document Processing Paths

## Status

Accepted

## Context

Memento processes source files such as PDFs and images, but there is no single
document-processing technology that is appropriate for every source. MinerU is
the first parser adapter, but local OCR tools, other hosted services, and
vision-capable sub-agents may also be useful. Treating MinerU as the only
processing path would make the data flow harder to extend and would conflate
text transcription with semantic extraction.

The current workspace contract makes parse snapshots optional. When a parser
does produce reusable text, that text can be stored as `content.md` with
structured `metadata.toml`, while records continue to refer directly to the
original source hash.

## Decision

Memento supports multiple document-processing paths:

- A **parser or transcription path** converts a source file into reusable text.
  MinerU, local tools, other services, or a sub-agent may implement this path.
  When its output is suitable for reuse, the path may persist a
  `ParseSnapshot` containing `metadata.toml` and `content.md` through the
  existing parser interface.
- A **semantic extraction path** converts source content into structured
  application data such as an `AchievementDraft`. A vision-capable sub-agent
  may inspect an image or PDF directly and return structured data without
  pretending to be a `Parser` and without producing a parse snapshot.

Both paths must preserve source-level provenance. The source hash is supplied
and validated by application code; a model or remote service must not invent
or replace it. A parse snapshot is therefore a reusable intermediate result,
not a prerequisite for creating a source-linked draft or record.

The current implementation keeps MinerU as the only remote parser adapter and
does not implement the direct sub-agent path yet.

## Consequences

- New transcription providers can be added without changing record schemas or
  evidence rules.
- Direct vision extraction can be evaluated independently from text parsing
  when a document is short, visual, or poorly served by OCR.
- Consumers must distinguish parser output from agent-generated structured
  interpretation and must not treat either as user-approved record data.
- A direct extraction path may lack a reusable textual snapshot, so later
  consumers that need replayable text or quote context may require a separate
  transcription step.

## Future trigger

Implement a direct sub-agent processing path when a concrete source type or
workflow shows that obtaining a structured draft from the original document
is more reliable or cheaper than first producing a parse snapshot. At that
point, define its input contract, model/provider metadata, error behavior, and
tests while retaining source hash injection outside the model.
