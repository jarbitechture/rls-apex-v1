# v0.2.1a Stream B — Redaction Pipeline + 18 Stubs — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `redaction-pipeline` service + 18 hand-crafted synthetic stub opinions + `redaction_audit` Postgres table that, together, let Stream C retrieval test against realistic opinion-like content while Stream B's governance work (Legal-access for the real 50 opinions) runs in parallel. Engineering proceeds independently on stubs.

**Architecture:** Queue-driven Python service (`services/redaction/`) — NOT always-on like the scraper. Reads stub or real opinion PDFs/text from an input directory, runs two-stage detection (regex + LLM), writes `redaction_audit` rows pending human review, and ingests approved-redacted text into `corpus_chunks` with `source_type="internal_opinion"`. The 18 stubs unblock Stream C's retrieval testing immediately.

**Tech Stack:** Python 3.12, `pdfminer.six` for PDF extraction, Ollama chat-model client for LLM-assisted detection, regex stdlib, asyncpg for DB writes, pytest with the existing `pytest-postgresql` fixture.

**Branch:** `feat/v0.2.0a-backend` (or `feat/v0.2.1a` if Plan A has merged and renamed by execution time).

**Reference docs:**
- Spec: `docs/superpowers/specs/2026-05-11-v0_2_1a-design.md` §5 (canonical) + ADR-003 (18 stubs) + ADR-007 (LLM-assisted + human review queue)
- Plan A: `docs/superpowers/plans/2026-05-11-v0_2_1a-stream-a-web-ingestion.md` (depends on T1 `corpus_chunks` schema being landed)
- Runbook: `docs/runbooks/2026-05-09-rls-apex-v0_2_0b-runbook.md`

**Baseline:** assumes Plan A has landed (HEAD ~`<post-Plan-A>`, ~89 backend tests). If Plan A is still BLOCKED at execution time, Plan B's Task 1 alembic migration must be sequenced AFTER Plan A's Task 1. Both alembic migrations stack cleanly (Plan A creates `corpus_chunks`; Plan B creates `redaction_audit` with FK to it).

After this plan: backend pytest count ~89 + ~18 new = ~107. New `services/redaction/` directory + 18 stub opinion files in `corpus-data/stubs/`. No new systemd always-on unit (redaction is queue-only).

**Out of scope** (lives in Plan C or v0.2.1b):
- Hybrid retriever + L3 + L4 MCP tools (Plan C)
- L14 frontend extension (Plan C)
- Human review queue UX — for v0.2.1a, reviewers manually `psql` (per ADR-007)
- Real 50 opinions ingestion (governance-gated; happens after Legal access)
- L1/L2 rule engines + W8 (Plan D)

---

## File Structure

| Path | Action | Responsibility |
|---|---|---|
| `alembic/versions/<new>_v021a_redaction_audit.py` | Create | Migration: `redaction_audit` table + FK to `corpus_chunks` |
| `services/redaction/__init__.py` | Create | Package marker |
| `services/redaction/pipeline.py` | Create | Entry point: `process_document(input_path) -> RedactionRun` |
| `services/redaction/detectors/__init__.py` | Create | Init |
| `services/redaction/detectors/regex_detectors.py` | Create | SSN, phone, email, Bates label patterns (high-confidence) |
| `services/redaction/detectors/llm_detector.py` | Create | Ollama chat-model wrapper for ambiguous span detection |
| `services/redaction/audit.py` | Create | Writes to `redaction_audit`; reads `pending` rows; applies after review |
| `services/redaction/ingest.py` | Create | After human review, applies redactions and INSERTs into `corpus_chunks` (source_type="internal_opinion") |
| `services/redaction/cli.py` | Create | `python -m services.redaction process /path/to/opinion.pdf` |
| `services/redaction/requirements.txt` | Create | Pinned: pdfminer.six, asyncpg, httpx, pydantic |
| `apps/gateway/db/models.py` | Modify | Add `RedactionAuditRow` Pydantic model + `RedactionReason` enum |
| `corpus-data/stubs/README.md` | Create | Documents stub authoring convention + PII pattern requirements |
| `corpus-data/stubs/stub-code_enforcement_litigation-1.md` | Create | Stub opinion #1 (per ADR-003) |
| `corpus-data/stubs/stub-code_enforcement_litigation-2.md` | Create | Stub #2 |
| `corpus-data/stubs/stub-code_enforcement_litigation-3.md` | Create | Stub #3 |
| `corpus-data/stubs/stub-permit_or_zoning-{1,2,3}.md` | Create (3 files) | Permit/zoning stubs |
| `corpus-data/stubs/stub-procurement-{1,2,3}.md` | Create (3 files) | Procurement stubs |
| `corpus-data/stubs/stub-public_records-{1,2,3}.md` | Create (3 files) | Public-records stubs |
| `corpus-data/stubs/stub-general_advisory-{1,2,3}.md` | Create (3 files) | General-advisory stubs |
| `corpus-data/stubs/stub-other-{1,2,3}.md` | Create (3 files) | Edge-case stubs |
| `tests/services/redaction/__init__.py` | Create | Empty |
| `tests/services/redaction/test_stub_quality.py` | Create | Validates 18 stubs meet W4 spec criteria (≥800 words, regex patterns, Bates, privilege markers) |
| `tests/services/redaction/test_regex_detectors.py` | Create | Each regex detector catches its target pattern + doesn't false-positive on common safe strings |
| `tests/services/redaction/test_llm_detector.py` | Create | LLM detector mocked; returns expected span shape; handles "no detections" cleanly |
| `tests/services/redaction/test_audit_writes.py` | Create | Audit rows written before redacted text is applied; reviewer_upn=NULL on insert; UPDATE-on-review |
| `tests/services/redaction/test_ingest.py` | Create | Apply redactions only after review; INSERT into corpus_chunks with source_type="internal_opinion" |
| `tests/services/redaction/test_pipeline_integration.py` | Create | End-to-end against stub-code_enforcement_litigation-1.md: PDF/text → detect → audit → review → ingest |

---

## Task 1: Alembic migration — `redaction_audit` table

**Files:**
- Create: `alembic/versions/<auto>_v021a_redaction_audit.py`

- [ ] **Step 1: Generate migration**

```bash
cd /Users/ejarbe/Projects/rls-apex-v1
.venv/bin/alembic revision -m "v021a redaction_audit table"
```

- [ ] **Step 2: Write migration body**

