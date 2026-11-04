# ADR-0002: Keep Description Suggestions Separate from Extracted Facts

## Status

Accepted

## Context

An achievement document can support facts such as the title, issuing
organization, and award level, but it usually cannot describe the user's
personal responsibilities, effort, or impact. At the same time, asking users
to write every description from scratch makes the workflow unnecessarily
demanding.

## Decision

The achievement extractor may return one optional `description_suggestion`
alongside the document-supported `AchievementItem` data. A suggestion contains
candidate text and a short rationale, is based only on the current parse
snapshot and extracted data, and remains an unconfirmed proposal.

The suggestion is never copied into `AchievementItem.description` by the
extractor. It must not assert personal responsibilities, impact, metrics, or
other facts absent from the source. When useful wording needs information the
source does not provide, the suggestion must leave that information as an
explicit prompt or placeholder. If no safe suggestion is possible, the field
is `None`.

## Consequences

- The draft can offer useful wording without presenting it as a source-backed
  fact.
- A future review workflow must visibly distinguish suggestions and require
  user acceptance before applying one to a record.
- Suggestions are not persisted or treated as evidence in this stage.
- Formal record creation, user review, and deterministic date processing
  remain separate work.
