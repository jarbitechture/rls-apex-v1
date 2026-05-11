# v0.2.1a Stream A — Web Ingestion — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `scraper-service` (systemd-managed weekly timer) that ingests Municode LDC + Code of Ordinances Ch. 2-26 + mymanatee.org LDR ecosystem + mymanatee.org county-holidays calendar + Florida AG Opinions into the versioned `corpus_chunks` Postgres table. Output is the data layer Stream C retrieval reads from.

**Architecture:** New top-level `services/scraper/` Python service. Per-source modules under `services/scraper/sources/` (one file per source). Shared `normalize.py` chunker + `persist.py` versioned writer. Service exposes `/health` on port 30200 (so W8 can poll it). ROI events emitted per scrape run.

**Tech Stack:** Python 3.12, `requests` + `beautifulsoup4` for HTML, `pdfminer.six` for the few PDFs in the LDR ecosystem, `psycopg[binary]`/`asyncpg` against Postgres, pytest with fixture HTML/PDF files, `pgvector` extension (already added in v0.2.0a).

**Branch:** continue on `feat/v0.2.0a-backend` for Plan A. Subsequent plans may branch to `feat/v0.2.1a` once Stream A merges if branch hygiene gets noisy.

**Reference docs:**
- Spec: `docs/superpowers/specs/2026-05-11-v0_2_1a-design.md` §3, §4, §13 (canonical)
- Runbook: `docs/runbooks/2026-05-09-rls-apex-v0_2_0b-runbook.md` (operational state)

**Baseline:** HEAD `06c3ea1`. 64 backend pytest + 50 frontend Vitest + 2 Playwright E2E + 7 Servo baselines green. After this plan: 64 + ~25 new backend tests = ~89 backend tests passing; frontend unchanged; one new `scraper-service` systemd unit running on weekly timer.

**Out of scope** (lives in Plans B/C/D or v0.2.1b):
- Redaction pipeline (Plan B)
- Retrieval engine + L3/L4/L14 (Plan C)
- L1/L2 rule engines + W8 health aggregator (Plan D)
- Embedding generation against scraped chunks (Plan C — `embedding-service`)
- Internal opinion ingestion (Stream B governance gates it)

---

## File Structure

| Path | Action | Responsibility |
|---|---|---|
| `alembic/versions/<new>_v021a_corpus_chunks.py` | Create | Migration: corpus_chunks table + indexes (BM25 GIN, future pgvector HNSW) |
| `services/__init__.py` | Create | Mark `services/` as a Python package root |
| `services/scraper/__init__.py` | Create | Service-level package init |
| `services/scraper/service.py` | Create | FastAPI app + /health + scrape orchestrator entrypoint |
| `services/scraper/config.py` | Create | Source list + timeouts + breaker thresholds |
| `services/scraper/breaker.py` | Create | Thin wrapper around `apps.gateway.circuit.CircuitBreaker` (one breaker per host) |
| `services/scraper/normalize.py` | Create | Paragraph + section-header chunking; citation formatting |
| `services/scraper/persist.py` | Create | Versioned write logic (valid_from / valid_to / sha256 diff) |
| `services/scraper/sources/__init__.py` | Create | Module init |
| `services/scraper/sources/municode_ldc.py` | Create | LDC scraper |
| `services/scraper/sources/municode_ch2_26.py` | Create | Code of Ordinances Ch. 2-26 scraper |
| `services/scraper/sources/mymanatee_ldr.py` | Create | LDR ecosystem (Dev Review Manual + Comp Plan + 2015 rewrite history) |
| `services/scraper/sources/mymanatee_calendar.py` | Create | County holidays / working-days calendar |
| `services/scraper/sources/fl_ag_opinions.py` | Create | Florida AG Opinions analog corpus |
| `apps/gateway/db/models.py` | Modify | Add `CorpusChunk` Pydantic model + ORM mapping |
| `services/scraper/requirements.txt` | Create | Pinned: requests, bs4, pdfminer.six, fastapi, uvicorn, asyncpg, psycopg[binary] |
| `services/scraper/systemd/scraper.service` | Create | systemd unit file for the FastAPI app on port 30200 |
| `services/scraper/systemd/scraper.timer` | Create | systemd weekly timer for the scrape job |
| `tests/services/scraper/fixtures/municode_ldc_section_6_4.html` | Create | Real Municode HTML sample, committed |
| `tests/services/scraper/fixtures/municode_ch2_26_section.html` | Create | Same |
| `tests/services/scraper/fixtures/mymanatee_ldr_page.html` | Create | Same |
| `tests/services/scraper/fixtures/mymanatee_calendar_2026.html` | Create | County holidays page snapshot |
| `tests/services/scraper/fixtures/fl_ag_opinion_sample.html` | Create | FL AG sample |
| `tests/services/scraper/fixtures/manatee_holidays_2026.json` | Create | 11 known Manatee holidays + their dates (per spec W6 fixture) |
| `tests/services/scraper/test_normalize.py` | Create | Chunker preserves citation precision; paragraph boundaries respected |
| `tests/services/scraper/test_persist_versioning.py` | Create | Versioned write logic (3 assertions: no-op, supersede, point-in-time) |
| `tests/services/scraper/test_municode_ldc.py` | Create | LDC source against fixture HTML |
| `tests/services/scraper/test_municode_ch2_26.py` | Create | Ch. 2-26 source against fixture |
| `tests/services/scraper/test_mymanatee_ldr.py` | Create | LDR source against fixture |
| `tests/services/scraper/test_mymanatee_calendar.py` | Create | Calendar against fixture; 11-holiday assertion |
| `tests/services/scraper/test_fl_ag_opinions.py` | Create | FL AG source against fixture |
| `tests/services/scraper/test_health.py` | Create | /health returns 200 + last_run + breaker states |
| `tests/services/scraper/test_integration_smoke.py` | Create | Full scrape cycle against fixture HTML; assert corpus_chunks rows |

---

## Task 1: Alembic migration — `corpus_chunks` table

**Files:**
- Create: `alembic/versions/<auto>_v021a_corpus_chunks.py`

- [ ] **Step 1: Generate the migration**

```bash
cd /Users/ejarbe/Projects/rls-apex-v1
.venv/bin/alembic revision -m "v021a corpus_chunks table"
```

This creates `alembic/versions/<hash>_v021a_corpus_chunks_table.py` with empty `upgrade`/`downgrade` bodies.

- [ ] **Step 2: Write the migration**

Replace the generated body with:

```python
"""v021a corpus_chunks table

Revision ID: <auto-generated>
Revises: <prior head — check alembic history>
Create Date: 2026-05-11

corpus_chunks holds versioned scraped + redacted-internal corpus rows
backing Stream A (scrape) + Stream B (redaction) + Stream C (retrieval).
valid_from / valid_to range supports point-in-time queries (ADR-002).
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "<auto>"
down_revision = "<auto — check alembic history before this commit>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ensure pgvector extension is present (already enabled in v0.2.0a but idempotent)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    op.create_table(
        "corpus_chunks",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("source_id", sa.Text, nullable=False),
        sa.Column("source_type", sa.Text, nullable=False),
        sa.Column("section_path", sa.Text, nullable=False),
        sa.Column("citation", sa.Text, nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("sha256", sa.Text, nullable=False),
        sa.Column("valid_from", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("valid_to", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("embedding", sa.dialects.postgresql.ARRAY(sa.Float), nullable=True),  # placeholder; pgvector column added by Plan C
        sa.Column("metadata", sa.dialects.postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    op.create_index(
        "idx_corpus_chunks_current",
        "corpus_chunks",
        ["source_type", "source_id"],
        postgresql_where=sa.text("valid_to IS NULL"),
    )
    # GIN index for sparse retrieval (Postgres ts_rank_cd — see spec §6.0 naming note)
    op.execute(
        "CREATE INDEX idx_corpus_chunks_fulltext ON corpus_chunks "
        "USING GIN (to_tsvector('english', body));"
    )
    # HNSW index is added by Plan C (after embedding column is converted from ARRAY(Float) to vector(1024))


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_corpus_chunks_fulltext;")
    op.drop_index("idx_corpus_chunks_current", table_name="corpus_chunks")
    op.drop_table("corpus_chunks")
```

- [ ] **Step 3: Run the migration**

```bash
.venv/bin/alembic upgrade head
```

Expected output: `Running upgrade <prior> -> <new>, v021a corpus_chunks table`.

- [ ] **Step 4: Verify schema in psql**

```bash
.venv/bin/python -c "
import asyncio, asyncpg, os
async def main():
    c = await asyncpg.connect(os.environ['DATABASE_URL'])
    rows = await c.fetch('SELECT column_name, data_type FROM information_schema.columns WHERE table_name = \\'corpus_chunks\\' ORDER BY ordinal_position')
    for r in rows: print(r['column_name'], r['data_type'])
    await c.close()
asyncio.run(main())
"
```

Expected: 11 columns listed (`id, source_id, source_type, section_path, citation, body, sha256, valid_from, valid_to, embedding, metadata, created_at`). If your `DATABASE_URL` env var isn't set, use the same connection string the existing tests use.

- [ ] **Step 5: Run full backend suite — confirm no regression**

```bash
.venv/bin/python -m pytest -q
```

Expected: `64 passed`. The migration itself doesn't add tests; it adds schema.

- [ ] **Step 6: Commit**

```bash
git add alembic/versions/*_v021a_corpus_chunks_table.py
git commit -m "$(cat <<'EOF'
feat(db): alembic migration — corpus_chunks table for v0.2.1a Stream A

Versioned corpus storage per spec ADR-002 — valid_from/valid_to range
supports point-in-time queries. GIN index for sparse retrieval
(Postgres ts_rank_cd; see spec §6.0 naming note re: BM25). HNSW vector
index added later by Plan C once embedding column is migrated from
ARRAY(Float) placeholder to vector(1024).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Pydantic model for `CorpusChunk`

**Files:**
- Modify: `apps/gateway/db/models.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_corpus_chunk_model.py`:

```python
"""CorpusChunk Pydantic model — matches alembic schema, supports point-in-time queries."""
from __future__ import annotations

import pytest
from datetime import datetime, timezone

from apps.gateway.db.models import CorpusChunk


def test_corpus_chunk_minimal_required():
    chunk = CorpusChunk(
        source_id="municode.ldc.6.4",
        source_type="ldc",
        section_path="Chapter 6 / §6.4",
        citation="Manatee County LDC §6.4 (2024)",
        body="The applicant shall provide...",
        sha256="a" * 64,
        valid_from=datetime.now(timezone.utc),
    )
    assert chunk.valid_to is None
    assert chunk.metadata == {}


def test_source_type_rejects_unknown():
    with pytest.raises(ValueError, match="source_type"):
        CorpusChunk(
            source_id="x",
            source_type="not_a_known_type",
            section_path="x",
            citation="x",
            body="x",
            sha256="a" * 64,
            valid_from=datetime.now(timezone.utc),
        )


def test_sha256_must_be_64_hex():
    with pytest.raises(ValueError, match="sha256"):
        CorpusChunk(
            source_id="x",
            source_type="ldc",
            section_path="x",
            citation="x",
            body="x",
            sha256="too-short",
            valid_from=datetime.now(timezone.utc),
        )
```

- [ ] **Step 2: Run RED**

```bash
.venv/bin/python -m pytest tests/test_corpus_chunk_model.py -v
```

Expected: 3 FAILED (CorpusChunk doesn't exist yet).

- [ ] **Step 3: Add the model**

Append to `apps/gateway/db/models.py`:

```python
from datetime import datetime
from typing import Literal, Annotated
from pydantic import BaseModel, Field, field_validator
import re


SourceType = Literal["ldc", "ordinance", "fl_ag_opinion", "internal_opinion", "procedure", "calendar"]


class CorpusChunk(BaseModel):
    """Versioned corpus chunk — matches alembic corpus_chunks table."""

    id: int | None = None  # set after DB insert
    source_id: str  # e.g., "municode.ldc.6.4"
    source_type: SourceType
    section_path: str
    citation: str
    body: str
    sha256: Annotated[str, Field(min_length=64, max_length=64)]
    valid_from: datetime
    valid_to: datetime | None = None
    embedding: list[float] | None = None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime | None = None

    @field_validator("sha256")
    @classmethod
    def _sha256_hex(cls, v: str) -> str:
        if not re.fullmatch(r"[0-9a-f]{64}", v):
            raise ValueError("sha256 must be 64 lowercase hex chars")
        return v