```python
"""v021a redaction_audit table

Revision ID: <auto>
Revises: <Plan A's corpus_chunks revision id — confirm via .venv/bin/alembic history>
Create Date: 2026-05-11

redaction_audit: every detected redaction span gets one row. reviewer_upn=NULL
means pending review (per ADR-007). Only rows with reviewer_upn IS NOT NULL are
applied to corpus_chunks. FK to corpus_chunks(id) allows direct join from a
redacted chunk back to all spans contributing to it.
"""
from alembic import op
import sqlalchemy as sa

revision = "<auto>"
down_revision = "<auto — Plan A corpus_chunks revision id>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "redaction_audit",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("source_doc_id", sa.Text, nullable=False),  # internal opinion identifier
        sa.Column("chunk_id", sa.BigInteger,
                  sa.ForeignKey("corpus_chunks.id", ondelete="SET NULL"),
                  nullable=True),  # NULL until chunk is INSERTed post-review
        sa.Column("original_span_start", sa.Integer, nullable=False),
        sa.Column("original_span_end", sa.Integer, nullable=False),
        sa.Column("original_text", sa.Text, nullable=False),  # the span content (encrypted at rest optional v0.2.1b)
        sa.Column("redaction_reason", sa.Text, nullable=False),  # enum string per RedactionReason
        sa.Column("detector", sa.Text, nullable=False),  # "regex:ssn" | "llm:mxbai-chat" | "human"
        sa.Column("reviewer_upn", sa.Text, nullable=True),  # NULL = pending
        sa.Column("reviewed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index(
        "idx_redaction_audit_pending",
        "redaction_audit",
        ["created_at"],
        postgresql_where=sa.text("reviewer_upn IS NULL"),
    )
    op.create_index(
        "idx_redaction_audit_source_doc",
        "redaction_audit",
        ["source_doc_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_redaction_audit_source_doc", table_name="redaction_audit")
    op.drop_index("idx_redaction_audit_pending", table_name="redaction_audit")
    op.drop_table("redaction_audit")
```

- [ ] **Step 3: Run migration + verify schema**

```bash
.venv/bin/alembic upgrade head
```

Verify via psql `\d+ redaction_audit` that all 11 columns + 2 indexes are present.

- [ ] **Step 4: Backend regression check**

```bash
.venv/bin/python -m pytest -q
```

Expected: prior count maintained (no new tests in this task; just schema).

- [ ] **Step 5: Commit**

```bash
git add alembic/versions/*_v021a_redaction_audit.py
git commit -m "$(cat <<'EOF'
feat(db): alembic migration — redaction_audit table for v0.2.1a Stream B

Per spec ADR-007: every detected span gets one row. reviewer_upn=NULL
means pending review. Only rows with reviewer_upn IS NOT NULL are
applied to corpus_chunks (source_type="internal_opinion"). FK to
corpus_chunks(id) allows direct join from a redacted chunk back to
all spans contributing to it.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: `RedactionReason` enum + `RedactionAuditRow` Pydantic model

**Files:**
- Modify: `apps/gateway/db/models.py`
- Create: `tests/test_redaction_audit_model.py`

- [ ] **Step 1: Write the failing test**

`tests/test_redaction_audit_model.py`:

```python
"""RedactionAuditRow Pydantic model — matches alembic schema, validates enum + spans."""
from __future__ import annotations

import pytest
from datetime import datetime, timezone

from apps.gateway.db.models import RedactionAuditRow, RedactionReason


def test_minimal_required_fields():
    row = RedactionAuditRow(
        source_doc_id="stub-code_enforcement_litigation-1",
        original_span_start=10,
        original_span_end=20,
        original_text="123-45-6789",
        redaction_reason=RedactionReason.pii_ssn_or_id,
        detector="regex:ssn",
    )
    assert row.reviewer_upn is None
    assert row.reviewed_at is None
    assert row.chunk_id is None


def test_redaction_reason_enum_accepts_all_documented_values():
    for value in ["pii_name", "pii_address", "pii_dob", "pii_ssn_or_id",
                  "pii_contact", "privileged", "settlement_terms",
                  "ongoing_litigation", "other"]:
        row = RedactionAuditRow(
            source_doc_id="x",
            original_span_start=0,
            original_span_end=1,
            original_text="x",
            redaction_reason=value,
            detector="regex:test",
        )
        assert row.redaction_reason == value


def test_redaction_reason_rejects_unknown():
    with pytest.raises(ValueError, match="redaction_reason"):
        RedactionAuditRow(
            source_doc_id="x",
            original_span_start=0,
            original_span_end=1,
            original_text="x",
            redaction_reason="not_a_valid_reason",
            detector="regex:test",
        )


def test_span_must_be_non_negative():
    with pytest.raises(ValueError):
        RedactionAuditRow(
            source_doc_id="x",
            original_span_start=-1,
            original_span_end=5,
            original_text="x",
            redaction_reason="other",
            detector="x",
        )


def test_span_end_must_exceed_start():
    with pytest.raises(ValueError, match="span_end"):
        RedactionAuditRow(
            source_doc_id="x",
            original_span_start=10,
            original_span_end=5,
            original_text="x",
            redaction_reason="other",
            detector="x",
        )
```

- [ ] **Step 2: RED**

```bash
.venv/bin/python -m pytest tests/test_redaction_audit_model.py -v
```

Expected: 5 FAILED.

- [ ] **Step 3: Add model**

Append to `apps/gateway/db/models.py`:

```python
from enum import Enum


class RedactionReason(str, Enum):
    """Per spec §5.4. Subject to County Attorney + records officer sign-off."""
    pii_name = "pii_name"
    pii_address = "pii_address"
    pii_dob = "pii_dob"
    pii_ssn_or_id = "pii_ssn_or_id"
    pii_contact = "pii_contact"
    privileged = "privileged"
    settlement_terms = "settlement_terms"
    ongoing_litigation = "ongoing_litigation"
    other = "other"


class RedactionAuditRow(BaseModel):
    """One row per detected redaction span. reviewer_upn=NULL means pending review."""
    id: int | None = None
    source_doc_id: str
    chunk_id: int | None = None  # set after redacted chunk is INSERTed
    original_span_start: int = Field(ge=0)
    original_span_end: int = Field(ge=1)
    original_text: str
    redaction_reason: RedactionReason
    detector: str  # "regex:ssn" | "llm:mxbai-chat" | "human"
    reviewer_upn: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime | None = None

    @field_validator("original_span_end")
    @classmethod
    def _end_after_start(cls, v: int, info) -> int:
        start = info.data.get("original_span_start")
        if start is not None and v <= start:
            raise ValueError("original_span_end must exceed original_span_start")
        return v
