# Memento Agent - Technical Specification

## Mission

Build a **provenance-backed personal memory assistant** for long-term record keeping. The first use case is achievement tracking for graduate students (awards, papers, projects, internships), but the architecture supports general memory types through a typed record system.

**Core principle**: Every factual claim must be traceable to either a source document, explicit user assertion, or agent inference—never fabricated. Verification is human-in-the-loop by design.

---

## Architecture Overview

### Storage Model: Three-Tier Separation

Data is organized by **recoverability** and **sensitivity**:

1. **Workspace** (user-chosen directory, git-backed):
   - Irreplaceable user data: original files, records, parse snapshots, audit ledger
   - Self-contained: uses only relative paths, relocatable across machines
   - Discovered like `.git` by walking up directory tree for `.memento/` marker

2. **Cache** (inside workspace, git-ignored):
   - Rebuildable artifacts: search indices, derived views
   - Lives at `.memento/cache/`

3. **User Config** (platform-specific, e.g. `~/.config/memento-agent`):
   - Machine-bound secrets: API tokens, default workspace pointer
   - Never committed to any repository

### Workspace Directory Structure

```
~/Memento/                              # User's workspace (example location)
├── AGENTS.md                           # This file (copied during init)
├── inbox/                              # Drop zone for new files
├── sources/                            # Content-addressed immutable originals
│   └── ab/
│       ├── ab12…ef.pdf                 # Named by SHA-256 hash
│       └── ab12…ef.json                # Sidecar metadata
├── records/                            # Memory ledger (one .toml per record)
│   └── achievement/
│       └── ach_01JBX7….toml
├── outputs/                            # Generated content with citations
└── .memento/                           # Tool internal state
    ├── workspace.toml                  # Config (no secrets)
    ├── parses/                         # Parse snapshots (not freely regenerable)
    │   └── <source_hash>/
    │       └── <parse_id>/
    │           ├── meta.json           # Engine, version, params, timestamp
    │           └── blocks.jsonl        # Normalized blocks
    ├── ledger.jsonl                    # Append-only audit log
    └── cache/                          # Disposable (git-ignored)
```

**Key Invariants**:
- `sources/` files are read-only after import
- Record IDs are stable (ULID-based), filenames can change
- Parse snapshots are immutable (re-parsing creates new parse_id)
- Workspace uses only relative paths (portable)
- `.memento/` marks workspace root (like `.git`)

---

## Core Data Structures

### 1. Source (Imported Original File)

**Location**: `sources/<first_two_chars_of_hash>/<full_hash>.<ext>`

**Sidecar** (`<hash>.json`):
```json
{
  "hash": "sha256:ab12…ef",
  "original_filename": "国家奖学金证书.pdf",
  "imported_at": "2025-01-12T09:30:00+08:00",
  "mime_type": "application/pdf",
  "size_bytes": 524288,
  "origin": "inbox",
  "sensitive": true
}
```

**Fields**:
- `hash`: Content-addressable identity (SHA-256)
- `original_filename`: Human-readable name preserved
- `imported_at`: When added to workspace
- `sensitive`: If true, requires explicit consent before API upload
- `origin`: Where it came from (inbox, URL, manual import)

### 2. ParsedBlock (Normalized Engine Output)

**Location**: `.memento/parses/<source_hash>/<parse_id>/blocks.jsonl`

Each line is a JSON object:
```json
{
  "id": "p0-b07",
  "page": 0,
  "bbox": [0.12, 0.34, 0.89, 0.45],
  "type": "text",
  "text": "授予张三同学在XX大学生程序设计竞赛中荣获省赛二等奖",
  "conf": 0.987
}
```

**Parse Metadata** (`meta.json` in same directory):
```json
{
  "parse_id": "p_20250112_093045",
  "source": "sha256:ab12…ef",
  "engine": "mineru-api",
  "version": "4.0",
  "params": {"tier": "standard", "language": "ch"},
  "parsed_at": "2025-01-12T09:30:45+08:00",
  "remote": true
}
```