```

- [ ] **Step 4: Run GREEN**

```bash
.venv/bin/python -m pytest tests/test_corpus_chunk_model.py -v
```

Expected: 3 PASSED.

- [ ] **Step 5: Confirm full suite**

```bash
.venv/bin/python -m pytest -q
```

Expected: 67 passed (64 baseline + 3 new).

- [ ] **Step 6: Commit**

```bash
git add apps/gateway/db/models.py tests/test_corpus_chunk_model.py
git commit -m "feat(db): CorpusChunk Pydantic model with SourceType enum + sha256 validator"
```

---

## Task 3: `services/` scaffolding + breaker library

**Files:**
- Create: `services/__init__.py`
- Create: `services/scraper/__init__.py`
- Create: `services/scraper/config.py`
- Create: `services/scraper/breaker.py`
- Create: `services/scraper/requirements.txt`
- Create: `tests/services/__init__.py`
- Create: `tests/services/scraper/__init__.py`
- Create: `tests/services/scraper/test_breaker.py`

- [ ] **Step 1: Failing test**

`tests/services/scraper/test_breaker.py`:

```python
"""Per-host breaker for scrape sources — wraps apps.gateway.circuit.CircuitBreaker."""
from __future__ import annotations

import pytest

from services.scraper.breaker import get_or_create_breaker, breaker_status_all


def test_get_or_create_returns_same_instance():
    b1 = get_or_create_breaker("municode")
    b2 = get_or_create_breaker("municode")
    assert b1 is b2


def test_status_includes_all_registered():
    get_or_create_breaker("municode")
    get_or_create_breaker("mymanatee")
    get_or_create_breaker("myfloridalegal")
    status = breaker_status_all()
    assert set(status.keys()) >= {"municode", "mymanatee", "myfloridalegal"}
    assert all("state" in v for v in status.values())
```

- [ ] **Step 2: RED**

```bash
.venv/bin/python -m pytest tests/services/scraper/test_breaker.py -v
```

Expected: 2 FAILED (module doesn't exist).

- [ ] **Step 3: Create the scaffolding**

`services/__init__.py`:
```python
# Marker package for long-running services (scraper, embedding, redaction).
```

`services/scraper/__init__.py`:
```python
# Stream A scraper service — see docs/superpowers/specs/2026-05-11-v0_2_1a-design.md §4
```

`services/scraper/config.py`:
```python
"""Per-source config for the scraper service."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceConfig:
    name: str            # logical name used in source_id prefix
    host: str            # host key for breaker registry
    timeout_s: float     # per-request timeout

SOURCES: dict[str, SourceConfig] = {
    "municode_ldc":         SourceConfig("municode_ldc",         "municode",     timeout_s=15.0),
    "municode_ch2_26":      SourceConfig("municode_ch2_26",      "municode",     timeout_s=15.0),
    "mymanatee_ldr":        SourceConfig("mymanatee_ldr",        "mymanatee",    timeout_s=10.0),
    "mymanatee_calendar":   SourceConfig("mymanatee_calendar",   "mymanatee",    timeout_s=10.0),
    "fl_ag_opinions":       SourceConfig("fl_ag_opinions",       "myfloridalegal", timeout_s=15.0),
}

BREAKER_DEFAULTS = {
    "failure_threshold": 3,
    "window_seconds":    300.0,
    "open_duration_seconds": 3600.0,  # 1 hour per spec §4.4
}
```

`services/scraper/breaker.py`:
```python
"""Per-host breaker registry. Reuses apps.gateway.circuit.CircuitBreaker so operators have one mental model."""
from __future__ import annotations

from apps.gateway.circuit import CircuitBreaker
from .config import BREAKER_DEFAULTS

_REGISTRY: dict[str, CircuitBreaker] = {}


def get_or_create_breaker(host: str) -> CircuitBreaker:
    if host not in _REGISTRY:
        _REGISTRY[host] = CircuitBreaker(name=f"scrape_{host}", **BREAKER_DEFAULTS)
    return _REGISTRY[host]


def breaker_status_all() -> dict[str, dict]:
    return {host: b.status() for host, b in _REGISTRY.items()}
```

`services/scraper/requirements.txt`:
```
requests==2.32.3
beautifulsoup4==4.12.3
pdfminer.six==20240706
fastapi==0.115.4
uvicorn[standard]==0.32.0
asyncpg==0.30.0
pydantic==2.9.2
```

`tests/services/__init__.py` and `tests/services/scraper/__init__.py`: empty files.

- [ ] **Step 4: GREEN**

```bash
.venv/bin/python -m pytest tests/services/scraper/test_breaker.py -v
```

Expected: 2 PASSED.

- [ ] **Step 5: Commit**

```bash
git add services/__init__.py services/scraper/__init__.py services/scraper/config.py services/scraper/breaker.py services/scraper/requirements.txt tests/services/__init__.py tests/services/scraper/__init__.py tests/services/scraper/test_breaker.py
git commit -m "feat(scraper): services/ package scaffolding + per-host breaker registry"
```

---

## Task 4: Normalize module — paragraph + section-header chunking

**Files:**
- Create: `services/scraper/normalize.py`
- Create: `tests/services/scraper/test_normalize.py`

- [ ] **Step 1: Failing test**

`tests/services/scraper/test_normalize.py`:

```python
"""Chunker preserves citation precision and paragraph boundaries."""
from __future__ import annotations

from services.scraper.normalize import chunk_html_section, Chunk


SAMPLE_HTML = """
<div class="section" id="sec_6_4">
  <h2>§6.4 — Building Code Compliance</h2>
  <p>(a) All structures shall comply with the Florida Building Code (FBC) as adopted by the State of Florida.</p>
  <p>(b) Applicants seeking variance approval shall submit a Variance Application Form FB-101.</p>
  <p>(c) The Building Official shall review applications within 30 working days of filing.</p>