```

- [ ] **Step 4: GREEN**

```bash
.venv/bin/python -m pytest tests/test_redaction_audit_model.py -v
```

Expected: 5 PASSED.

- [ ] **Step 5: Commit**

```bash
git add apps/gateway/db/models.py tests/test_redaction_audit_model.py
git commit -m "feat(db): RedactionReason enum + RedactionAuditRow Pydantic model with span validators"
```

---

## Task 3: 18 stub opinions (ADR-003, W4 spec acceptance)

**Files:**
- Create: `corpus-data/stubs/README.md`
- Create: `corpus-data/stubs/stub-{matter_type}-{1,2,3}.md` (18 files)
- Create: `tests/services/redaction/test_stub_quality.py`

- [ ] **Step 1: Write the W4 acceptance test FIRST**

`tests/services/redaction/test_stub_quality.py`:

```python
"""W4 — validate 18 stub opinions meet spec criteria.

Per spec ADR-003 + §15 W4:
- 18 files committed under corpus-data/stubs/
- Named stub-{matter_type}-{1,2,3}.md
- Each ≥800 words
- Each MUST contain:
  ≥1 SSN regex match (\\d{3}-\\d{2}-\\d{4})
  ≥1 phone match (\\(\\d{3}\\) \\d{3}-\\d{4} or \\d{3}-\\d{3}-\\d{4})
  ≥1 Bates label (MC-\\d{6} format)
  ≥1 attorney-client work-product marker ([ATTORNEY-CLIENT PRIVILEGED] or similar)
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


STUBS_DIR = Path(__file__).resolve().parents[3] / "corpus-data" / "stubs"

MATTER_TYPES = [
    "code_enforcement_litigation",
    "permit_or_zoning",
    "procurement",
    "public_records",
    "general_advisory",
    "other",
]

SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
PHONE_RE = re.compile(r"\(\d{3}\) \d{3}-\d{4}|\d{3}-\d{3}-\d{4}")
BATES_RE = re.compile(r"\bMC-\d{6}\b")
PRIVILEGE_RE = re.compile(r"\[ATTORNEY[- ]CLIENT PRIVILEGED\]|\[WORK PRODUCT\]|\[PRIVILEGED\]", re.IGNORECASE)


def test_eighteen_stub_files_exist():
    assert STUBS_DIR.exists(), f"stubs dir missing: {STUBS_DIR}"
    stub_files = sorted(STUBS_DIR.glob("stub-*.md"))
    assert len(stub_files) == 18, f"expected 18 stub files, got {len(stub_files)}: {[f.name for f in stub_files]}"


def test_three_stubs_per_matter_type():
    for matter_type in MATTER_TYPES:
        files = sorted(STUBS_DIR.glob(f"stub-{matter_type}-*.md"))
        assert len(files) == 3, f"expected 3 stubs for {matter_type}, got {len(files)}"


@pytest.mark.parametrize("matter_type", MATTER_TYPES)
@pytest.mark.parametrize("idx", [1, 2, 3])
def test_stub_word_count_at_least_800(matter_type, idx):
    path = STUBS_DIR / f"stub-{matter_type}-{idx}.md"
    text = path.read_text()
    words = len(text.split())
    assert words >= 800, f"{path.name} has only {words} words; ≥800 required"


@pytest.mark.parametrize("matter_type", MATTER_TYPES)
@pytest.mark.parametrize("idx", [1, 2, 3])
def test_stub_contains_required_pii_patterns(matter_type, idx):
    path = STUBS_DIR / f"stub-{matter_type}-{idx}.md"
    text = path.read_text()
    assert SSN_RE.search(text), f"{path.name} missing SSN pattern"
    assert PHONE_RE.search(text), f"{path.name} missing phone pattern"
    assert BATES_RE.search(text), f"{path.name} missing Bates label"
    assert PRIVILEGE_RE.search(text), f"{path.name} missing privilege marker"
```

- [ ] **Step 2: RED**

```bash
.venv/bin/python -m pytest tests/services/redaction/test_stub_quality.py -v
```

Expected: All FAILED (stub files don't exist yet).

- [ ] **Step 3: Author the 18 stub opinions**

Create `corpus-data/stubs/README.md`:

```markdown
# Synthetic stub opinions — RLS Apex v0.2.1a

18 hand-crafted stub opinions used to test the redaction pipeline (Stream B)
and seed retrieval testing (Stream C) before real opinions are accessible.

## Authoring convention

- Filename: `stub-{matter_type}-{N}.md` where `matter_type ∈ {code_enforcement_litigation, permit_or_zoning, procurement, public_records, general_advisory, other}` and `N ∈ {1, 2, 3}`
- ≥800 words each
- Each MUST contain at minimum (validated by `tests/services/redaction/test_stub_quality.py`):
  - ≥1 SSN pattern: `\d{3}-\d{2}-\d{4}`
  - ≥1 phone pattern: `(NNN) NNN-NNNN` or `NNN-NNN-NNNN`
  - ≥1 Bates label: `MC-NNNNNN`
  - ≥1 privilege marker: `[ATTORNEY-CLIENT PRIVILEGED]` or `[WORK PRODUCT]` or `[PRIVILEGED]`

## Realism

Stubs should read like Manatee County Attorney opinions in tone + citation
style (LDC §X.Y, Procedure 26-104.001, Ch. 2-26 references). They're test
fixtures, NOT real opinions — every name, address, case number, and SSN
must be synthetic. Do not use real Manatee residents or actual ongoing matters.
```

Then author 18 files. Each ~800-1500 words, matter-type-appropriate. Example template for one stub (the implementer writes 18 like this):

```markdown
# stub-code_enforcement_litigation-1.md

## MEMORANDUM — [ATTORNEY-CLIENT PRIVILEGED]

**To:** Board of County Commissioners
**From:** County Attorney's Office
**Re:** NOV 2024-CE-0143 — Parcel ID 12345-6789-0
**Bates:** MC-104301
**Date:** [synthetic — March 15, 2024]

**Requester contact:**
- John Synthwood (synthetic name)
- SSN: 123-45-6789
- Phone: (941) 555-0142
- Address: 1234 Synthetic Lane, Bradenton FL 34205

### Background

In November 2023, Code Enforcement issued NOV 2024-CE-0143 to the
property owner for alleged violation of Manatee County LDC §6.4(a)
relating to unpermitted structures. The owner has retained counsel and
requested administrative review pursuant to Procedure 26-104.001.

The property is currently subject to a Bates-numbered evidence
collection (MC-104301 through MC-104327) including aerial photographs
dated 2023-08-12 and 2024-02-04. Substantive content of the file is
not at issue today; the threshold question is whether the special
magistrate's jurisdiction is properly invoked.

[Stub continues for 800+ words covering: legal analysis, citations to
LDC §6.4, references to analogous matters like RLS-23-0067, discussion
of vested-rights doctrine, settlement-terms discussion (which would be
flagged for redaction in production), and a recommended next step.]

### Recommendation

[ATTORNEY-CLIENT PRIVILEGED] — Counsel recommends...

---

*Internal opinion. Not for distribution outside the County Attorney's office.*
```

**Implementer note:** Write 17 more in similar style, varying matter type and substantive content. Use a templating discipline: each stub has a Header block (memo metadata), 3-5 Body paragraphs (legal analysis), and a Recommendation block. PII patterns get distributed naturally (SSN in requester block, phone + address there too, Bates in evidence references, privilege markers in Recommendation block).

Approximate per-file authoring time: 10-15 min × 18 = 3-4 hours of careful work. **This is the most time-consuming task in Plan B.** Worth doing well — Stream C's retrieval quality validation depends on stub diversity.

- [ ] **Step 4: GREEN**

```bash
.venv/bin/python -m pytest tests/services/redaction/test_stub_quality.py -v
```

Expected: All PASSED (18 stubs × 4 parametrized assertions + 2 setup tests = ~74 test cases). If any fail, fix the specific stub file's missing pattern.

- [ ] **Step 5: Commit**

```bash
git add corpus-data/stubs/README.md corpus-data/stubs/stub-*.md tests/services/redaction/test_stub_quality.py
git commit -m "$(cat <<'EOF'
feat(stubs): 18 synthetic opinion stubs covering 6 matter types (ADR-003, W4)

3 stubs per matter type from spec §4.1 enum. Each ≥800 words with
realistic PII patterns (SSN, phone, Bates labels) and privilege
markers. Authoring convention documented in README.md.

These stubs unblock Stream C retrieval testing immediately; real 50
opinions land later once Legal access is granted (Stream B governance).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Regex detectors

**Files:**
- Create: `services/__init__.py` (if not already from Plan A)
- Create: `services/redaction/__init__.py`
- Create: `services/redaction/detectors/__init__.py`
- Create: `services/redaction/detectors/regex_detectors.py`
- Create: `services/redaction/requirements.txt`
- Create: `tests/services/redaction/__init__.py`
- Create: `tests/services/redaction/test_regex_detectors.py`

- [ ] **Step 1: Failing test**

`tests/services/redaction/test_regex_detectors.py`:

```python
"""Regex detectors for high-confidence PII patterns."""
from __future__ import annotations

import pytest

from services.redaction.detectors.regex_detectors import detect_all, DetectedSpan


def test_ssn_detected():
    spans = detect_all("Patient SSN is 123-45-6789 on file.")
    ssns = [s for s in spans if s.reason == "pii_ssn_or_id"]
    assert len(ssns) == 1
    assert ssns[0].text == "123-45-6789"


def test_phone_detected_both_formats():
    text = "Call (941) 555-0142 or 941-555-0143 anytime."
    spans = detect_all(text)
    phones = [s for s in spans if s.reason == "pii_contact"]
    assert len(phones) == 2


def test_bates_detected():
    spans = detect_all("See Bates MC-104301 for the exhibit.")
    bates = [s for s in spans if s.reason == "other"]
    assert any(s.text == "MC-104301" for s in bates)


def test_no_false_positive_on_dates():
    # 2024-01-15 looks like a date, not an SSN
    spans = detect_all("Filing date 2024-01-15.")
    ssns = [s for s in spans if s.reason == "pii_ssn_or_id"]
    assert ssns == []


def test_no_false_positive_on_empty_text():
    assert detect_all("") == []


def test_detector_label_present():
    spans = detect_all("SSN 123-45-6789")
    assert all(s.detector.startswith("regex:") for s in spans)
```

- [ ] **Step 2: RED**

```bash
.venv/bin/python -m pytest tests/services/redaction/test_regex_detectors.py -v
```

Expected: 6 FAILED.

- [ ] **Step 3: Implement `regex_detectors.py`**

`services/redaction/__init__.py`:
```python
# Stream B redaction pipeline — see docs/superpowers/specs/2026-05-11-v0_2_1a-design.md §5
```

`services/redaction/detectors/__init__.py`: empty.

`services/redaction/detectors/regex_detectors.py`:

```python
"""High-confidence regex detectors for PII redaction.