**Normalization Rules**:
- `page`: 0-indexed integer
- `bbox`: `[x0, y0, x1, y1]` in relative coordinates (0.0 to 1.0), top-left origin
- `conf`: Optional confidence score (null if engine doesn't provide)
- `type`: `text | table | image | equation | ...`

**Critical Design Note**: Parse snapshots are **not freely regenerable**:
- Re-parsing costs API calls
- New engine versions may assign different block IDs
- Evidence pointers rely on block IDs remaining stable
- Therefore: each parse gets unique `parse_id`, stored as immutable snapshot

### 3. Record Envelope (Generic Container)

All records share this envelope structure. Type-specific data lives under `data:`.

**Location**: `records/<type>/<id>.toml` (pure TOML)

**Envelope Fields**:
```yaml
---
id: ach_01JBX7Q3M8K2N5R9V4W6Y0ZDEF   # Type prefix + ULID
schema: achievement/1                 # Type-specific schema version
provenance: document                  # document | user | agent
created_at: "2025-01-12T09:30:00+08:00"
occurred:                             # When the event happened in the world
  start: "2024-10"
  end: "2024-10"
data: { ... }                         # Type-specific payload (see below)
evidence: [ ... ]                     # Links to source documents (see below)
verification: null                    # Seal after human review (see below)
---

Freeform narrative goes here. This is for user's own description,
not machine-extracted facts. Generated outputs will label this as "self-reported".
```

**Field Descriptions**:

- **`id`**: Stable identifier (never changes even if title/filename changes)
  - Format: `<type_prefix>_<ULID>`
  - ULID: 26-char time-sortable base32 (e.g. `01JBX7Q3M8K2N5R9V4W6Y0ZDEF`)
  - Avoids sequential counters (which collide with concurrent writes)

- **`schema`**: `<type>/<version>` for schema evolution
  - Envelope changes separately from payload schema
  - Allows gradual migration

- **`provenance`**: Origin of the claim
  - `document`: Extracted from source files (must have evidence)
  - `user`: Explicitly asserted by user (evidence optional)
  - `agent`: Generated by AI (must remain unverified until human reviews)

- **`created_at`**: When this record was created (not when event occurred)
  - Always quoted string to avoid YAML date object coercion
  - ISO 8601 with timezone

- **`occurred`**: When the underlying event happened
  - `start` and `end` support ranges (e.g. "2023-2024学年")
  - Quoted strings (partial dates like "2024-10" stay as strings)
  - Can be null for facts without clear temporal bounds

- **`data`**: Type-specific payload (validated by type schema, not envelope)

- **`evidence`**: Array of links to source documents (see Evidence structure below)

- **`verification`**: Null until human reviews. Once sealed, contains:
  ```yaml
  verification:
    by: human              # Who verified (always "human" for now)
    at: "2025-01-12T10:00:00+08:00"
    sealed: "sha256:3f8a..."   # Hash of canonical critical fields
  ```

**Deliberately Absent Fields**:
- **No `status` field**: Derived from `verification` state, not stored
  - Computed by checker: `draft | verified | tampered`
- **No `review_flags`**: Computed on-demand by validation rules
  - Storing them would let them drift from reality

### 4. Achievement Type (First Concrete Type)

**Payload under `data:`**:
```yaml
data:
  kind: award              # award | paper | project | internship | certificate
  title: XX 大学生程序设计竞赛
  issuer: XX 竞赛组委会
  level_raw: 省赛二等奖    # Raw text from document, NOT normalized
  notes: 团队赛第一名        # Optional
```

**Critical Design Choice**: `level_raw` stays as **raw extracted text**:
- DO NOT normalize ("二等奖" vs "second prize" vs "2nd place")
- Different institutions use incomparable scales
- Normalization is inference, which must be explicit and human-reviewed
- Let generation layer decide how to phrase it per context

**Other Fields**:
- `kind`: Controlled vocabulary (small fixed set per type)
- `title`: Full official name
- `issuer`: Awarding organization (raw text, not canonicalized)
- `notes`: Optional free text

**Future Types** (not implemented yet, listed for context):
- `paper`: title, authors, venue, date, doi, citation_count
- `project`: title, role, duration, team_size, tech_stack
- `internship`: company, role, duration, responsibilities

### 5. Evidence (Source-to-Record Link)

**Structure** (array under `evidence:`):
```yaml
evidence:
  - source: sha256:ab12…ef       # Which original file
    parse: p_20250112_093045     # Which parse snapshot
    block: p0-b07                # Which block in that parse
    supports:                    # Which fields this backs up
      - data.title
      - data.issuer
      - data.level_raw
      - occurred
    quote: "授予张三同学在XX大学生程序设计竞赛中荣获省赛二等奖"
```

**Validation Rules**:
1. `source` must exist in `sources/`
2. `parse` must exist in `.memento/parses/<source>/<parse>`
3. `block` must exist in that parse's `blocks.jsonl`
4. `quote` must be substring of `block.text` (after whitespace normalization)
5. If `provenance: document`, at least one evidence entry required
6. If `provenance: agent`, must cite source record IDs (not implemented yet)

**Why `quote` is critical**:
- Substring check catches hallucinations deterministically
- LLM can't fabricate quotes without getting caught
- Even if LLM "fixes" an OCR typo, mismatch triggers review

---

## Validation Contract

The "contract" has **two halves**:

### 1. Shape Validation (Pydantic)

Define models for:
- `SourceMetadata`
- `ParseMeta` and `ParsedBlock`
- `RecordEnvelope` (generic)
- `AchievementData` (type-specific payload)
- `Evidence`, `Verification`

Located in: `src/mementoagent/schema/`

### 2. Cross-Field Invariants (Check Functions)

File: `src/mementoagent/commands/check.py`

**Invariants to enforce**:

1. **Evidence Grounding** (`provenance: document` only):
   - At least one evidence entry exists
   - Each `quote` is substring of `block.text` (normalize whitespace)
   - All referenced `source`, `parse`, `block` exist on disk

2. **Verification Seal**:
   - If `verification` present, recompute `sealed` hash from critical fields
   - Critical fields: `data` (full payload), `occurred`, `evidence`
   - Canonical form: sorted JSON keys, UTF-8, compact (no spaces)
   - Hash: SHA-256 hex digest
   - If mismatch: status = `tampered`, auto-demote to `draft`

3. **Provenance Rules**:
   - `provenance: agent` → must stay `verification: null` until human reviews
   - `provenance: user` → evidence optional
   - `provenance: document` → evidence required

4. **Critical Fields Review**:
   - For `achievement`: `data.level_raw`, `data.issuer`, `occurred` always flagged
   - Even if confidence high, human must visually confirm against source image
   - Reason: cost of error (wrong award level in application) outweighs cost of review

**Check Command Output**:
```bash
memento check records/achievement/ach_01JBX….toml

# Output:
Status: draft
Issues:
  - [ERROR] quote_mismatch: evidence[0].quote not found in block text
  - [WARN] critical_field: data.level_raw requires human review
  - [INFO] verification: not yet verified
```

**Exit Codes**:
- 0: All checks pass, status = verified
- 1: Errors present (quote mismatch, missing evidence, broken seal)
- 2: Warnings only (needs review, but structurally valid)

---

## Implementation Roadmap

### Already Exists (Scaffolding)
- `src/mementoagent/providers/`: LLM provider abstraction (OpenAI base)
- `src/mementoagent/agents/`: ReAct agent skeleton

### Phase 1: Core Data Layer (Priority: CRITICAL)

**Goal**: Make the data model real and testable.

**Deliverables**:
1. `src/mementoagent/schema/`:
   - `envelope.py`: `RecordEnvelope`, `Evidence`, `Verification` (Pydantic)
   - `achievement.py`: `AchievementData` (Pydantic)
   - `source.py`: `SourceMetadata` (Pydantic)
   - `parse.py`: `ParseMeta`, `ParsedBlock` (Pydantic)
   - `__init__.py`: Export all schemas with version constants

2. `src/mementoagent/workspace/`:
   - `discovery.py`: Find workspace root (walk up for `.memento/`)
   - `paths.py`: Standardized path helpers (sources_dir, records_dir, etc.)
   - `config.py`: Read/write `workspace.toml`

3. `src/mementoagent/validation/`:
   - `shape.py`: Pydantic model loading from TOML
   - `invariants.py`: Evidence grounding, seal verification, provenance rules
   - `seal.py`: Compute canonical hash of critical fields

4. `src/mementoagent/commands/`:
   - `check.py`: CLI command implementing validation contract
   - Exit codes: 0 (verified), 1 (errors), 2 (warnings)

**Testing**:
- `tests/fixtures/workspaces/`: At least 5 fixture workspaces
  - `clean_award/`: Fully valid achievement record
  - `quote_mismatch/`: Evidence quote doesn't match block text
  - `tampered_seal/`: Verification seal broken by post-seal edit
  - `duplicate_source/`: Same certificate imported twice
  - `user_narration/`: User-asserted experience, no document
- Golden tests: Each fixture has expected `check` output

### Phase 2: Import Pipeline (Priority: HIGH)

**Deliverables**:
1. `src/mementoagent/parsers/`:
   - `base.py`: Abstract `DocumentParser` interface
   - `mineru.py`: MinerU API client (see integration section below)
   - `adapter.py`: Raw engine output → normalized `ParsedBlock`

2. `src/mementoagent/commands/`:
   - `init.py`: Scaffold new workspace (create dirs, copy AGENTS.md, generate workspace.toml)
   - `import.py`: Add file to `inbox/` → hash → move to `sources/` → create sidecar
   - `parse.py`: Run parser on source → save to `.memento/parses/<source>/<parse_id>/`

**Key Constraints**:
- `sources/` files become immutable after import (set filesystem read-only)
- Hash collisions: if file already exists, skip import (idempotent)
- Parse results are snapshots: never overwrite, always append new `parse_id`

**Testing**:
- Mock MinerU API (return canned `content_list.json`)
- Test adapter normalization (bbox 0-1000 → 0.0-1.0, page_idx consistency)
- Test parse_id uniqueness under concurrent imports

### Phase 3: Extraction & Review (Priority: HIGH)

**Deliverables**:
1. `src/mementoagent/extraction/`:
   - `extract.py`: LLM-based field extraction from `ParsedBlock` + prompt
   - `prompts.py`: Extraction prompts per record type
   - Use existing `providers/` for LLM calls

2. `src/mementoagent/commands/`:
   - `extract.py`: Parse result → draft record in `records/achievement/`
   - Auto-populate: `id` (generate ULID), `provenance: document`, `evidence`
   - Leave `verification: null`

3. `src/mementoagent/commands/`:
   - `review.py`: Interactive TUI for pending records
   - Show: source image crop (from bbox), extracted fields side-by-side
   - User confirms → compute seal → write `verification` block
   - Multi-select support for batch review

**Testing**:
- Golden extraction tests: source + blocks → expected draft record
- Seal computation: verify deterministic hash across Python versions

### Phase 4: Generation (Priority: MEDIUM)

**Goal**: Use verified records to generate application materials.

**Deliverables**:
1. `src/mementoagent/templates/`:
   - Jinja2 templates for: resume, scholarship form, personal statement
   - Each template declares required record types/fields

2. `src/mementoagent/commands/`:
   - `generate.py`: Template + record filter → output with citations
   - Output metadata: which record IDs + content hashes used
   - Save to `outputs/<timestamp>_<template_name>.md`

**Not in Scope Yet**:
- Multi-record reasoning (e.g. "pick top 3 awards")
- Narrative synthesis beyond template filling

---

## MinerU Integration

### API Overview

MinerU provides document parsing via REST API. Key endpoints:

**Parse Request**:
```http
POST https://mineru.net/api/v1/parse
Authorization: Bearer <token>
Content-Type: application/json

{
  "file_url": "https://...",          # Or use file upload
  "tier": "standard",                 # flash | basic | standard | advanced
  "language": "ch",
  "enable_table": true,
  "enable_formula": true
}
```

**Poll Status**:
```http
GET https://mineru.net/api/v1/parse/{task_id}
```

**Response** (when complete):
```json
{
  "state": "success",
  "result": {
    "full_zip_url": "https://cdn.mineru.net/..."
  }
}
```

**ZIP Contents**:
- `full.md`: Markdown output
- `content_list.json`: Block-level structured content
- `layout.json`: Layout analysis (middle.json)
- `model.json`: Raw model output
- `images/`: Extracted images

### Integration Points

**File**: `src/mementoagent/parsers/mineru.py`

**Class**: `MinerUParser(DocumentParser)`

**Methods to Implement**:
1. `async def submit_parse(source_path: Path) -> str`:
   - Upload file or provide URL
   - Return `task_id`

2. `async def poll_until_done(task_id: str) -> dict`:
   - Poll every 5s until `state != "running"`
   - Return full result JSON

3. `async def download_zip(zip_url: str, dest_dir: Path)`:
   - Download and extract ZIP to temp dir
   - Return path to extracted contents

4. `def normalize_blocks(content_list_path: Path) -> list[ParsedBlock]`:
   - Read `content_list.json`
   - Convert each entry to normalized `ParsedBlock`:
     - `page_idx` → `page` (already 0-indexed)
     - `bbox` (0-1000 ints) → (0.0-1.0 floats): `[x/1000, y/1000, ...]`
     - `text` → `text`
     - `type` → `type`
     - No `conf` field in MinerU output (leave as `null`)

**Config** (in `workspace.toml`):
```toml
[parse]
engine = "mineru"
tier = "standard"
language = "ch"

[parse.remote]
enabled = true
api_url = "https://mineru.net/api/v1"
# Token loaded from user config, NOT workspace
```

**User Config** (`~/.config/memento-agent/config.toml`):
```toml
[mineru]
api_token = "sk-..."
```

**Privacy Constraint**:
- Check `source.sensitive` flag before uploading
- If `sensitive: true` and `parse.remote.enabled: true`, require explicit consent
- Log upload event to `ledger.jsonl`

**Adapter Notes**:
- MinerU's `page_idx` is 0-indexed (matches our convention)
- MinerU's `bbox` uses 0-1000 range (needs normalization to 0.0-1.0)
- MinerU doesn't provide per-block confidence (our `conf` stays `null`)
- If API details uncertain, implement interface with clear TODOs and mock for testing

---

## Testing Philosophy

### Principle: Adversarial Fixtures Over Happy Paths

Mock data should **stress test invariants**, not confirm assumptions.

**Required Fixture Scenarios**:
1. **Clean Record**: Everything valid, seal intact
2. **Quote Mismatch**: LLM hallucinated part of a quote
3. **Duplicate Source**: Same certificate imported twice (different filenames)
4. **Tampered Seal**: Someone edited `data.level_raw` after verification
5. **Agent Inference**: Agent wrote summary without evidence (provenance: agent)
6. **User Narration**: User described experience, no documents (provenance: user)

### Golden Tests

Each fixture includes:
- Input files (`sources/`, `records/`, `.memento/parses/`)
- Expected `check` command output (exit code + messages)

Test runner:
1. Copy fixture to `tmp_path`
2. Run `memento check <record>`
3. Compare output to golden file
4. Assert exit code matches

**Why This Matters**:
- Validates schema against real-world edge cases
- Catches silent failures (e.g. seal not recomputed after edit)
- Documents expected behavior as runnable tests

---

## Constraints & Non-Goals

### Hard Constraints

1. **Human-in-the-Loop Verification**:
   - AI extracts, human verifies
   - No auto-verification, even at 99.9% confidence
   - Critical fields (level, issuer, date) always require review

2. **Provenance Traceability**:
   - Every document-sourced claim must link to source + block
   - Quotes must be substring-matchable
   - No unsourced factual assertions

3. **Immutable Sources**:
   - Original files never modified after import
   - Parse snapshots never overwritten
   - Ledger is append-only

4. **Schema Versioning**:
   - Every record carries `schema: <type>/<version>`
   - Workspace config declares schema version
   - Enable gradual migration

### Current Non-Goals (v2)

- Multi-record reasoning (e.g. "pick best 3 awards to highlight")
- Inter-record relationships (project → paper citations)
- Fact supersession (old address → new address)
- Search/retrieval indexing (pure linear scan for now)
- Web UI (CLI only)
- Multi-user collaboration

### Technology Stack

- **Language**: Python 3.11+
- **Packaging**: uv (already in use)
- **Schema**: Pydantic v2
- **CLI**: Typer
- **Testing**: pytest
- **Records**: Pure TOML via stdlib tomllib

---

## Next Steps for Agent

1. **Read and understand** this entire specification
2. **Propose implementation plan** for Phase 1 (Core Data Layer)
3. **Start with schema definitions** (`src/mementoagent/schema/`)
4. **Build validation** (`src/mementoagent/validation/`)
5. **Implement `check` command** with exit codes
6. **Create 5 fixture workspaces** in `tests/fixtures/`
7. **Write golden tests** for each fixture

**Critical Question to Answer First**:
What's the canonical representation of critical fields for seal hashing?
- Proposal: Sorted JSON keys, compact (no whitespace), UTF-8 bytes
- Must be deterministic across Python versions and platforms

**Expected Timeline**:
- Phase 1: ~200-300 lines of schema + validation logic
- Phase 1 tests: 5 fixtures + pytest suite
- Total: deliverable in one session, testable immediately

---

## Questions & Clarifications

If anything in this spec is ambiguous:
1. Check existing code in `src/mementoagent/` for patterns
2. Refer to Python/pytest conventions for project structure
3. Ask for clarification before implementing conflicting logic
4. When in doubt, prioritize **human verifiability** over automation

---

**Revision**: 2025-01-12
**Schema Version**: `envelope/1`, `achievement/1`
**Status**: Living document (update as implementation evolves)
```

---

## Plan Mode Prompt

```
You are tasked with implementing the Memento Agent, a provenance-backed personal memory assistant. All architectural decisions and requirements are documented in AGENTS.md in the project root.

CONTEXT:
- Project: Python 3.11+ using uv for dependency management
- Existing scaffold: providers (LLM abstraction), agents (ReAct skeleton)
- Target: Build Phase 1 (Core Data Layer) as specified in AGENTS.md

YOUR TASK:
1. Read and fully understand AGENTS.md, especially:
   - Storage model (workspace + three-tier separation)
   - Core data structures (Source, ParsedBlock, Record envelope, Achievement type, Evidence)
   - Validation contract (Pydantic shape + cross-field invariants)
   - Verification seal mechanism (SHA-256 over canonical critical fields)

2. Propose a detailed implementation plan for Phase 1:
   - Schema definitions in `src/mementoagent/schema/`
   - Validation logic in `src/mementoagent/validation/`
   - CLI `check` command in `src/mementoagent/commands/`
   - 5 adversarial test fixtures in `tests/fixtures/workspaces/`
   - Golden test suite using pytest

3. Start implementation with:
   - Pydantic models for RecordEnvelope, AchievementData, Evidence, Verification
   - Workspace discovery (find .memento/ marker by walking up directory tree)
   - Seal computation (canonical JSON → SHA-256, must be deterministic)
   - Evidence grounding checker (quote substring matching after whitespace normalization)

4. Create test fixtures that stress-test invariants:
   - Clean validated record
   - Quote mismatch (simulated hallucination)
   - Duplicate source (same file, different filenames)
   - Tampered seal (post-verification edit)
   - Agent-generated content (provenance: agent, no verification)
   - User narration (provenance: user, no evidence)

5. Implement `memento check <record_path>` command with exit codes:
   - 0: All checks pass, status = verified
   - 1: Errors (quote mismatch, broken seal, missing evidence)
   - 2: Warnings (needs review, but structurally valid)

CONSTRAINTS:
- DO NOT implement MinerU integration yet (Phase 2). Leave clear interface for DocumentParser.
- DO NOT implement extraction/generation yet (Phases 3-4).
- FOCUS on making the data model real, validated, and testable.
- Prioritize correctness over completeness: a working check command with 5 fixtures is better than partial extraction logic.
- Use existing project structure: src/mementoagent/, tests/, pyproject.toml (uv-managed).

CRITICAL DESIGN DECISIONS TO RESOLVE FIRST:
1. Canonical form for seal hashing:
   - Proposal: Sorted JSON keys, compact (no spaces), UTF-8 encoded
   - Must work identically on Linux/macOS/Windows, Python 3.11+
   - Test with fixture: compute seal on record, modify field, verify mismatch detected

2. TOML record parsing:
   - Use stdlib tomllib; records are read-only during checking
   - Parse dates as strings (quote them to avoid YAML's date object coercion)
   - Store optional body before all table headers

3. Workspace discovery:
   - Walk up from cwd looking for .memento/ directory
   - Error if not found: "Not in a memento workspace (no .memento/ found)"
   - Cache result to avoid repeated filesystem walks

EXPECTED DELIVERABLES (Phase 1):
- src/mementoagent/schema/envelope.py, achievement.py, source.py, parse.py
- src/mementoagent/workspace/discovery.py, paths.py, config.py
- src/mementoagent/validation/shape.py, invariants.py, seal.py
- src/mementoagent/commands/check.py (CLI entrypoint)
- tests/fixtures/workspaces/ (5 scenarios)
- tests/test_validation.py (golden tests)
- pyproject.toml: add dependencies (pydantic, click/typer, ruamel.yaml, pytest)

OUTPUT FORMAT:
1. High-level plan (what you'll build, in what order, why)
2. Key design decisions with rationale
3. Step-by-step implementation sequence
4. Testing strategy
5. Ask any blocking questions BEFORE starting implementation

TONE: You're a senior engineer proposing an implementation plan to the team. Be concrete, identify risks, suggest alternatives where ambiguous. Prioritize shipping a testable Phase 1 over prematurely building Phase 2/3.

Now, propose your implementation plan.