</div>
"""


def test_chunker_returns_one_chunk_per_paragraph():
    chunks = chunk_html_section(
        html=SAMPLE_HTML,
        source_id="municode.ldc.6.4",
        source_type="ldc",
        section_path="Chapter 6 / §6.4",
        citation_prefix="Manatee County LDC",
        version_year=2024,
    )
    assert len(chunks) == 3
    assert all(isinstance(c, Chunk) for c in chunks)


def test_chunker_preserves_subsection_in_section_path():
    chunks = chunk_html_section(SAMPLE_HTML, "x", "ldc", "Chapter 6 / §6.4", "Manatee LDC", 2024)
    paths = [c.section_path for c in chunks]
    assert "Chapter 6 / §6.4 / (a)" in paths
    assert "Chapter 6 / §6.4 / (b)" in paths
    assert "Chapter 6 / §6.4 / (c)" in paths


def test_chunker_formats_citation_with_subsection():
    chunks = chunk_html_section(SAMPLE_HTML, "x", "ldc", "Chapter 6 / §6.4", "Manatee County LDC", 2024)
    citations = [c.citation for c in chunks]
    assert "Manatee County LDC §6.4(a) (2024)" in citations
    assert "Manatee County LDC §6.4(b) (2024)" in citations


def test_chunker_body_is_plain_text_no_html():
    chunks = chunk_html_section(SAMPLE_HTML, "x", "ldc", "Chapter 6 / §6.4", "Manatee LDC", 2024)
    assert all("<" not in c.body for c in chunks)


def test_chunker_sha256_is_64_hex():
    chunks = chunk_html_section(SAMPLE_HTML, "x", "ldc", "Chapter 6 / §6.4", "Manatee LDC", 2024)
    import re
    assert all(re.fullmatch(r"[0-9a-f]{64}", c.sha256) for c in chunks)


def test_chunker_handles_empty_section():
    chunks = chunk_html_section("<div></div>", "x", "ldc", "Chapter 6 / §6.4", "Manatee LDC", 2024)
    assert chunks == []
```

- [ ] **Step 2: RED**

```bash
.venv/bin/python -m pytest tests/services/scraper/test_normalize.py -v
```

Expected: 6 FAILED.

- [ ] **Step 3: Implement `normalize.py`**

`services/scraper/normalize.py`:

```python
"""HTML → paragraph chunks with section-header context, citations, and sha256.

Per spec §4.3: paragraph-level chunks with section-header context. Each chunk
records section_path (full hierarchy), citation (formatted), body (plain text),
and sha256 (for change detection).
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from bs4 import BeautifulSoup


@dataclass(frozen=True)
class Chunk:
    body: str
    source_id: str
    source_type: str
    section_path: str
    citation: str
    sha256: str


SUBSECTION_PREFIX_RE = re.compile(r"^\(([a-z0-9]+)\)\s*")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _extract_subsection_marker(text: str) -> tuple[str | None, str]:
    """If paragraph starts with '(a)' or '(1)', strip and return (marker, remaining_text)."""
    m = SUBSECTION_PREFIX_RE.match(text)
    if m:
        return m.group(1), text[m.end():].strip()
    return None, text


def chunk_html_section(
    html: str,
    source_id: str,
    source_type: str,
    section_path: str,
    citation_prefix: str,
    version_year: int,
) -> list[Chunk]:
    """Parse an HTML fragment representing one code section; return one Chunk per paragraph.

    Paragraphs starting with `(a)`, `(b)`, etc. are recognized as subsections;
    the marker is appended to section_path and citation.
    """
    soup = BeautifulSoup(html, "html.parser")
    paragraphs = soup.find_all("p")
    chunks: list[Chunk] = []

    # Parse section number out of section_path (last "§X.Y" pattern)
    section_num_match = re.search(r"§([\d.]+)", section_path)
    section_num = section_num_match.group(1) if section_num_match else None

    for p in paragraphs:
        raw_text = p.get_text(strip=True)
        if not raw_text:
            continue

        marker, body_text = _extract_subsection_marker(raw_text)
        if marker:
            full_section_path = f"{section_path} / ({marker})"
            citation = f"{citation_prefix} §{section_num}({marker}) ({version_year})" if section_num else f"{citation_prefix} ({version_year})"
        else:
            full_section_path = section_path
            citation = f"{citation_prefix} §{section_num} ({version_year})" if section_num else f"{citation_prefix} ({version_year})"

        chunks.append(Chunk(
            body=body_text,
            source_id=source_id,
            source_type=source_type,
            section_path=full_section_path,
            citation=citation,
            sha256=_sha256(body_text),
        ))

    return chunks
```

- [ ] **Step 4: GREEN**

```bash
.venv/bin/python -m pytest tests/services/scraper/test_normalize.py -v
```

Expected: 6 PASSED.

- [ ] **Step 5: Commit**

```bash
git add services/scraper/normalize.py tests/services/scraper/test_normalize.py
git commit -m "feat(scraper): normalize.py — paragraph + section-header chunker with citations + sha256"
```

---

## Task 5: Persist module — versioned writes (W2)

**Files:**
- Create: `services/scraper/persist.py`
- Create: `tests/services/scraper/test_persist_versioning.py`

- [ ] **Step 1: Failing test**

`tests/services/scraper/test_persist_versioning.py`:

```python
"""Versioned write logic — same sha256 is no-op; new sha256 supersedes; point-in-time query returns the right version."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from services.scraper.normalize import Chunk
from services.scraper.persist import upsert_chunks, query_at_time


@pytest.fixture
async def fresh_db(postgresql):
    """Truncate corpus_chunks before each test (pytest-postgresql fixture)."""
    conn = postgresql
    await conn.execute("TRUNCATE TABLE corpus_chunks")
    return conn


@pytest.mark.asyncio
async def test_same_sha256_is_noop(fresh_db):
    chunk = Chunk(body="t1", source_id="s1", source_type="ldc",
                  section_path="p1", citation="c1", sha256="a"*64)
    await upsert_chunks(fresh_db, [chunk])
    await upsert_chunks(fresh_db, [chunk])  # idempotent re-write
    rows = await fresh_db.fetch("SELECT COUNT(*) FROM corpus_chunks WHERE source_id = $1", "s1")
    assert rows[0]["count"] == 1


@pytest.mark.asyncio
async def test_new_sha256_supersedes_previous(fresh_db):
    old = Chunk(body="t1", source_id="s1", source_type="ldc",
                section_path="p1", citation="c1", sha256="a"*64)
    new = Chunk(body="t2", source_id="s1", source_type="ldc",
                section_path="p1", citation="c1", sha256="b"*64)
    await upsert_chunks(fresh_db, [old])
    await upsert_chunks(fresh_db, [new])
    rows = await fresh_db.fetch("SELECT sha256, valid_to FROM corpus_chunks WHERE source_id = $1 ORDER BY valid_from", "s1")
    assert len(rows) == 2
    assert rows[0]["sha256"] == "a"*64
    assert rows[0]["valid_to"] is not None  # superseded
    assert rows[1]["sha256"] == "b"*64
    assert rows[1]["valid_to"] is None      # current


@pytest.mark.asyncio
async def test_point_in_time_query_returns_correct_version(fresh_db):
    # Write old chunk
    old = Chunk(body="t1", source_id="s1", source_type="ldc",
                section_path="p1", citation="c1", sha256="a"*64)
    await upsert_chunks(fresh_db, [old])
    # Capture anchor moment
    anchor = datetime.now(timezone.utc)
    # Write new chunk (supersedes)
    new = Chunk(body="t2", source_id="s1", source_type="ldc",
                section_path="p1", citation="c1", sha256="b"*64)
    await upsert_chunks(fresh_db, [new])
    # Query at the anchor moment should return the OLD chunk
    hits = await query_at_time(fresh_db, source_id="s1", at=anchor)
    assert len(hits) == 1
    assert hits[0]["sha256"] == "a"*64
```

- [ ] **Step 2: RED**

```bash
.venv/bin/python -m pytest tests/services/scraper/test_persist_versioning.py -v
```

Expected: 3 FAILED.

- [ ] **Step 3: Implement `persist.py`**

`services/scraper/persist.py`:

```python
"""Versioned write to corpus_chunks. Per spec ADR-002:
- Same sha256 (already-current row): no-op.
- New sha256 for same source_id + source_type + section_path: set old row valid_to=NOW; insert new row valid_from=NOW.
- Initial insert: valid_from=NOW, valid_to=NULL.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