Per spec ADR-007: regex catches deterministic patterns; LLM detector handles
ambiguous spans (names, addresses, privileged content). Both write to
redaction_audit with detector="regex:<name>" or "llm:<model>".
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class DetectedSpan:
    start: int
    end: int
    text: str
    reason: str  # matches RedactionReason enum value
    detector: str  # "regex:ssn" | "regex:phone" | "regex:bates"


# SSN — three groups of digits separated by dashes; word-boundary anchored
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

# Phone — accept both (NNN) NNN-NNNN and NNN-NNN-NNNN
PHONE_RE = re.compile(r"\(\d{3}\)\s\d{3}-\d{4}|\b\d{3}-\d{3}-\d{4}\b")

# Bates label — MC-NNNNNN format
BATES_RE = re.compile(r"\bMC-\d{6}\b")


def detect_all(text: str) -> list[DetectedSpan]:
    """Run all regex detectors over `text`; return non-overlapping spans."""
    spans: list[DetectedSpan] = []
    for m in SSN_RE.finditer(text):
        spans.append(DetectedSpan(
            start=m.start(), end=m.end(), text=m.group(),
            reason="pii_ssn_or_id", detector="regex:ssn",
        ))
    for m in PHONE_RE.finditer(text):
        spans.append(DetectedSpan(
            start=m.start(), end=m.end(), text=m.group(),
            reason="pii_contact", detector="regex:phone",
        ))
    for m in BATES_RE.finditer(text):
        spans.append(DetectedSpan(
            start=m.start(), end=m.end(), text=m.group(),
            reason="other", detector="regex:bates",
        ))
    # De-overlap: sort by start; drop spans that fall inside earlier-finishing ones
    spans.sort(key=lambda s: (s.start, -s.end))
    deduped: list[DetectedSpan] = []
    for s in spans:
        if deduped and s.start < deduped[-1].end:
            continue
        deduped.append(s)
    return deduped