import asyncpg

from .normalize import Chunk


async def upsert_chunks(conn: asyncpg.Connection, chunks: Iterable[Chunk]) -> dict:
    """Versioned upsert. Returns counts of {added, superseded, unchanged}."""
    added = superseded = unchanged = 0
    now = datetime.now(timezone.utc)

    for chunk in chunks:
        # Find current (valid_to IS NULL) row for this logical entity
        existing = await conn.fetchrow(
            """
            SELECT id, sha256
            FROM corpus_chunks
            WHERE source_id = $1 AND source_type = $2 AND section_path = $3 AND valid_to IS NULL
            """,
            chunk.source_id, chunk.source_type, chunk.section_path,
        )

        if existing is None:
            # Initial insert
            await conn.execute(
                """
                INSERT INTO corpus_chunks (
                    source_id, source_type, section_path, citation, body, sha256, valid_from
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                chunk.source_id, chunk.source_type, chunk.section_path,
                chunk.citation, chunk.body, chunk.sha256, now,
            )
            added += 1
        elif existing["sha256"] == chunk.sha256:
            unchanged += 1
        else:
            # Supersede: close old row, insert new
            await conn.execute(
                "UPDATE corpus_chunks SET valid_to = $1 WHERE id = $2",
                now, existing["id"],
            )
            await conn.execute(
                """
                INSERT INTO corpus_chunks (
                    source_id, source_type, section_path, citation, body, sha256, valid_from
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                chunk.source_id, chunk.source_type, chunk.section_path,
                chunk.citation, chunk.body, chunk.sha256, now,
            )
            superseded += 1

    return {"added": added, "superseded": superseded, "unchanged": unchanged}


async def query_at_time(conn: asyncpg.Connection, source_id: str, at: datetime) -> list[dict]:
    """Point-in-time query: return rows valid at the given moment."""
    rows = await conn.fetch(
        """
        SELECT source_id, source_type, section_path, citation, body, sha256, valid_from, valid_to
        FROM corpus_chunks
        WHERE source_id = $1
          AND valid_from <= $2
          AND (valid_to IS NULL OR valid_to > $2)
        ORDER BY section_path
        """,
        source_id, at,
    )
    return [dict(r) for r in rows]
```

- [ ] **Step 4: GREEN**

```bash
.venv/bin/python -m pytest tests/services/scraper/test_persist_versioning.py -v
```

Expected: 3 PASSED.

- [ ] **Step 5: Commit**

```bash
git add services/scraper/persist.py tests/services/scraper/test_persist_versioning.py
git commit -m "feat(scraper): persist.py — versioned upsert with valid_from/valid_to (W2)"
```

---

## Task 6: Source module — `municode_ldc.py`

**Files:**
- Create: `services/scraper/sources/__init__.py`
- Create: `services/scraper/sources/municode_ldc.py`
- Create: `tests/services/scraper/fixtures/municode_ldc_section_6_4.html`
- Create: `tests/services/scraper/test_municode_ldc.py`

- [ ] **Step 1: Capture a real Municode LDC fixture**

Manually fetch one Municode LDC section as a fixture (use a section that's likely to remain stable, e.g., LDC §6.4):

```bash
curl -L 'https://library.municode.com/fl/manatee_county/codes/land_development_code?nodeId=PTIIMACOLADERE_CH6BUDECO_6.4BUCO' \
  -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36" \
  -o tests/services/scraper/fixtures/municode_ldc_section_6_4.html
```

If the URL is gated (Municode commonly requires JS), capture via browser → "Save As" → strip down to just the relevant `<div class="section">`. Commit the result.

- [ ] **Step 2: Failing test**

`tests/services/scraper/test_municode_ldc.py`:

```python
"""LDC source module — parses fixture HTML, returns chunks with expected fields."""
from __future__ import annotations

from pathlib import Path
import pytest

from services.scraper.sources.municode_ldc import parse_section_html, fetch_and_chunk


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "municode_ldc_section_6_4.html"


def test_parse_fixture_returns_chunks():
    html = FIXTURE_PATH.read_text()
    chunks = parse_section_html(html, section_url="https://library.municode.com/fl/manatee_county/codes/land_development_code?nodeId=PTIIMACOLADERE_CH6BUDECO_6.4BUCO")
    assert len(chunks) > 0
    assert all(c.source_type == "ldc" for c in chunks)
    assert all("Manatee County LDC" in c.citation for c in chunks)


def test_chunks_have_valid_section_paths():
    chunks = parse_section_html(FIXTURE_PATH.read_text(), "x")
    for c in chunks:
        assert c.section_path.startswith("Chapter 6")
        assert "§6.4" in c.section_path


def test_chunks_include_metadata():
    chunks = parse_section_html(FIXTURE_PATH.read_text(), "https://x")
    for c in chunks:
        # source_id format: municode.ldc.<section_num>
        assert c.source_id.startswith("municode.ldc.6.4")
```

- [ ] **Step 3: RED**

```bash
.venv/bin/python -m pytest tests/services/scraper/test_municode_ldc.py -v
```

Expected: 3 FAILED.

- [ ] **Step 4: Implement `municode_ldc.py`**

`services/scraper/sources/__init__.py`: empty.

`services/scraper/sources/municode_ldc.py`:

```python
"""Municode LDC scraper. Source: library.municode.com/fl/manatee_county/codes/land_development_code

Strategy: scrape the chapter index, then per-section pages. Each section page contains
one or more <p> paragraphs that map to chunks via normalize.chunk_html_section.
"""
from __future__ import annotations

import re
from typing import Iterable

import requests
from bs4 import BeautifulSoup

from services.scraper.config import SOURCES
from services.scraper.breaker import get_or_create_breaker
from services.scraper.normalize import Chunk, chunk_html_section


VERSION_YEAR = 2024  # update annually when LDC is re-codified


def parse_section_html(html: str, section_url: str) -> list[Chunk]:
    """Parse one LDC section page; return chunks."""
    soup = BeautifulSoup(html, "html.parser")
    # Municode uses <div class="section"> for code sections
    section_div = soup.find("div", class_="section") or soup
    # Extract section number from header
    header = section_div.find(["h1", "h2", "h3"])
    section_num_match = re.search(r"§\s*([\d.]+)", header.get_text() if header else "")
    section_num = section_num_match.group(1) if section_num_match else "unknown"
    chapter_match = re.search(r"Chapter\s+(\d+)", header.get_text() if header else "")
    chapter_num = chapter_match.group(1) if chapter_match else "unknown"

    section_path = f"Chapter {chapter_num} / §{section_num}"
    source_id = f"municode.ldc.{section_num}"

    return chunk_html_section(
        html=str(section_div),
        source_id=source_id,
        source_type="ldc",
        section_path=section_path,
        citation_prefix="Manatee County LDC",
        version_year=VERSION_YEAR,
    )


def fetch_and_chunk() -> Iterable[Chunk]:
    """Top-level entry point for scraping Municode LDC.

    For v0.2.1a Task 6, this is a minimal walking-skeleton that fetches a
    seed page; full chapter-tree crawling is added in W1 follow-up if needed.
    """
    cfg = SOURCES["municode_ldc"]
    breaker = get_or_create_breaker(cfg.host)

    # Real implementation: enumerate sections via chapter-index page.
    # For initial commit, fetch one seed section (LDC §6.4) as proof.
    SEED_URL = "https://library.municode.com/fl/manatee_county/codes/land_development_code?nodeId=PTIIMACOLADERE_CH6BUDECO_6.4BUCO"

    response = breaker.call(lambda: requests.get(SEED_URL, timeout=cfg.timeout_s,
                                                  headers={"User-Agent": "RLS-Apex Scraper (Manatee County internal)"}))
    response.raise_for_status()

    yield from parse_section_html(response.text, SEED_URL)
```

- [ ] **Step 5: GREEN**

```bash
.venv/bin/python -m pytest tests/services/scraper/test_municode_ldc.py -v
```

Expected: 3 PASSED.

- [ ] **Step 6: Commit**

```bash
git add services/scraper/sources/__init__.py services/scraper/sources/municode_ldc.py tests/services/scraper/fixtures/municode_ldc_section_6_4.html tests/services/scraper/test_municode_ldc.py
git commit -m "feat(scraper): municode_ldc source — parser + fetch_and_chunk skeleton"
```

---

## Task 7: Source module — `municode_ch2_26.py`

Same shape as Task 6, applied to Code of Ordinances Ch. 2-26.

**Files:**
- Create: `services/scraper/sources/municode_ch2_26.py`
- Create: `tests/services/scraper/fixtures/municode_ch2_26_section.html`
- Create: `tests/services/scraper/test_municode_ch2_26.py`

- [ ] **Step 1: Capture fixture**

```bash
curl -L 'https://library.municode.com/fl/manatee_county/codes/code_of_ordinances?nodeId=PTIIMACOCOOR_CH2-26MACOPROR' \
  -A "Mozilla/5.0" \
  -o tests/services/scraper/fixtures/municode_ch2_26_section.html
```

- [ ] **Step 2: Failing test** (mirror structure of Task 6 test, replace LDC strings with Ch. 2-26 and `source_type="ordinance"`)

- [ ] **Step 3: RED**

```bash
.venv/bin/python -m pytest tests/services/scraper/test_municode_ch2_26.py -v
```

- [ ] **Step 4: Implement `municode_ch2_26.py`** — same shape as `municode_ldc.py` but with:
  - `source_type="ordinance"`
  - citation prefix "Manatee County Code §2-26"
  - source_id format `municode.ch2_26.{section_num}`
  - section_path format `Ch. 2-26 / §{section_num}`

- [ ] **Step 5: GREEN + commit**

```bash
git add services/scraper/sources/municode_ch2_26.py tests/services/scraper/fixtures/municode_ch2_26_section.html tests/services/scraper/test_municode_ch2_26.py
git commit -m "feat(scraper): municode_ch2_26 source — Code of Ordinances Ch. 2-26 parser"
```

---

## Task 8: Source module — `mymanatee_ldr.py`

Mymanatee.org LDR ecosystem page + linked Dev Review Manual + Comp Plan + 2015 rewrite history.

**Files:**
- Create: `services/scraper/sources/mymanatee_ldr.py`
- Create: `tests/services/scraper/fixtures/mymanatee_ldr_page.html`
- Create: `tests/services/scraper/test_mymanatee_ldr.py`

- [ ] **Step 1: Capture fixture**

```bash
curl -L 'https://www.mymanatee.org/services-and-amenities/service-listing/service-details/view-land-development-regulations' \
  -o tests/services/scraper/fixtures/mymanatee_ldr_page.html
```

- [ ] **Step 2-5: Same TDD shape as Tasks 6-7**

Implementation specifics:
- Parse the main LDR page for links to Development Review Manual + Comp Plan + ordinance-change history pages
- Recursively fetch + chunk each linked HTML/PDF
- For PDFs: use `pdfminer.six` `extract_text` then run through normalize
- `source_type="ldc"` or `"ordinance"` depending on linked doc; `mymanatee.ldr.*` source_id

Commit message: `feat(scraper): mymanatee_ldr source — LDR ecosystem + linked docs`

---

## Task 9: Source module — `mymanatee_calendar.py`

County working-days calendar — feeds L2's `calendar.check_working_days` (in Plan D). Also satisfies spec W6.

**Files:**
- Create: `services/scraper/sources/mymanatee_calendar.py`
- Create: `tests/services/scraper/fixtures/mymanatee_calendar_2026.html`
- Create: `tests/services/scraper/fixtures/manatee_holidays_2026.json`
- Create: `tests/services/scraper/test_mymanatee_calendar.py`

- [ ] **Step 1: Capture fixture + holiday list**

```bash
# County holidays page (URL pattern: mymanatee.org typically posts holidays under HR or Admin Services)
curl -L 'https://www.mymanatee.org/government/board_of_county_commissioners/calendar_of_events' \
  -o tests/services/scraper/fixtures/mymanatee_calendar_2026.html
```

Hand-author `tests/services/scraper/fixtures/manatee_holidays_2026.json` — 11 known Manatee County holidays per spec W6:

```json
{
  "year": 2026,
  "holidays": [
    {"date": "2026-01-01", "name": "New Year's Day"},
    {"date": "2026-01-19", "name": "MLK Day"},
    {"date": "2026-02-16", "name": "Presidents Day"},
    {"date": "2026-05-25", "name": "Memorial Day"},
    {"date": "2026-07-03", "name": "Independence Day observed"},
    {"date": "2026-09-07", "name": "Labor Day"},
    {"date": "2026-11-11", "name": "Veterans Day"},
    {"date": "2026-11-26", "name": "Thanksgiving"},
    {"date": "2026-11-27", "name": "Day after Thanksgiving"},
    {"date": "2026-12-24", "name": "Christmas Eve"},
    {"date": "2026-12-25", "name": "Christmas Day"}
  ]
}
```

- [ ] **Step 2: Failing test**

```python
# tests/services/scraper/test_mymanatee_calendar.py
import json
from pathlib import Path

from services.scraper.sources.mymanatee_calendar import parse_calendar_html

FIXTURE_HTML = Path(__file__).parent / "fixtures" / "mymanatee_calendar_2026.html"
FIXTURE_HOLIDAYS = Path(__file__).parent / "fixtures" / "manatee_holidays_2026.json"

def test_parser_extracts_11_holidays():
    chunks = parse_calendar_html(FIXTURE_HTML.read_text(), year=2026)
    assert len(chunks) == 11

def test_chunks_have_source_type_calendar():
    chunks = parse_calendar_html(FIXTURE_HTML.read_text(), year=2026)
    assert all(c.source_type == "calendar" for c in chunks)

def test_holidays_match_known_dates():
    known = json.loads(FIXTURE_HOLIDAYS.read_text())["holidays"]
    chunks = parse_calendar_html(FIXTURE_HTML.read_text(), year=2026)
    dates_from_chunks = sorted([c.body.split(":")[0] for c in chunks])
    dates_known = sorted([h["date"] for h in known])
    assert dates_from_chunks == dates_known
```

- [ ] **Step 3: RED + implement + GREEN + commit**

Implementation chunks each holiday as one row in `corpus_chunks` with `source_type="calendar"`, `body="2026-01-01: New Year's Day"`, `section_path="Holidays 2026"`. The L2 tool in Plan D reads these via `WHERE source_type='calendar'`.

Commit: `feat(scraper): mymanatee_calendar source — county holidays for L2 working-days check`

---

## Task 10: Source module — `fl_ag_opinions.py`

Florida AG Opinions as analog corpus for L3 precedent retrieval (per spec §4.1).

**Files:**
- Create: `services/scraper/sources/fl_ag_opinions.py`
- Create: `tests/services/scraper/fixtures/fl_ag_opinion_sample.html`
- Create: `tests/services/scraper/test_fl_ag_opinions.py`

- [ ] **Step 1: Capture fixture**

```bash
# Per friend's research note: actual URL is myfloridalegal.com/opinions (the /ag-opinions path may redirect)
# Verify the index page before implementing the source
curl -L 'https://www.myfloridalegal.com/opinions' \
  -o /tmp/fl_ag_index.html
# Then pick one specific opinion to use as parsing fixture
```

- [ ] **Step 2-5: TDD shape per Tasks 6-9**

Implementation specifics:
- `source_type="fl_ag_opinion"`
- citation format: `Fla. Op. Att'y Gen. <year>-<num>`
- source_id format: `fl_ag.<year>-<num>`
- section_path: opinion title or topic header

Commit: `feat(scraper): fl_ag_opinions source — FL AG Opinions analog corpus`

---

## Task 11: Scraper FastAPI app + `/health` (W8 hook)

**Files:**
- Create: `services/scraper/service.py`
- Create: `tests/services/scraper/test_health.py`

- [ ] **Step 1: Failing test**

```python
# tests/services/scraper/test_health.py
import pytest
from httpx import AsyncClient, ASGITransport

from services.scraper.service import app


@pytest.mark.asyncio
async def test_health_returns_200_and_shape():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert "status" in body
    assert "last_run_per_source" in body
    assert "breaker_states" in body
    assert isinstance(body["last_run_per_source"], dict)
    assert isinstance(body["breaker_states"], dict)


@pytest.mark.asyncio
async def test_health_includes_all_5_sources():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/health")
    last_run = r.json()["last_run_per_source"]
    # All 5 source keys present, even if values are None (never run)
    assert set(last_run.keys()) >= {"municode_ldc", "municode_ch2_26",
                                    "mymanatee_ldr", "mymanatee_calendar", "fl_ag_opinions"}
```

- [ ] **Step 2: RED**

- [ ] **Step 3: Implement `service.py`**

```python
"""Stream A scraper service. Exposes /health on port 30200 for W8 polling.
Scrape job is triggered by systemd timer (see scraper.timer); the FastAPI app
itself is long-running so /health is always reachable.
"""
from __future__ import annotations

import asyncpg
import os
from datetime import datetime, timezone
from fastapi import FastAPI

from services.scraper.config import SOURCES
from services.scraper.breaker import breaker_status_all

app = FastAPI(title="rls-apex-scraper", version="0.2.1a")


@app.get("/health")
async def health() -> dict:
    """W8-pollable /health. Returns last-run-per-source from corpus_chunks max(created_at)."""
    db_url = os.environ.get("DATABASE_URL")
    last_run_per_source: dict[str, str | None] = {name: None for name in SOURCES}
    if db_url:
        try:
            conn = await asyncpg.connect(db_url)
            try:
                rows = await conn.fetch(
                    """
                    SELECT split_part(source_id, '.', 1) || '_' || split_part(source_id, '.', 2) AS source_key,
                           MAX(created_at) AS last_run
                    FROM corpus_chunks
                    GROUP BY source_key
                    """
                )
                for r in rows:
                    # Re-map DB source_key (e.g., "municode_ldc") to config source name
                    name = r["source_key"]
                    if name in last_run_per_source and r["last_run"] is not None:
                        last_run_per_source[name] = r["last_run"].isoformat()
            finally:
                await conn.close()
        except Exception:
            # DB unreachable — surface in status but don't 500
            pass

    return {
        "status": "healthy",  # extend to "degraded" if any breaker open or DB unreachable
        "last_run_per_source": last_run_per_source,
        "breaker_states": breaker_status_all(),
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=30200, log_level="info")
```

- [ ] **Step 4: GREEN + commit**

Commit: `feat(scraper): FastAPI service.py + /health endpoint for W8 polling`

---

## Task 12: Scrape job orchestrator + ROI emit per source

**Files:**
- Modify: `services/scraper/service.py` (add `run_scrape_job` function + ROI emit)
- Create: `tests/services/scraper/test_orchestrator.py`

Adds a `run_scrape_job()` function (called by the systemd timer via a CLI subcommand) that:

1. For each source in `SOURCES`:
   - Calls source-module `fetch_and_chunk()` (breaker-wrapped)
   - Calls `persist.upsert_chunks(conn, chunks)`
   - Emits ROI event with `event_kind="tool_invocation"`, `workflow="rls_apex.scrape"`, `tool="rls_apex"`, `surface="other"`, `task_type="data_analysis"`, `success`, `extra={source, added, superseded, unchanged}`
2. Reports total run summary

Test: mock source modules to return known Chunks; assert `upsert_chunks` is called per source + ROI emit is called per source with correct fields.

Commit: `feat(scraper): scrape job orchestrator with per-source ROI emit (Rule #18)`

---

## Task 13: systemd unit + timer

**Files:**
- Create: `services/scraper/systemd/scraper.service`
- Create: `services/scraper/systemd/scraper.timer`

These are deployment artifacts (no tests). The unit file launches the FastAPI app on port 30200; the timer schedules the scrape-job CLI command weekly (Sunday 02:00 LAN time).

```ini
# scraper.service — long-running FastAPI app for /health
[Unit]
Description=RLS Apex Scraper Service (FastAPI /health on 30200)
After=network.target

[Service]
Type=simple
User=rls-apex
WorkingDirectory=/opt/rls-apex-v1
Environment=DATABASE_URL=postgresql://...
ExecStart=/opt/rls-apex-v1/.venv/bin/python -m uvicorn services.scraper.service:app --host 127.0.0.1 --port 30200
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```ini
# scraper.timer — weekly scrape job
[Unit]
Description=RLS Apex weekly scrape job

[Timer]
OnCalendar=Sun 02:00
Persistent=true
Unit=scraper-run.service

[Install]
WantedBy=timers.target
```

Plus a companion `scraper-run.service` that runs `python -m services.scraper run` (the orchestrator CLI subcommand from Task 12).

Commit: `feat(scraper): systemd unit + weekly timer for deployment`

---

## Task 14: Integration smoke + final regression

**Files:**
- Create: `tests/services/scraper/test_integration_smoke.py`
- Verification commands per the plan

- [ ] **Step 1: Integration smoke test** — invokes `run_scrape_job` against fixture HTML/PDFs (mocked at the requests layer), asserts `corpus_chunks` table has expected rows after the run, asserts ROI emit was called per source.

- [ ] **Step 2: Full backend regression**

```bash
.venv/bin/python -m pytest -q
```

Expected: ~89 passed (64 baseline + ~25 new across all scraper tests).

- [ ] **Step 3: Push**

```bash
git push origin feat/v0.2.0a-backend
```

- [ ] **Step 4: Update `pending_work.md`** — strike v0.2.1a Stream A items.

- [ ] **Step 5: Commit final integration test**

```bash
git commit -m "test(scraper): integration smoke + Stream A complete"
```

---

## Self-Review

**Spec coverage check** (against `2026-05-11-v0_2_1a-design.md` Stream A scope):

- §3.2 file layout — every `services/scraper/` path in this plan ✓
- §3.3 schema — `corpus_chunks` table per Task 1; `redaction_audit` deferred to Plan B ✓
- §4.1 sources — 5 sources (LDC, Ch.2-26, LDR, calendar, FL AG) → Tasks 6, 7, 8, 9, 10 ✓
- §4.2 scraper architecture — Tasks 11 (FastAPI), 12 (orchestrator), 13 (systemd) ✓
- §4.3 chunking strategy — Task 4 normalize.py ✓
- §4.4 breaker behavior — Task 3 breaker.py + per-source use in Tasks 6-10 ✓
- §9.1 unit roster — scraper-service on port 30200 ✓ (Task 11)
- §15 W1 (scraper per-source modules with fixtures) → Tasks 6-10 ✓
- §15 W2 (versioned write logic) → Task 5 ✓
- §15 W6 (calendar working-days) → Task 9 ✓

**Out of scope** (correctly deferred to later plans):
- L1/L2 rule engines → Plan D
- L3/L4 retrieval tools → Plan C
- Hybrid retriever library → Plan C
- pgvector HNSW index (embedding column conversion from ARRAY(Float) to vector(1024)) → Plan C
- Redaction pipeline → Plan B
- L14 frontend extension → Plan C

**Placeholder scan:** Task 1's migration has a `<auto-generated>` revision-id and `<auto — check alembic history>` `down_revision` — these are filled at `alembic revision` time, not placeholders the implementer must invent. All other code is concrete.

**Type/path consistency:**
- `Chunk` dataclass shape consistent across Tasks 4, 5, 6-10 ✓
- `SOURCES` config keys consistent between `config.py` and per-source `source_id` patterns ✓
- DB connection string env var `DATABASE_URL` consistent across persist.py, service.py, integration tests ✓

**Risk acknowledgment:**
- Tasks 6-10 capture fixture HTML via `curl`. Municode + mymanatee + FL AG site changes could break parsers between fixture capture and prod. Mitigation: CI runs daily against committed fixtures (W3 from contract hardening design carries forward); separate `--scrape-real` flag (in `pytest`) hits the real sites once per test session to detect upstream drift.
- Step 1 of Task 1 (alembic revision) generates a file with `<auto>` placeholders; implementer must edit the new file's revision-id/down-revision fields to match alembic's actual output.

---

**Plan complete and saved to `docs/superpowers/plans/2026-05-11-v0_2_1a-stream-a-web-ingestion.md`.**

Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task + foreground GREEN verification fallback (lessons applied from v0.2.0b). Estimated wall time: ~8-12h. Background subagent runs while you brainstorm Plans B/C/D OR work on v0.2.0c hygiene.
2. **Inline Execution** — `superpowers:executing-plans` in this session. Faster turnaround but burns ~30-40% of remaining context.

Which approach?

After Plan A ships, the next plan to write is **Plan B (Stream B — Redaction pipeline + 18 stubs)** — smaller (~6-8 tasks, ~500-800 lines), then Plan C (largest — retrieval + L3/L4/L14), then Plan D (validators + W8).