```

`services/redaction/requirements.txt`:
```
pdfminer.six==20240706
asyncpg==0.30.0
httpx==0.28.1
pydantic==2.9.2
```

- [ ] **Step 4: GREEN**

```bash
.venv/bin/python -m pytest tests/services/redaction/test_regex_detectors.py -v
```

Expected: 6 PASSED.

- [ ] **Step 5: Commit**

```bash
git add services/redaction/__init__.py services/redaction/detectors/__init__.py services/redaction/detectors/regex_detectors.py services/redaction/requirements.txt tests/services/redaction/__init__.py tests/services/redaction/test_regex_detectors.py
git commit -m "feat(redaction): regex detectors for SSN + phone + Bates labels"
```

---

## Task 5: LLM detector (Ollama chat)

**Files:**
- Create: `services/redaction/detectors/llm_detector.py`
- Create: `tests/services/redaction/test_llm_detector.py`

- [ ] **Step 1: Failing test**

`tests/services/redaction/test_llm_detector.py`:

```python
"""LLM detector — Ollama chat-model wrapper for ambiguous spans (names, addresses, privileged content)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from services.redaction.detectors.llm_detector import LlmDetector
from services.redaction.detectors.regex_detectors import DetectedSpan


@pytest.fixture
def detector():
    return LlmDetector(model="phi4", ollama_url="http://localhost:11434")


@pytest.mark.asyncio
async def test_llm_detector_parses_structured_response(detector):
    """LLM returns structured JSON of spans; detector parses to DetectedSpan list."""
    fake_response = {
        "spans": [
            {"start": 10, "end": 22, "text": "John Synthwood", "reason": "pii_name"},
            {"start": 45, "end": 70, "text": "1234 Synthetic Lane", "reason": "pii_address"},
        ]
    }
    with patch.object(detector, "_call_ollama", new=AsyncMock(return_value=fake_response)):
        spans = await detector.detect("Some document text containing John Synthwood at 1234 Synthetic Lane today.")
    assert len(spans) == 2
    assert spans[0].text == "John Synthwood"
    assert spans[0].reason == "pii_name"
    assert spans[0].detector.startswith("llm:")


@pytest.mark.asyncio
async def test_llm_detector_handles_empty_response(detector):
    with patch.object(detector, "_call_ollama", new=AsyncMock(return_value={"spans": []})):
        spans = await detector.detect("clean text with no PII")
    assert spans == []


@pytest.mark.asyncio
async def test_llm_detector_handles_malformed_response(detector):
    """Defensive: if Ollama returns garbage, log + return empty list (don't raise)."""
    with patch.object(detector, "_call_ollama", new=AsyncMock(return_value={"unexpected_key": "garbage"})):
        spans = await detector.detect("any text")
    assert spans == []
```

- [ ] **Step 2: RED**

```bash
.venv/bin/python -m pytest tests/services/redaction/test_llm_detector.py -v
```

Expected: 3 FAILED.

- [ ] **Step 3: Implement `llm_detector.py`**

`services/redaction/detectors/llm_detector.py`:

```python
"""LLM-assisted detection for ambiguous redaction spans.

Per spec ADR-007: LLM catches what regex can't (names, addresses, contextual
privilege markers). Returns structured spans for human review (queue UX in
v0.2.1b; manual psql review in v0.2.1a).

Model: Ollama-hosted chat model (default phi4 — fast + cheap). User can override
via constructor or env var OLLAMA_REDACTION_MODEL.

Prompt strategy: instruct the model to return JSON with explicit (start, end,
text, reason) per span. Mismatches between LLM-claimed start/end and actual
text positions are tolerated by re-locating the span via str.find.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass

import httpx

from .regex_detectors import DetectedSpan


logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are a public-records redaction assistant for the Manatee County Attorney's office.

Identify spans in the input text that should be redacted under Florida public-records law. Categories:
- pii_name: individual names (NOT party names in published case law)
- pii_address: physical addresses
- pii_dob: dates of birth
- pii_contact: emails (phones are caught by regex)
- privileged: attorney-client work product
- settlement_terms: confidential settlement language
- ongoing_litigation: identifiers tied to pending matters

Return ONLY a JSON object: {"spans": [{"start": int, "end": int, "text": str, "reason": str}, ...]}
If nothing should be redacted, return {"spans": []}."""


@dataclass
class LlmDetector:
    model: str = "phi4"
    ollama_url: str = "http://localhost:11434"
    timeout_s: float = 30.0

    async def _call_ollama(self, text: str) -> dict:
        """Single Ollama chat call returning parsed JSON."""
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            "format": "json",
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            r = await client.post(f"{self.ollama_url}/api/chat", json=payload)
            r.raise_for_status()
            data = r.json()
        # Ollama wraps response in {message: {content: "..."}}
        content = data.get("message", {}).get("content", "{}")
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.warning("LLM detector returned non-JSON content: %r", content[:200])
            return {"spans": []}

    async def detect(self, text: str) -> list[DetectedSpan]:
        """Run LLM detection; return DetectedSpan list."""
        try:
            response = await self._call_ollama(text)
        except Exception as exc:
            logger.warning("LLM detector call failed: %s", exc)
            return []

        raw_spans = response.get("spans", [])
        if not isinstance(raw_spans, list):
            logger.warning("LLM detector returned non-list spans: %r", raw_spans)
            return []

        spans: list[DetectedSpan] = []
        for raw in raw_spans:
            if not isinstance(raw, dict):
                continue
            try:
                start = int(raw["start"])
                end = int(raw["end"])
                t = str(raw["text"])
                reason = str(raw["reason"])
            except (KeyError, ValueError, TypeError):
                continue
            # Sanity: if LLM-reported start/end don't match the actual text, re-locate
            if text[start:end] != t:
                relocated = text.find(t)
                if relocated >= 0:
                    start = relocated
                    end = relocated + len(t)
                else:
                    continue  # span text not found; skip
            spans.append(DetectedSpan(
                start=start, end=end, text=t,
                reason=reason, detector=f"llm:{self.model}",
            ))
        return spans
```

- [ ] **Step 4: GREEN**

```bash
.venv/bin/python -m pytest tests/services/redaction/test_llm_detector.py -v
```

Expected: 3 PASSED.

- [ ] **Step 5: Commit**

```bash
git add services/redaction/detectors/llm_detector.py tests/services/redaction/test_llm_detector.py
git commit -m "feat(redaction): LLM detector (Ollama chat) for ambiguous redaction spans"
```

---

## Task 6: Audit writes (`services/redaction/audit.py`)

**Files:**
- Create: `services/redaction/audit.py`
- Create: `tests/services/redaction/test_audit_writes.py`

- [ ] **Step 1: Failing test**

`tests/services/redaction/test_audit_writes.py`:

```python
"""Audit-write logic: detected spans → redaction_audit rows with reviewer_upn=NULL."""
from __future__ import annotations

import pytest

from services.redaction.detectors.regex_detectors import DetectedSpan
from services.redaction.audit import write_pending_spans, approve_span, list_pending


@pytest.fixture(autouse=True)
async def fresh_audit(postgresql):
    await postgresql.execute("TRUNCATE TABLE redaction_audit")
    return postgresql


@pytest.mark.asyncio
async def test_write_pending_spans_inserts_with_null_reviewer(fresh_audit):
    spans = [
        DetectedSpan(start=10, end=21, text="123-45-6789",
                     reason="pii_ssn_or_id", detector="regex:ssn"),
        DetectedSpan(start=30, end=44, text="(941) 555-0142",
                     reason="pii_contact", detector="regex:phone"),
    ]
    inserted = await write_pending_spans(fresh_audit, source_doc_id="stub-x-1", spans=spans)
    assert inserted == 2
    rows = await fresh_audit.fetch("SELECT * FROM redaction_audit ORDER BY id")
    assert all(r["reviewer_upn"] is None for r in rows)
    assert all(r["chunk_id"] is None for r in rows)
    assert {r["redaction_reason"] for r in rows} == {"pii_ssn_or_id", "pii_contact"}


@pytest.mark.asyncio
async def test_approve_sets_reviewer_and_reviewed_at(fresh_audit):
    span = DetectedSpan(start=0, end=5, text="hello",
                        reason="other", detector="regex:test")
    await write_pending_spans(fresh_audit, "doc-x", [span])
    pending_before = await list_pending(fresh_audit, source_doc_id="doc-x")
    assert len(pending_before) == 1

    await approve_span(fresh_audit, pending_before[0]["id"], reviewer_upn="reviewer@manatee.local")

    row = await fresh_audit.fetchrow("SELECT * FROM redaction_audit WHERE id = $1", pending_before[0]["id"])
    assert row["reviewer_upn"] == "reviewer@manatee.local"
    assert row["reviewed_at"] is not None


@pytest.mark.asyncio
async def test_list_pending_excludes_approved(fresh_audit):
    s1 = DetectedSpan(start=0, end=5, text="aaaaa", reason="other", detector="t")
    s2 = DetectedSpan(start=10, end=15, text="bbbbb", reason="other", detector="t")
    await write_pending_spans(fresh_audit, "doc-x", [s1, s2])
    rows = await list_pending(fresh_audit, source_doc_id="doc-x")
    await approve_span(fresh_audit, rows[0]["id"], "r@x")
    remaining = await list_pending(fresh_audit, source_doc_id="doc-x")
    assert len(remaining) == 1
```

- [ ] **Step 2: RED**

```bash
.venv/bin/python -m pytest tests/services/redaction/test_audit_writes.py -v
```

Expected: 3 FAILED.

- [ ] **Step 3: Implement `audit.py`**

`services/redaction/audit.py`:

```python
"""redaction_audit table operations: write pending spans, list, approve."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

import asyncpg

from .detectors.regex_detectors import DetectedSpan


async def write_pending_spans(
    conn: asyncpg.Connection,
    source_doc_id: str,
    spans: Iterable[DetectedSpan],
) -> int:
    """Insert each span as a pending audit row. Returns count inserted."""
    spans = list(spans)
    if not spans:
        return 0
    await conn.executemany(
        """
        INSERT INTO redaction_audit (
            source_doc_id, original_span_start, original_span_end,
            original_text, redaction_reason, detector
        ) VALUES ($1, $2, $3, $4, $5, $6)
        """,
        [(source_doc_id, s.start, s.end, s.text, s.reason, s.detector) for s in spans],
    )
    return len(spans)


async def list_pending(
    conn: asyncpg.Connection,
    source_doc_id: str | None = None,
) -> list[dict]:
    """Return pending (reviewer_upn IS NULL) audit rows, optionally filtered by source_doc_id."""
    if source_doc_id is not None:
        rows = await conn.fetch(
            """
            SELECT id, source_doc_id, original_span_start, original_span_end,
                   original_text, redaction_reason, detector, created_at
            FROM redaction_audit
            WHERE reviewer_upn IS NULL AND source_doc_id = $1
            ORDER BY id
            """,
            source_doc_id,
        )
    else:
        rows = await conn.fetch(
            """
            SELECT id, source_doc_id, original_span_start, original_span_end,
                   original_text, redaction_reason, detector, created_at
            FROM redaction_audit
            WHERE reviewer_upn IS NULL
            ORDER BY id
            """
        )
    return [dict(r) for r in rows]


async def approve_span(
    conn: asyncpg.Connection,
    audit_id: int,
    reviewer_upn: str,
) -> None:
    """Mark an audit row as reviewed-and-approved."""
    await conn.execute(
        """
        UPDATE redaction_audit
        SET reviewer_upn = $1, reviewed_at = $2
        WHERE id = $3 AND reviewer_upn IS NULL
        """,
        reviewer_upn, datetime.now(timezone.utc), audit_id,
    )
```

- [ ] **Step 4: GREEN**

```bash
.venv/bin/python -m pytest tests/services/redaction/test_audit_writes.py -v
```

Expected: 3 PASSED.

- [ ] **Step 5: Commit**

```bash
git add services/redaction/audit.py tests/services/redaction/test_audit_writes.py
git commit -m "feat(redaction): audit writes + list_pending + approve_span"
```

---

## Task 7: Apply-and-ingest (`services/redaction/ingest.py`)

**Files:**
- Create: `services/redaction/ingest.py`
- Create: `tests/services/redaction/test_ingest.py`

- [ ] **Step 1: Failing test**

`tests/services/redaction/test_ingest.py`:

```python
"""Apply approved redactions and ingest redacted chunks into corpus_chunks (source_type='internal_opinion')."""
from __future__ import annotations

import pytest

from services.redaction.ingest import apply_and_ingest


@pytest.fixture(autouse=True)
async def fresh_db(postgresql):
    await postgresql.execute("TRUNCATE TABLE redaction_audit, corpus_chunks RESTART IDENTITY")
    return postgresql


@pytest.mark.asyncio
async def test_apply_redacts_only_approved_spans(fresh_db):
    text = "Hello John Smith aged 42 phone 941-555-0100 SSN 123-45-6789 end."
    # Pre-insert two audit rows; only one approved.
    await fresh_db.execute(
        """
        INSERT INTO redaction_audit (source_doc_id, original_span_start, original_span_end,
            original_text, redaction_reason, detector, reviewer_upn, reviewed_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
        """,
        "doc-1", 6, 16, "John Smith", "pii_name", "llm:phi4", "reviewer@x",
    )
    await fresh_db.execute(
        """
        INSERT INTO redaction_audit (source_doc_id, original_span_start, original_span_end,
            original_text, redaction_reason, detector, reviewer_upn)
        VALUES ($1, $2, $3, $4, $5, $6, NULL)
        """,
        "doc-1", 51, 62, "123-45-6789", "pii_ssn_or_id", "regex:ssn",
    )

    chunk_id = await apply_and_ingest(
        fresh_db,
        source_doc_id="doc-1",
        original_text=text,
        section_path="Memorandum / Background",
        citation="Manatee County Attorney Opinion stub-doc-1 (2024)",
    )
    assert chunk_id is not None

    row = await fresh_db.fetchrow("SELECT body, source_type FROM corpus_chunks WHERE id = $1", chunk_id)
    assert row["source_type"] == "internal_opinion"
    # John Smith redacted; SSN NOT redacted (not approved)
    assert "[REDACTED:pii_name]" in row["body"]
    assert "John Smith" not in row["body"]
    assert "123-45-6789" in row["body"]


@pytest.mark.asyncio
async def test_apply_with_no_approved_spans_still_creates_chunk(fresh_db):
    """If nothing is approved, original text is ingested verbatim — but with source_type='internal_opinion'."""
    chunk_id = await apply_and_ingest(
        fresh_db, source_doc_id="doc-2", original_text="Clean text.",
        section_path="x", citation="x",
    )
    row = await fresh_db.fetchrow("SELECT body FROM corpus_chunks WHERE id = $1", chunk_id)
    assert row["body"] == "Clean text."


@pytest.mark.asyncio
async def test_apply_links_redaction_audit_rows_to_chunk(fresh_db):
    """After ingest, approved audit rows should have chunk_id set."""
    text = "Hello John Smith end."
    await fresh_db.execute(
        """
        INSERT INTO redaction_audit (source_doc_id, original_span_start, original_span_end,
            original_text, redaction_reason, detector, reviewer_upn, reviewed_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
        """,
        "doc-3", 6, 16, "John Smith", "pii_name", "llm:phi4", "reviewer@x",
    )
    chunk_id = await apply_and_ingest(
        fresh_db, source_doc_id="doc-3", original_text=text,
        section_path="x", citation="x",
    )
    row = await fresh_db.fetchrow(
        "SELECT chunk_id FROM redaction_audit WHERE source_doc_id = 'doc-3' AND reviewer_upn IS NOT NULL"
    )
    assert row["chunk_id"] == chunk_id
```

- [ ] **Step 2: RED**

```bash
.venv/bin/python -m pytest tests/services/redaction/test_ingest.py -v
```

Expected: 3 FAILED.

- [ ] **Step 3: Implement `ingest.py`**

`services/redaction/ingest.py`:

```python
"""Apply approved redactions and ingest into corpus_chunks.

Per spec ADR-007 stage 4: spans with reviewer_upn IS NOT NULL are applied;
pending spans are left in audit and skipped. The redacted text is INSERTed
into corpus_chunks as source_type='internal_opinion'. The approved audit
rows are back-linked via chunk_id.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import asyncpg


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def apply_and_ingest(
    conn: asyncpg.Connection,
    source_doc_id: str,
    original_text: str,
    section_path: str,
    citation: str,
) -> int:
    """Apply approved spans to original_text and INSERT a corpus_chunks row.
    Returns the new chunk's id. Approved redaction_audit rows are back-linked.
    """
    # 1. Fetch approved spans for this doc, sorted by start desc (so we can splice from end)
    approved = await conn.fetch(
        """
        SELECT id, original_span_start, original_span_end, redaction_reason
        FROM redaction_audit
        WHERE source_doc_id = $1 AND reviewer_upn IS NOT NULL
        ORDER BY original_span_start DESC
        """,
        source_doc_id,
    )

    # 2. Splice in [REDACTED:<reason>] from end to start (preserves earlier offsets)
    redacted = original_text
    for r in approved:
        start = r["original_span_start"]
        end = r["original_span_end"]
        reason = r["redaction_reason"]
        redacted = redacted[:start] + f"[REDACTED:{reason}]" + redacted[end:]

    # 3. INSERT chunk
    chunk_id = await conn.fetchval(
        """
        INSERT INTO corpus_chunks (
            source_id, source_type, section_path, citation, body, sha256, valid_from
        ) VALUES ($1, 'internal_opinion', $2, $3, $4, $5, $6)
        RETURNING id
        """,
        f"internal.opinion.{source_doc_id}",
        section_path, citation, redacted, _sha256(redacted),
        datetime.now(timezone.utc),
    )

    # 4. Back-link approved audit rows
    if approved:
        await conn.execute(
            "UPDATE redaction_audit SET chunk_id = $1 WHERE id = ANY($2)",
            chunk_id, [r["id"] for r in approved],
        )

    return chunk_id
```

- [ ] **Step 4: GREEN**

```bash
.venv/bin/python -m pytest tests/services/redaction/test_ingest.py -v
```

Expected: 3 PASSED.

- [ ] **Step 5: Commit**

```bash
git add services/redaction/ingest.py tests/services/redaction/test_ingest.py
git commit -m "feat(redaction): apply_and_ingest — approved spans → corpus_chunks + back-link audit"
```

---

## Task 8: Pipeline orchestrator + CLI

**Files:**
- Create: `services/redaction/pipeline.py`
- Create: `services/redaction/cli.py`
- Create: `tests/services/redaction/test_pipeline_integration.py`

- [ ] **Step 1: Failing test**

`tests/services/redaction/test_pipeline_integration.py`:

```python
"""End-to-end pipeline test against stub-code_enforcement_litigation-1.md."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest

from services.redaction.pipeline import process_document
from services.redaction.detectors.regex_detectors import DetectedSpan


@pytest.fixture(autouse=True)
async def fresh_db(postgresql):
    await postgresql.execute("TRUNCATE TABLE redaction_audit, corpus_chunks RESTART IDENTITY")
    return postgresql


STUB_PATH = Path(__file__).resolve().parents[3] / "corpus-data" / "stubs" / "stub-code_enforcement_litigation-1.md"


@pytest.mark.asyncio
async def test_pipeline_creates_audit_rows_from_stub(fresh_db):
    # Mock LLM detector to return no extra spans (let regex carry the load for this test)
    with patch("services.redaction.pipeline.LlmDetector") as MockLlm:
        instance = MockLlm.return_value
        instance.detect = AsyncMock(return_value=[])

        result = await process_document(fresh_db, STUB_PATH, source_doc_id="stub-ce-1")

    assert result.spans_detected >= 4  # at minimum: 1 SSN + 1 phone + 1 Bates + (LLM=0 in this test)
    pending_rows = await fresh_db.fetch(
        "SELECT * FROM redaction_audit WHERE source_doc_id = 'stub-ce-1' AND reviewer_upn IS NULL"
    )
    assert len(pending_rows) >= 4
    # Confirm SSN was detected
    assert any(r["redaction_reason"] == "pii_ssn_or_id" for r in pending_rows)


@pytest.mark.asyncio
async def test_pipeline_does_not_ingest_until_approved(fresh_db):
    with patch("services.redaction.pipeline.LlmDetector") as MockLlm:
        MockLlm.return_value.detect = AsyncMock(return_value=[])
        await process_document(fresh_db, STUB_PATH, source_doc_id="stub-ce-1")
    chunks_count = await fresh_db.fetchval("SELECT COUNT(*) FROM corpus_chunks WHERE source_type = 'internal_opinion'")
    assert chunks_count == 0  # nothing approved yet
```

- [ ] **Step 2: RED**

```bash
.venv/bin/python -m pytest tests/services/redaction/test_pipeline_integration.py -v
```

Expected: 2 FAILED.

- [ ] **Step 3: Implement `pipeline.py` + `cli.py`**

`services/redaction/pipeline.py`:

```python
"""Pipeline orchestrator: file → detect (regex + LLM) → audit writes.
Does NOT auto-ingest; that happens only after human review approves spans via approve_span.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import asyncpg

from .audit import write_pending_spans
from .detectors.regex_detectors import detect_all as regex_detect, DetectedSpan
from .detectors.llm_detector import LlmDetector


@dataclass
class PipelineResult:
    source_doc_id: str
    spans_detected: int


def _load_document_text(path: Path) -> str:
    """Load text content. .md → str; .pdf → pdfminer.six extract; .txt → str."""
    suffix = path.suffix.lower()
    if suffix in {".md", ".txt"}:
        return path.read_text()
    if suffix == ".pdf":
        from pdfminer.high_level import extract_text
        return extract_text(str(path))
    raise ValueError(f"Unsupported document format: {suffix}")


async def process_document(
    conn: asyncpg.Connection,
    path: Path,
    source_doc_id: str,
    llm_model: str = "phi4",
) -> PipelineResult:
    """Run detection (regex + LLM) over the document; write pending audit rows."""
    text = _load_document_text(path)
    regex_spans = regex_detect(text)

    llm = LlmDetector(model=llm_model)
    llm_spans = await llm.detect(text)

    all_spans: list[DetectedSpan] = list(regex_spans) + list(llm_spans)
    inserted = await write_pending_spans(conn, source_doc_id, all_spans)

    return PipelineResult(source_doc_id=source_doc_id, spans_detected=inserted)
```

`services/redaction/cli.py`:

```python
"""CLI entrypoint: python -m services.redaction process <path> [--source-doc-id ID]

For v0.2.1a, human review is manual (psql query on redaction_audit table).
v0.2.1b adds a review queue UX.
"""
from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

import asyncpg

from .pipeline import process_document


def main():
    parser = argparse.ArgumentParser(prog="services.redaction")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_process = sub.add_parser("process", help="Run detection over a document; write pending audit rows.")
    p_process.add_argument("path", type=Path)
    p_process.add_argument("--source-doc-id", required=True)
    p_process.add_argument("--llm-model", default=os.environ.get("OLLAMA_REDACTION_MODEL", "phi4"))

    args = parser.parse_args()

    async def run():
        db_url = os.environ["DATABASE_URL"]
        conn = await asyncpg.connect(db_url)
        try:
            if args.cmd == "process":
                result = await process_document(
                    conn, args.path, args.source_doc_id, llm_model=args.llm_model
                )
                print(f"Detected {result.spans_detected} spans for {result.source_doc_id}. "
                      f"Pending review — query: SELECT * FROM redaction_audit "
                      f"WHERE source_doc_id = '{result.source_doc_id}' AND reviewer_upn IS NULL;")
        finally:
            await conn.close()

    asyncio.run(run())


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: GREEN**

```bash
.venv/bin/python -m pytest tests/services/redaction/test_pipeline_integration.py -v
```

Expected: 2 PASSED.

- [ ] **Step 5: Final regression**

```bash
.venv/bin/python -m pytest -q
```

Expected: ~107 passed (89 from after Plan A + ~18 new from Plan B).

- [ ] **Step 6: Commit**

```bash
git add services/redaction/pipeline.py services/redaction/cli.py tests/services/redaction/test_pipeline_integration.py
git commit -m "feat(redaction): pipeline orchestrator + CLI — file → detect → audit rows pending review"
```

- [ ] **Step 7: Push**

```bash
git push origin feat/v0.2.0a-backend
```

- [ ] **Step 8: Update `pending_work.md`** — strike v0.2.1a Stream B engineering items; keep Stream B governance items (Legal email, redaction reviewers).

---

## Self-Review

**Spec coverage check** (against `2026-05-11-v0_2_1a-design.md` Stream B scope):

- §5.1 governance activities — out of plan scope (user-driven; tracked in pending_work.md) ✓
- §5.2 18 stub opinions across 6 matter types → Task 3 ✓
- §5.3 pipeline 4-stage architecture (detect → audit → review → apply) → Tasks 4 (regex), 5 (LLM), 6 (audit), 7 (apply), 8 (orchestrator) ✓
- §5.4 redaction reason enum → Task 2 ✓
- §15 W4 spec acceptance — concrete regex patterns + 800-word minimum → Task 3 ✓
- §15 W5 detector + audit contract — order-of-operations enforced (audit rows BEFORE apply) → Tasks 6, 7, 8 ✓

**Out of scope** (correctly deferred):
- Human review queue UX (ADR-007 explicitly defers to v0.2.1b — for v0.2.1a, manual psql per CLI's printed instruction)
- Encryption-at-rest for `original_text` in `redaction_audit` (ADR mentions "optional" — v0.2.1b)
- Real opinion ingestion (Stream B governance; engineering scaffolds against stubs)
- pgvector embedding column conversion (Plan C)

**Placeholder scan:** Task 1 + Task 3's stub template have `<auto-generated>` and template-style placeholders that the implementer fills in (alembic revision id; per-stub substantive content). All other code is concrete.

**Type/path consistency:**
- `DetectedSpan` dataclass shape consistent across Tasks 4, 5, 6, 7, 8 ✓
- `RedactionReason` enum values consistent between Task 2 model + Task 4 regex detectors + Task 5 LLM prompt ✓
- `redaction_audit` table columns (Task 1) match Pydantic model fields (Task 2) ✓
- `source_id` format `internal.opinion.<source_doc_id>` consistent in Task 7 ingest ✓
- CLI `--source-doc-id` flag name consistent with internal `source_doc_id` parameter ✓

**Risk acknowledgment:**
- Task 3 is the longest pole (3-4 hours of careful stub authoring). If an implementer subagent rushes, the stubs lose realism + diversity. Worth budgeting full attention.
- Task 5's LLM detector tests mock Ollama. Real Ollama on `bcc-ap-infer01` must be running with `phi4` for the integration smoke (Task 8) to exercise the actual LLM path. The integration smoke MOCKS the LLM by default; a `--live-llm` pytest flag could be added in v0.2.1b for ad-hoc real-Ollama runs.
- Task 1 depends on Plan A's `corpus_chunks` migration. If Plan A is BLOCKED at execution time, Plan B's Task 1 MUST run after Plan A's Task 1.

---

**Plan complete and saved to `docs/superpowers/plans/2026-05-11-v0_2_1a-stream-b-redaction.md`.**

Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task; expected ~6-8h wall time. **Task 3 (stub authoring) is the biggest single time sink** — 3-4 hours of careful writing for 18 files. If running as a background subagent, consider splitting Task 3 across 2-3 sub-dispatches (6 stubs per dispatch) so context stays focused per matter type.
2. **Inline Execution** — same TDD shape; faster turnaround but Task 3 still demands focused authoring time.

Plan B is sequenced AFTER Plan A (depends on Plan A's `corpus_chunks` migration landing). If Plan A is still running when Plan B starts, gate Task 1 on Plan A's Task 1 completion.

After Plans B + A + C + D ship, v0.2.1a is complete. Then Stream B governance work (Legal email, real opinion access) replaces stubs incrementally — no further plan writing needed; the same `process_document` CLI handles both stubs and real PDFs.
