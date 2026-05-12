# v0.2.1a Stream C — Retrieval Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the retrieval engine — hybrid BM25 (Postgres `ts_rank_cd`) + pgvector ANN with Reciprocal Rank Fusion — plus the `embedding-service`, the `EmbedClient`, and the two L3/L4 MCP tools (`list_rls_precedents`, `get_policy_snippets`) that consume retrieval. Output is the surface that lets a requester ask "what RLS precedents apply to this matter?" and "what policy snippets bound this lint suggestion?" against the corpus Plan A scraped and Plan B onboarded.

**Architecture:** Library-in-each-tool (per ADR-006). `mcp_tools/_lib/corpus/` is the shared retrieval library — `retriever.py` (HybridRetriever class), `embed_client.py` (HTTP wrapper to embedding-service), `types.py` (Hit model). Two MCP tools import the library and add their tool-specific filtering + ROI emit. Embedding-service is a new top-level service (port 30201) that owns the breaker around Ollama `bcc-ap-infer01:11434` — centralizes breaker state so multiple tool processes share one Ollama-circuit. RRF k=60 per Cormack 2009.

**Tech Stack:** Python 3.12, `mcp` framework (existing — `apps.gateway.tools.build_tool_app`), `httpx` for embed HTTP calls, `pgvector` Postgres extension + `pgvector-python` (for adapter), `asyncpg` against the existing pool, pytest with `pytest-postgresql` fixtures for retrieval-correctness assertions, FastAPI for the embedding-service `/health` + `/embed` endpoints.

**Branch:** continues on `feat/v0.2.0a-backend` to match Plans A and B. If branch hygiene gets noisy after A+B land, rebase Plan C onto `feat/v0.2.1a-stream-c` cut from Plan B HEAD — operator choice at execute time.

**Reference docs:**
- Spec: `docs/superpowers/specs/2026-05-11-v0_2_1a-design.md` §3.3 (schema), §6 (Stream C), §9 (W8 unit roster), §10 (testing strategy), §13 (NFRs)
- ADRs (in spec §11): 001 hybrid retrieval, 002 versioned snapshots, 005 mxbai-embed-large, 006 library-in-each-tool
- W3 (RRF correctness test), E1 (emit compliance for L3/L4), E2 (embedding-breaker fallback)
- Plan A: `docs/superpowers/plans/2026-05-11-v0_2_1a-stream-a-web-ingestion.md` — defines `corpus_chunks` schema (Task 1) + `CorpusChunk` Pydantic model (Task 2). Plan C depends on both.
- Plan B: `docs/superpowers/plans/2026-05-11-v0_2_1a-stream-b-redaction.md` — populates `corpus_chunks` rows with `source_type='internal_opinion'`. Plan C consumes them.
- Runbook: `docs/runbooks/2026-05-09-rls-apex-v0_2_0b-runbook.md` — operational state

**Baseline assumed when Plan C executes:** Plans A and B have merged. Concretely:
- `corpus_chunks` table exists with `embedding` column as `ARRAY(Float)` placeholder + GIN full-text index (Plan A Task 1)
- `CorpusChunk` Pydantic model in `apps/gateway/db/models.py` (Plan A Task 2)
- `scraper-service` is producing rows (Plan A end-to-end)
- 18 stub opinions are landed with `source_type='internal_opinion'` (Plan B Task 3 + 7)
- `redaction_audit` table exists (Plan B Task 1)
- Backend pytest baseline: ~119 tests (64 v0.2.0b + ~25 Plan A + ~30 Plan B)

**Plan C target after completion:** ~149 backend pytest (119 baseline + ~30 new). One new `embedding-service` systemd unit (port 30201) + two new MCP tool units (`list_rls_precedents` port 30103, `get_policy_snippets` port 30104) running. `corpus_chunks.embedding` is `vector(1024)`; HNSW index built. L3/L4 are reachable via gateway `/api/intake` and `/api/lint/policy` (gateway endpoint for L14 backing is Plan D scope; Plan C ships L4 as a callable MCP tool only).

**Out of scope** (lives in Plan D or v0.2.1b):
- L1 `check_code_enforcement_litigation` rule engine (Plan D)
- L2 `check_urgency_rules` + `calendar.check_working_days` (Plan D)
- L14 frontend chip (`apps/web/static/core/automation/auto-correct.js` policy-lint-llm rule) + gateway `POST /api/lint/policy` endpoint (Plan D — depends on L4 from this plan)
- W8 `/api/health/aggregated` gateway endpoint (Plan D)
- Retrieval eval harness with 50 hand-labeled query/relevance pairs (v0.2.1b)
- Procedure-snippets corpus from a verified Procedure 26-104.001 source (Stream B governance; v0.2.1a ships with `procedure_corpus_pending: true` until Legal confirms)

---

## File Structure

| Path | Action | Responsibility |
|---|---|---|
| `alembic/versions/<auto>_v021a_corpus_embedding_hnsw.py` | Create | Migration: convert `corpus_chunks.embedding` from `ARRAY(Float)` to `vector(1024)`; add HNSW cosine index |
| `mcp_tools/_lib/corpus/__init__.py` | Create | Library package init — re-exports `HybridRetriever`, `EmbedClient`, `Hit` |
| `mcp_tools/_lib/corpus/types.py` | Create | `Hit` Pydantic model — id, source_id, source_type, citation, body, score, metadata |
| `mcp_tools/_lib/corpus/embed_client.py` | Create | `EmbedClient` — async httpx call to embedding-service `/embed`; raises on breaker-open so caller can fall back |
| `mcp_tools/_lib/corpus/retriever.py` | Create | `HybridRetriever` class — BM25 (`ts_rank_cd`) + pgvector ANN + RRF merge (k=60) + point-in-time filter |
| `services/embedding/__init__.py` | Create | Service package init |
| `services/embedding/service.py` | Create | FastAPI app on port 30201 — POST `/embed` + GET `/health`; owns the Ollama breaker |
| `services/embedding/breaker.py` | Create | Thin wrapper around `apps.gateway.circuit.CircuitBreaker` with single-probe enforcement (per `manatee-civic-ai` pattern) |
| `services/embedding/config.py` | Create | OLLAMA_URL, model name (`mxbai-embed-large`), KEEP_ALIVE, timeouts, breaker thresholds |
| `services/embedding/requirements.txt` | Create | Pinned: `fastapi`, `uvicorn`, `httpx`, `pydantic` |
| `services/embedding/systemd/embedding.service` | Create | systemd unit — `embedding-service` on port 30201, `KEEP_ALIVE=24h` env (Ollama config; see ADR-005) |
| `mcp_tools/list_rls_precedents/__init__.py` | Create | MCP tool package init |
| `mcp_tools/list_rls_precedents/server.py` | Create | L3 — `list_rls_precedents` MCP tool, port 30103. Uses HybridRetriever + matter_type metadata filter + ROI `rag_hit` emit |
| `mcp_tools/list_rls_precedents/requirements.txt` | Create | Tool deps inheriting `mcp_tools/_lib/corpus` |
| `mcp_tools/list_rls_precedents/systemd/list_rls_precedents.service` | Create | systemd unit, port 30103 |
| `mcp_tools/get_policy_snippets/__init__.py` | Create | MCP tool package init |
| `mcp_tools/get_policy_snippets/server.py` | Create | L4 — `get_policy_snippets` MCP tool, port 30104. Policy/procedure source-type filter + `procedure_corpus_pending` flag in response |
| `mcp_tools/get_policy_snippets/requirements.txt` | Create | Tool deps inheriting `mcp_tools/_lib/corpus` |
| `mcp_tools/get_policy_snippets/systemd/get_policy_snippets.service` | Create | systemd unit, port 30104 |
| `tests/mcp_tools/_lib/corpus/__init__.py` | Create | Test package init |
| `tests/mcp_tools/_lib/corpus/test_types.py` | Create | `Hit` model validation — required fields, score bounds, metadata JSON round-trip |
| `tests/mcp_tools/_lib/corpus/test_embed_client.py` | Create | EmbedClient HTTP shape; raises `EmbeddingUnavailable` on 503 (breaker-open) |
| `tests/mcp_tools/_lib/corpus/test_retriever.py` | Create | W3 — RRF correctness; BM25 ordering; ANN ordering; point-in-time filter (W3 acceptance) |
| `tests/services/embedding/__init__.py` | Create | Test package init |
| `tests/services/embedding/test_service.py` | Create | `/embed` round-trip against mocked Ollama; `/health` reflects breaker state |
| `tests/services/embedding/test_breaker.py` | Create | Breaker opens after 3 failures; single-probe half-open; recovers on success |
| `tests/mcp_tools/list_rls_precedents/__init__.py` | Create | Test package init |
| `tests/mcp_tools/list_rls_precedents/test_server.py` | Create | L3 returns hits filtered by matter_type + source_filter; emits `rag_hit` with hit_count in extra |
| `tests/mcp_tools/list_rls_precedents/test_emit_compliance.py` | Create | E1 — parametrized event-shape contract test (extends existing pattern from v0.2.0a) |
| `tests/mcp_tools/get_policy_snippets/__init__.py` | Create | Test package init |
| `tests/mcp_tools/get_policy_snippets/test_server.py` | Create | L4 returns snippets; `procedure_corpus_pending=true` when no `source_type='procedure'` hits |
| `tests/mcp_tools/get_policy_snippets/test_emit_compliance.py` | Create | E1 — parametrized event-shape contract test |
| `tests/integration/test_embedding_breaker_fallback.py` | Create | E2 — Embedding service down → retrieval falls back to BM25-only with warning surfaced via Hit metadata |
| `tests/integration/test_retrieval_smoke.py` | Create | Full path: POST `/api/intake` → MCP tool dispatch to L3 → assert hits + ROI emit visible |
| `tests/fixtures/corpus_seed.py` | Create | pytest fixture inserting ~30 deterministic chunks across all 5 `source_type` values for retrieval tests |
| `apps/gateway/sidecar/manatee_ai_roi.schema.json` | Modify | Add the `rag_hit` event-kind path/example if not already present (verify, no-op if already there) |

---

## Task 1: Alembic migration — `embedding` → `vector(1024)` + HNSW index

**Files:**
- Create: `alembic/versions/<auto>_v021a_corpus_embedding_hnsw.py`

**Preconditions verified before starting:**
- `pgvector` extension is installed in the Postgres instance (`SELECT * FROM pg_extension WHERE extname = 'vector';` returns a row). Plan A Task 1 ran `CREATE EXTENSION IF NOT EXISTS vector;` idempotently — but on a fresh DB the operator must have installed the `pgvector` Homebrew formula (`brew install pgvector`) before Plan A migrated. This task assumes that's done; if not, alembic upgrade fails with `extension "vector" is not available` and the operator installs pgvector then re-runs.

- [ ] **Step 1: Generate the migration**

```bash
cd /Users/ejarbe/Projects/rls-apex-v1
.venv/bin/alembic revision -m "v021a corpus_chunks embedding vector(1024) + HNSW"
```

This creates `alembic/versions/<hash>_v021a_corpus_chunks_embedding_vector_1024_hnsw.py` with empty `upgrade`/`downgrade` bodies.

- [ ] **Step 2: Write the migration**

Replace the generated body with:

```python
"""v021a corpus_chunks embedding vector(1024) + HNSW

Revision ID: <auto-generated>
Revises: <Plan A corpus_chunks migration revision — check alembic history>
Create Date: 2026-05-11

Converts corpus_chunks.embedding from ARRAY(Float) placeholder (Plan A) to
pgvector vector(1024) and adds the HNSW cosine index.

Per spec §6 + ADR-001 + ADR-005:
- mxbai-embed-large produces 1024-dim vectors
- HNSW with vector_cosine_ops for semantic ANN

Note: if the column already contains placeholder array rows from Plan A
backfill, the USING expression casts them. If no rows exist yet (expected
for the v0.2.1a fresh-DB path), the cast is a no-op.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "<auto>"
down_revision = "<Plan A v021a corpus_chunks migration revision>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. pgvector extension must exist (Plan A migration already runs this idempotently)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 2. Convert the embedding column type
    # Use ALTER COLUMN ... TYPE with USING clause. If the column is currently
    # ARRAY(Float) and contains rows, this casts each array to a vector.
    # On a clean DB (no rows) the USING clause is a no-op.
    op.execute(
        "ALTER TABLE corpus_chunks "
        "ALTER COLUMN embedding TYPE vector(1024) "
        "USING embedding::vector(1024);"
    )

    # 3. HNSW cosine index for semantic ANN (per ADR-001)
    # m=16, ef_construction=64 are pgvector defaults sufficient for ≤5k chunks (NFR §13).
    op.execute(
        "CREATE INDEX idx_corpus_chunks_hnsw ON corpus_chunks "
        "USING hnsw (embedding vector_cosine_ops);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_corpus_chunks_hnsw;")
    # Revert embedding to ARRAY(Float) so Plan A's downgrade path stays clean
    op.execute(
        "ALTER TABLE corpus_chunks "
        "ALTER COLUMN embedding TYPE float8[] "
        "USING embedding::float8[];"
    )
```

- [ ] **Step 3: Run the migration**

```bash
.venv/bin/alembic upgrade head
```

Expected output: `Running upgrade <prior> -> <new>, v021a corpus_chunks embedding vector(1024) + HNSW`.

If you see `ERROR: extension "vector" is not available`, install pgvector via Homebrew (`brew install pgvector`) and restart Postgres before re-running.

- [ ] **Step 4: Verify the column type + index**

```bash
.venv/bin/python -c "
import asyncio, asyncpg, os
async def main():
    c = await asyncpg.connect(os.environ['DATABASE_URL'])
    col = await c.fetchrow('''
        SELECT data_type, udt_name
        FROM information_schema.columns
        WHERE table_name = 'corpus_chunks' AND column_name = 'embedding'
    ''')
    print('embedding udt_name:', col['udt_name'])
    idx = await c.fetchrow(\"\"\"SELECT indexdef FROM pg_indexes WHERE indexname = 'idx_corpus_chunks_hnsw'\"\"\")
    print('hnsw index def:', idx['indexdef'] if idx else 'MISSING')
    await c.close()
asyncio.run(main())
"
```

Expected:
- `embedding udt_name: vector`
- `hnsw index def: CREATE INDEX idx_corpus_chunks_hnsw ON public.corpus_chunks USING hnsw (embedding vector_cosine_ops)`

- [ ] **Step 5: Run full backend suite**

```bash
.venv/bin/python -m pytest -q
```

Expected: baseline-after-A-and-B count passes (~119). No regressions.

- [ ] **Step 6: Commit**

```bash
git add alembic/versions/*_v021a_corpus_chunks_embedding_vector_1024_hnsw.py
git commit -m "$(cat <<'EOF'
feat(db): migrate corpus_chunks.embedding to vector(1024) + HNSW index

Per Stream C plan Task 1. Plan A's placeholder ARRAY(Float) embedding
column is converted to pgvector vector(1024), and the HNSW cosine index
is built (per spec ADR-001 hybrid retrieval, ADR-005 mxbai-embed-large
dim). HNSW defaults (m=16, ef_construction=64) are sufficient for the
≤5k chunk corpus targeted in NFR §13.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: `Hit` Pydantic model + library package init

**Files:**
- Create: `mcp_tools/_lib/corpus/__init__.py`
- Create: `mcp_tools/_lib/corpus/types.py`
- Create: `tests/mcp_tools/_lib/corpus/__init__.py`
- Create: `tests/mcp_tools/_lib/corpus/test_types.py`

- [ ] **Step 1: Write the failing test**

`tests/mcp_tools/_lib/corpus/test_types.py`:

```python
"""Hit model unit tests."""
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from mcp_tools._lib.corpus.types import Hit


def test_hit_minimal_required_fields():
    h = Hit(
        id=42,
        source_id="municode.ldc.6.4",
        source_type="ldc",
        citation="Manatee County LDC §6.4(a)(2) (2024)",
        body="No structure shall be erected without...",
        score=0.87,
    )
    assert h.id == 42
    assert h.source_type == "ldc"
    assert h.score == pytest.approx(0.87)
    # metadata defaults to empty dict
    assert h.metadata == {}


def test_hit_full_metadata_roundtrip():
    meta = {"matter_type": "permit_or_zoning", "retrieved_at": "2026-05-11T10:00:00Z"}
    h = Hit(
        id=1,
        source_id="internal_opinion.stub.1",
        source_type="internal_opinion",
        citation="Internal Opinion 2026-001",
        body="...",
        score=0.5,
        section_path="opinion / recommendation",
        metadata=meta,
        valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        valid_to=None,
    )
    dumped = h.model_dump()
    rebuilt = Hit(**dumped)
    assert rebuilt.metadata == meta
    assert rebuilt.section_path == "opinion / recommendation"


def test_hit_rejects_score_out_of_range_lower():
    with pytest.raises(ValidationError):
        Hit(
            id=1, source_id="x", source_type="ldc", citation="x", body="x",
            score=-0.1,
        )


def test_hit_rejects_score_out_of_range_upper():
    with pytest.raises(ValidationError):
        Hit(
            id=1, source_id="x", source_type="ldc", citation="x", body="x",
            score=1.5,
        )


def test_hit_rejects_unknown_source_type():
    with pytest.raises(ValidationError):
        Hit(
            id=1, source_id="x", source_type="bogus_source", citation="x", body="x",
            score=0.5,
        )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/python -m pytest tests/mcp_tools/_lib/corpus/test_types.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'mcp_tools._lib.corpus.types'`.

- [ ] **Step 3: Create the package init files**

`mcp_tools/_lib/corpus/__init__.py`:

```python
"""Shared retrieval library — imported by list_rls_precedents and get_policy_snippets."""
from mcp_tools._lib.corpus.types import Hit, SourceType

__all__ = ["Hit", "SourceType"]
```

`tests/mcp_tools/_lib/corpus/__init__.py`: empty.

- [ ] **Step 4: Write the Hit model**

`mcp_tools/_lib/corpus/types.py`:

```python
"""Pydantic types for retrieval. Hit is the unit of retrieval output."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SourceType = Literal[
    "ldc",
    "ordinance",
    "fl_ag_opinion",
    "internal_opinion",
    "procedure",
    "calendar",
]


class Hit(BaseModel):
    """One retrieval hit. Score is normalized to [0, 1] post-RRF."""

    model_config = ConfigDict(extra="forbid")

    id: int
    source_id: str
    source_type: SourceType
    citation: str
    body: str
    score: float = Field(ge=0.0, le=1.0)
    section_path: str | None = None
    metadata: dict = Field(default_factory=dict)
    valid_from: datetime | None = None
    valid_to: datetime | None = None
```

- [ ] **Step 5: Run test to verify it passes**

```bash
.venv/bin/python -m pytest tests/mcp_tools/_lib/corpus/test_types.py -v
```

Expected: 5 passed.

- [ ] **Step 6: Run full backend suite**

```bash
.venv/bin/python -m pytest -q
```

Expected: baseline + 5 = 124 passed.

- [ ] **Step 7: Commit**

```bash
git add mcp_tools/_lib/corpus/__init__.py mcp_tools/_lib/corpus/types.py \
        tests/mcp_tools/_lib/corpus/__init__.py tests/mcp_tools/_lib/corpus/test_types.py
git commit -m "$(cat <<'EOF'
feat(corpus): Hit pydantic model + library package scaffolding

Hit is the unit of retrieval output — id, source_id, source_type
(Literal of 6 corpus source-types), citation, body, score [0,1], and
optional section_path / metadata / valid_from / valid_to. The shared
mcp_tools._lib.corpus package will hold the HybridRetriever and
EmbedClient (next tasks).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `embedding-service` — FastAPI app + Ollama breaker

**Files:**
- Create: `services/embedding/__init__.py`
- Create: `services/embedding/config.py`
- Create: `services/embedding/breaker.py`
- Create: `services/embedding/service.py`
- Create: `services/embedding/requirements.txt`
- Create: `tests/services/embedding/__init__.py`
- Create: `tests/services/embedding/test_service.py`
- Create: `tests/services/embedding/test_breaker.py`

The embedding-service is a thin wrapper around Ollama at `bcc-ap-infer01:11434`. The breaker lives here (not in EmbedClient) so multiple tool processes share one circuit state — when Ollama hangs, all retrievers see the open breaker simultaneously.

- [ ] **Step 1: Write failing breaker tests first**

`tests/services/embedding/test_breaker.py`:

```python
"""Embedding-service breaker tests. Mirrors the manatee-civic-ai breaker pattern."""
import asyncio

import pytest

from services.embedding.breaker import EmbeddingBreaker


@pytest.mark.asyncio
async def test_breaker_starts_closed():
    b = EmbeddingBreaker(failure_threshold=3, open_for_seconds=30)
    assert b.state == "closed"


@pytest.mark.asyncio
async def test_breaker_opens_after_threshold_failures():
    b = EmbeddingBreaker(failure_threshold=3, open_for_seconds=30)
    for _ in range(3):
        b.record_failure()
    assert b.state == "open"


@pytest.mark.asyncio
async def test_breaker_blocks_calls_when_open():
    b = EmbeddingBreaker(failure_threshold=1, open_for_seconds=30)
    b.record_failure()
    assert b.state == "open"
    with pytest.raises(RuntimeError, match="breaker is open"):
        b.guard()


@pytest.mark.asyncio
async def test_breaker_single_probe_half_open():
    """After open_for_seconds elapses, exactly ONE probe is allowed."""
    b = EmbeddingBreaker(failure_threshold=1, open_for_seconds=0)
    b.record_failure()
    assert b.state == "open"
    # First guard() after expiry transitions to half_open
    await asyncio.sleep(0.01)
    b.guard()  # OK — half-open probe allowed
    assert b.state == "half_open"
    # Second guard() while still half-open MUST block
    with pytest.raises(RuntimeError, match="probe in flight"):
        b.guard()


@pytest.mark.asyncio
async def test_breaker_recovers_on_probe_success():
    b = EmbeddingBreaker(failure_threshold=1, open_for_seconds=0)
    b.record_failure()
    await asyncio.sleep(0.01)
    b.guard()  # half-open
    b.record_success()
    assert b.state == "closed"


@pytest.mark.asyncio
async def test_breaker_reopens_on_probe_failure():
    b = EmbeddingBreaker(failure_threshold=1, open_for_seconds=0)
    b.record_failure()
    await asyncio.sleep(0.01)
    b.guard()  # half-open
    b.record_failure()
    assert b.state == "open"
```

- [ ] **Step 2: Run breaker tests — verify failure**

```bash
.venv/bin/python -m pytest tests/services/embedding/test_breaker.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement the breaker**

`services/embedding/breaker.py`:

```python
"""Single-probe circuit breaker for Ollama embed calls.

Mirrors the manatee-civic-ai breaker semantics:
- closed → open after `failure_threshold` consecutive failures
- open → half_open after `open_for_seconds`, allowing ONE probe
- half_open → closed on probe success, → open on probe failure
- only one probe allowed in half_open (single-probe enforcement)
"""
from __future__ import annotations

import time
from typing import Literal

State = Literal["closed", "open", "half_open"]


class EmbeddingBreaker:
    def __init__(self, failure_threshold: int = 3, open_for_seconds: int = 30):
        self._threshold = failure_threshold
        self._open_for = open_for_seconds
        self._state: State = "closed"
        self._consecutive_failures = 0
        self._opened_at: float = 0.0
        self._probe_in_flight = False

    @property
    def state(self) -> State:
        # Lazy transition: open → half_open after the timer expires.
        if self._state == "open" and (time.monotonic() - self._opened_at) >= self._open_for:
            return "half_open"
        return self._state

    def guard(self) -> None:
        """Raise if the breaker won't allow a call. Transitions open → half_open if expired."""
        if self._state == "open":
            if (time.monotonic() - self._opened_at) >= self._open_for:
                self._state = "half_open"
                self._probe_in_flight = True
                return
            raise RuntimeError("Embedding breaker is open — refusing call")
        if self._state == "half_open":
            if self._probe_in_flight:
                raise RuntimeError("Embedding breaker probe in flight — refusing call")
            self._probe_in_flight = True
            return
        # closed — allowed
        return

    def record_success(self) -> None:
        self._consecutive_failures = 0
        self._state = "closed"
        self._probe_in_flight = False

    def record_failure(self) -> None:
        self._consecutive_failures += 1
        self._probe_in_flight = False
        if self._consecutive_failures >= self._threshold:
            self._state = "open"
            self._opened_at = time.monotonic()
```

- [ ] **Step 4: Run breaker tests — verify pass**

```bash
.venv/bin/python -m pytest tests/services/embedding/test_breaker.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Write failing service tests**

`tests/services/embedding/test_service.py`:

```python
"""FastAPI service tests — POST /embed + GET /health."""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from services.embedding.service import app


@pytest.fixture()
def client():
    return TestClient(app)


def test_health_when_breaker_closed_and_ollama_reachable(client):
    with patch("services.embedding.service._probe_ollama", AsyncMock(return_value=True)):
        r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy"
    assert body["ollama_reachable"] is True
    assert body["breaker_state"] == "closed"


def test_health_returns_503_when_breaker_open(client):
    from services.embedding.service import _breaker
    _breaker.record_failure(); _breaker.record_failure(); _breaker.record_failure()
    try:
        r = client.get("/health")
        assert r.status_code == 503
        assert r.json()["breaker_state"] == "open"
    finally:
        _breaker.record_success()  # reset for next test


def test_embed_returns_vector_when_ollama_succeeds(client):
    fake_vec = [0.1] * 1024
    fake_resp = {"embedding": fake_vec}
    async_fake = AsyncMock(return_value=fake_resp)
    with patch("services.embedding.service._ollama_embed_call", async_fake):
        r = client.post("/embed", json={"text": "RLS form requirements"})
    assert r.status_code == 200
    body = r.json()
    assert body["embedding"] == fake_vec
    assert len(body["embedding"]) == 1024


def test_embed_returns_503_when_breaker_open(client):
    from services.embedding.service import _breaker
    _breaker.record_failure(); _breaker.record_failure(); _breaker.record_failure()
    try:
        r = client.post("/embed", json={"text": "x"})
        assert r.status_code == 503
    finally:
        _breaker.record_success()


def test_embed_increments_failure_on_ollama_error(client):
    from services.embedding.service import _breaker
    _breaker.record_success()  # reset
    async_fail = AsyncMock(side_effect=RuntimeError("ollama down"))
    with patch("services.embedding.service._ollama_embed_call", async_fail):
        r = client.post("/embed", json={"text": "x"})
    assert r.status_code == 502
    assert _breaker._consecutive_failures == 1
```

- [ ] **Step 6: Implement the service**

`services/embedding/config.py`:

```python
"""embedding-service configuration."""
import os

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://bcc-ap-infer01:11434")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "mxbai-embed-large")
EMBED_DIM = 1024
HTTP_TIMEOUT_SECONDS = 10
BREAKER_FAILURE_THRESHOLD = 3
BREAKER_OPEN_SECONDS = 30
KEEP_ALIVE = os.environ.get("OLLAMA_KEEP_ALIVE", "24h")  # passed to Ollama per ADR-005
```

`services/embedding/service.py`:

```python
"""embedding-service — port 30201.

Wraps Ollama mxbai-embed-large with a single-probe circuit breaker. Multiple
MCP tool processes share this service so the breaker state is centralized.

Endpoints:
- POST /embed {text: str} → {embedding: list[float]}
- GET  /health           → {status, ollama_reachable, breaker_state, last_inference_ms}
"""
from __future__ import annotations

import time
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from services.embedding.breaker import EmbeddingBreaker
from services.embedding.config import (
    BREAKER_FAILURE_THRESHOLD,
    BREAKER_OPEN_SECONDS,
    EMBED_DIM,
    EMBED_MODEL,
    HTTP_TIMEOUT_SECONDS,
    KEEP_ALIVE,
    OLLAMA_URL,
)

app = FastAPI(title="embedding-service")

_breaker = EmbeddingBreaker(
    failure_threshold=BREAKER_FAILURE_THRESHOLD,
    open_for_seconds=BREAKER_OPEN_SECONDS,
)

_last_inference_ms: Optional[float] = None


class EmbedRequest(BaseModel):
    text: str = Field(min_length=1, max_length=8000)


class EmbedResponse(BaseModel):
    embedding: list[float]


async def _ollama_embed_call(text: str) -> dict:
    """Real Ollama call — split out for monkey-patching in tests."""
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as c:
        r = await c.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": text, "keep_alive": KEEP_ALIVE},
        )
        r.raise_for_status()
        return r.json()


async def _probe_ollama() -> bool:
    """Lightweight probe used by /health. Times out fast."""
    try:
        async with httpx.AsyncClient(timeout=2.0) as c:
            r = await c.get(f"{OLLAMA_URL}/api/tags")
            return r.status_code == 200
    except Exception:
        return False


@app.post("/embed", response_model=EmbedResponse)
async def embed(req: EmbedRequest) -> EmbedResponse:
    try:
        _breaker.guard()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    started = time.monotonic()
    try:
        resp = await _ollama_embed_call(req.text)
    except Exception as e:
        _breaker.record_failure()
        raise HTTPException(status_code=502, detail=f"ollama error: {e}")

    vec = resp.get("embedding")
    if not isinstance(vec, list) or len(vec) != EMBED_DIM:
        _breaker.record_failure()
        raise HTTPException(
            status_code=502, detail=f"unexpected embedding shape: len={len(vec) if isinstance(vec, list) else 'NA'}"
        )

    _breaker.record_success()
    global _last_inference_ms
    _last_inference_ms = (time.monotonic() - started) * 1000.0
    return EmbedResponse(embedding=vec)


@app.get("/health")
async def health():
    reachable = await _probe_ollama()
    state = _breaker.state
    ok = state == "closed" and reachable
    body = {
        "status": "healthy" if ok else "degraded",
        "ollama_reachable": reachable,
        "breaker_state": state,
        "last_inference_ms": _last_inference_ms,
    }
    if not ok:
        return JSONResponse(status_code=503, content=body)
    return body
```

`services/embedding/__init__.py`: empty.

`services/embedding/requirements.txt`:

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
httpx==0.27.2
pydantic==2.9.2
```

- [ ] **Step 7: Run service tests — verify pass**

```bash
.venv/bin/python -m pytest tests/services/embedding/ -v
```

Expected: 6 (breaker) + 5 (service) = 11 passed.

- [ ] **Step 8: Run full backend suite**

```bash
.venv/bin/python -m pytest -q
```

Expected: 124 + 11 = 135 passed.

- [ ] **Step 9: Commit**

```bash
git add services/embedding/ tests/services/embedding/
git commit -m "$(cat <<'EOF'
feat(embedding-service): port 30201 — Ollama wrapper + single-probe breaker

POST /embed (mxbai-embed-large via Ollama at bcc-ap-infer01:11434) and
GET /health (returns ollama_reachable + breaker_state). Breaker uses
manatee-civic-ai single-probe semantics: opens after 3 consecutive
failures, half-open allows exactly one probe per cycle.

Per spec ADR-005 (embedding model) and §9.1 (W8 unit roster). Breaker
state surface gives Plan D's W8 aggregator a single source of truth for
embedding-circuit health.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: `EmbedClient` — HTTP wrapper for retrieval tools

**Files:**
- Create: `mcp_tools/_lib/corpus/embed_client.py`
- Create: `tests/mcp_tools/_lib/corpus/test_embed_client.py`
- Modify: `mcp_tools/_lib/corpus/__init__.py` (add `EmbedClient` to `__all__`)

`EmbedClient` is the retrieval-side wrapper. It calls embedding-service's `/embed`. On 503 (breaker open) or 502 (Ollama error), it raises `EmbeddingUnavailable` — the HybridRetriever catches this and falls back to BM25-only.

- [ ] **Step 1: Write the failing test**

`tests/mcp_tools/_lib/corpus/test_embed_client.py`:

```python
"""EmbedClient tests."""
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from mcp_tools._lib.corpus.embed_client import EmbedClient, EmbeddingUnavailable


@pytest.mark.asyncio
async def test_embed_returns_vector_on_200():
    fake_vec = [0.1] * 1024
    mock_resp = httpx.Response(200, json={"embedding": fake_vec})
    async with httpx.AsyncClient() as _client_unused:
        pass
    with patch.object(httpx.AsyncClient, "post", AsyncMock(return_value=mock_resp)):
        c = EmbedClient(base_url="http://localhost:30201")
        vec = await c.embed("RLS form requirements")
    assert len(vec) == 1024


@pytest.mark.asyncio
async def test_embed_raises_unavailable_on_503():
    mock_resp = httpx.Response(503, json={"detail": "breaker open"})
    with patch.object(httpx.AsyncClient, "post", AsyncMock(return_value=mock_resp)):
        c = EmbedClient(base_url="http://localhost:30201")
        with pytest.raises(EmbeddingUnavailable, match="breaker"):
            await c.embed("x")


@pytest.mark.asyncio
async def test_embed_raises_unavailable_on_connect_error():
    with patch.object(
        httpx.AsyncClient,
        "post",
        AsyncMock(side_effect=httpx.ConnectError("connection refused")),
    ):
        c = EmbedClient(base_url="http://localhost:30201")
        with pytest.raises(EmbeddingUnavailable, match="connect"):
            await c.embed("x")


@pytest.mark.asyncio
async def test_embed_raises_unavailable_on_timeout():
    with patch.object(
        httpx.AsyncClient,
        "post",
        AsyncMock(side_effect=httpx.TimeoutException("timed out")),
    ):
        c = EmbedClient(base_url="http://localhost:30201")
        with pytest.raises(EmbeddingUnavailable, match="timeout"):
            await c.embed("x")
```

- [ ] **Step 2: Run — expect fail**

```bash
.venv/bin/python -m pytest tests/mcp_tools/_lib/corpus/test_embed_client.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement EmbedClient**

`mcp_tools/_lib/corpus/embed_client.py`:

```python
"""EmbedClient — HTTP wrapper to embedding-service for the retrieval library.

Distinct exception type EmbeddingUnavailable lets HybridRetriever drop to
BM25-only without conflating with other retrieval errors.
"""
from __future__ import annotations

import httpx


class EmbeddingUnavailable(RuntimeError):
    """Raised when embedding-service refuses (breaker open) or is unreachable."""


class EmbedClient:
    def __init__(self, base_url: str, timeout_seconds: float = 5.0):
        self._base = base_url.rstrip("/")
        self._timeout = timeout_seconds

    async def embed(self, text: str) -> list[float]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as c:
                r = await c.post(f"{self._base}/embed", json={"text": text})
        except httpx.TimeoutException as e:
            raise EmbeddingUnavailable(f"embedding-service timeout: {e}") from e
        except httpx.ConnectError as e:
            raise EmbeddingUnavailable(f"embedding-service connect error: {e}") from e
        except httpx.HTTPError as e:
            raise EmbeddingUnavailable(f"embedding-service http error: {e}") from e

        if r.status_code == 503:
            raise EmbeddingUnavailable(f"embedding-service breaker open: {r.text}")
        if r.status_code != 200:
            raise EmbeddingUnavailable(f"embedding-service {r.status_code}: {r.text}")

        return r.json()["embedding"]
```

- [ ] **Step 4: Update package init**

`mcp_tools/_lib/corpus/__init__.py`:

```python
"""Shared retrieval library."""
from mcp_tools._lib.corpus.embed_client import EmbedClient, EmbeddingUnavailable
from mcp_tools._lib.corpus.types import Hit, SourceType

__all__ = ["Hit", "SourceType", "EmbedClient", "EmbeddingUnavailable"]
```

- [ ] **Step 5: Run — verify pass**

```bash
.venv/bin/python -m pytest tests/mcp_tools/_lib/corpus/test_embed_client.py -v
```

Expected: 4 passed.

- [ ] **Step 6: Run full backend suite**

```bash
.venv/bin/python -m pytest -q
```

Expected: 135 + 4 = 139 passed.

- [ ] **Step 7: Commit**

```bash
git add mcp_tools/_lib/corpus/embed_client.py mcp_tools/_lib/corpus/__init__.py \
        tests/mcp_tools/_lib/corpus/test_embed_client.py
git commit -m "$(cat <<'EOF'
feat(corpus): EmbedClient + EmbeddingUnavailable exception

Retrieval-side HTTP client to embedding-service. On 503 (breaker open),
502, timeout, or connect error, raises EmbeddingUnavailable so the
HybridRetriever can fall back to BM25-only retrieval (per spec R11
mitigation + E2 acceptance).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: `HybridRetriever` — BM25 + pgvector ANN + RRF merge + point-in-time

**Files:**
- Create: `mcp_tools/_lib/corpus/retriever.py`
- Create: `tests/fixtures/corpus_seed.py`
- Create: `tests/mcp_tools/_lib/corpus/test_retriever.py`
- Modify: `mcp_tools/_lib/corpus/__init__.py` (add `HybridRetriever`)

This is the W3 deliverable from spec §15. The retriever class accepts a `db_pool` + `EmbedClient`, runs both candidate searches in parallel, merges via Reciprocal Rank Fusion, and supports point-in-time filtering.

- [ ] **Step 1: Write the corpus seed fixture**

`tests/fixtures/corpus_seed.py`:

```python
"""pytest fixture that seeds corpus_chunks with deterministic test rows.

Used by retriever tests, MCP tool tests, and integration tests. Seeds 30
chunks across source_types (ldc, ordinance, fl_ag_opinion, internal_opinion,
procedure, calendar) so retrieval tests can assert filter behavior and
RRF ordering against known data.

Provides BOTH current-valid rows and a small set of historical rows with
valid_to set, so point-in-time queries can be asserted.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import asyncpg
import pytest_asyncio


# 30 rows: 6 source_types × 5 rows each. Bodies are short but distinctive
# enough that BM25 ranking is deterministic.
SEED_BODIES: list[tuple[str, str, str, str, str]] = [
    # (source_type, source_id, section_path, citation, body)
    ("ldc", "ldc.6.4.a.2", "Chapter 6 / §6.4 / (a)(2)",
     "Manatee County LDC §6.4(a)(2) (2024)",
     "No structure shall be erected without a permit issued under §6.4."),
    ("ldc", "ldc.6.5.a", "Chapter 6 / §6.5 / (a)",
     "Manatee County LDC §6.5(a) (2024)",
     "Variance applications must be filed at least thirty days before the hearing."),
    ("ldc", "ldc.6.6.b", "Chapter 6 / §6.6 / (b)",
     "Manatee County LDC §6.6(b) (2024)",
     "Setback requirements for residential zoning shall be twenty feet from street."),
    ("ldc", "ldc.7.1.a", "Chapter 7 / §7.1 / (a)",
     "Manatee County LDC §7.1(a) (2024)",
     "Conditional use permits require a public hearing before the planning commission."),
    ("ldc", "ldc.8.2.c", "Chapter 8 / §8.2 / (c)",
     "Manatee County LDC §8.2(c) (2024)",
     "Subdivision plats must include drainage easements and street alignments."),
    ("ordinance", "ord.2.4.a", "Chapter 2 / §2.4 / (a)",
     "Manatee County Code of Ordinances §2.4(a) (2024)",
     "Procurement of professional services follows the qualifications based selection process."),
    ("ordinance", "ord.5.1.b", "Chapter 5 / §5.1 / (b)",
     "Manatee County Code of Ordinances §5.1(b) (2024)",
     "Code enforcement liens attach to the property upon recording in the official records."),
    ("ordinance", "ord.10.3.a", "Chapter 10 / §10.3 / (a)",
     "Manatee County Code of Ordinances §10.3(a) (2024)",
     "Public records requests must be acknowledged within reasonable time per Chapter 119."),
    ("ordinance", "ord.15.2.a", "Chapter 15 / §15.2 / (a)",
     "Manatee County Code of Ordinances §15.2(a) (2024)",
     "Animal control violations are subject to administrative fines and confiscation."),
    ("ordinance", "ord.20.1.a", "Chapter 20 / §20.1 / (a)",
     "Manatee County Code of Ordinances §20.1(a) (2024)",
     "Noise ordinances prohibit construction work between 9 PM and 7 AM in residential zones."),
    ("fl_ag_opinion", "fl-ag.2023-08", "Opinion 2023-08",
     "Fla. AGO 2023-08 (2023)",
     "Florida Attorney General opinion on dual office holding for elected commissioners."),
    ("fl_ag_opinion", "fl-ag.2022-15", "Opinion 2022-15",
     "Fla. AGO 2022-15 (2022)",
     "Public records exemptions for active code enforcement investigations under Chapter 119."),
    ("fl_ag_opinion", "fl-ag.2021-04", "Opinion 2021-04",
     "Fla. AGO 2021-04 (2021)",
     "Application of the Sunshine Law to advisory boards lacking final decision-making authority."),
    ("fl_ag_opinion", "fl-ag.2020-11", "Opinion 2020-11",
     "Fla. AGO 2020-11 (2020)",
     "Florida Attorney General opinion on procurement bid protests and standing."),
    ("fl_ag_opinion", "fl-ag.2019-02", "Opinion 2019-02",
     "Fla. AGO 2019-02 (2019)",
     "Ethics commission jurisdiction over local government employees under §112.313."),
    ("internal_opinion", "internal_opinion.stub.1", "opinion / recommendation",
     "Internal Opinion 2026-001",
     "Vested rights claim under pre-amendment LDC §6.4 approval before 2024 amendments."),
    ("internal_opinion", "internal_opinion.stub.2", "opinion / recommendation",
     "Internal Opinion 2026-002",
     "Notice of violation NOV-2026-117 dated 2026-01-15 requires special magistrate hearing."),
    ("internal_opinion", "internal_opinion.stub.3", "opinion / recommendation",
     "Internal Opinion 2026-003",
     "RFP procurement protest under Ch. 2-26 procedures and qualifications based selection."),
    ("internal_opinion", "internal_opinion.stub.4", "opinion / recommendation",
     "Internal Opinion 2026-004",
     "Sunshine Law compliance for citizen advisory boards reviewing comprehensive plan amendments."),
    ("internal_opinion", "internal_opinion.stub.5", "opinion / recommendation",
     "Internal Opinion 2026-005",
     "Public records exemption claims for ongoing litigation under §119.071(1)(d)."),
    ("procedure", "procedure.26-104.001.1", "Procedure 26-104.001 / §1",
     "Manatee County Procedure 26-104.001 §1 (2024)",
     "RLS form submissions must include matter classification, factual background, and legal question."),
    ("procedure", "procedure.26-104.001.2", "Procedure 26-104.001 / §2",
     "Manatee County Procedure 26-104.001 §2 (2024)",
     "NOV references must include the NOV date and current administrative status."),
    ("procedure", "procedure.26-104.001.3", "Procedure 26-104.001 / §3",
     "Manatee County Procedure 26-104.001 §3 (2024)",
     "Critical urgency RLS requires deadline within 15 working days and adverse consequence statement."),
    ("procedure", "procedure.26-104.001.4", "Procedure 26-104.001 / §4",
     "Manatee County Procedure 26-104.001 §4 (2024)",
     "Procurement RLS must reference applicable Ch. 2-26 provisions and contract dispute history."),
    ("procedure", "procedure.26-104.001.5", "Procedure 26-104.001 / §5",
     "Manatee County Procedure 26-104.001 §5 (2024)",
     "Public records RLS must specify Chapter 119 exemption claims and redaction history."),
    ("calendar", "calendar.holidays.2026", "Holidays 2026",
     "Manatee County Working Days Calendar (2026)",
     "New Year's Day January 1, Memorial Day May 25, Independence Day July 4."),
    ("calendar", "calendar.holidays.2025", "Holidays 2025",
     "Manatee County Working Days Calendar (2025)",
     "New Year's Day January 1, Memorial Day May 26, Independence Day July 4."),
    ("calendar", "calendar.holidays.2024", "Holidays 2024",
     "Manatee County Working Days Calendar (2024)",
     "New Year's Day January 1, Memorial Day May 27, Independence Day July 4."),
    ("calendar", "calendar.holidays.2023", "Holidays 2023",
     "Manatee County Working Days Calendar (2023)",
     "New Year's Day January 2, Memorial Day May 29, Independence Day July 4."),
    ("calendar", "calendar.holidays.2022", "Holidays 2022",
     "Manatee County Working Days Calendar (2022)",
     "New Year's Day January 1, Memorial Day May 30, Independence Day July 4."),
]


# Deterministic non-zero embeddings: dim 1024, each row's vector is normalized hash-derived.
def _deterministic_embedding(seed: str) -> list[float]:
    """Generate a deterministic unit-norm 1024-dim vector from a seed string.

    Used for tests only. Real embeddings come from Ollama mxbai-embed-large.
    """
    h = hashlib.sha256(seed.encode()).digest()
    # Tile 32 bytes into 1024 floats. Map byte → [-1, 1].
    raw = list(h) * (1024 // 32 + 1)
    raw = raw[:1024]
    floats = [(b - 128) / 128.0 for b in raw]
    norm = sum(f * f for f in floats) ** 0.5
    return [f / norm for f in floats]


@pytest_asyncio.fixture()
async def seeded_corpus(db_pool):
    """Insert 30 deterministic rows + 1 historical row, yield pool, truncate after."""
    base_valid_from = datetime(2024, 1, 1, tzinfo=timezone.utc)
    async with db_pool.acquire() as conn:
        await conn.execute("TRUNCATE corpus_chunks RESTART IDENTITY CASCADE;")
        for source_type, sid, section, citation, body in SEED_BODIES:
            emb = _deterministic_embedding(sid)
            sha = hashlib.sha256(body.encode()).hexdigest()
            await conn.execute(
                """
                INSERT INTO corpus_chunks
                  (source_id, source_type, section_path, citation, body, sha256,
                   valid_from, valid_to, embedding, metadata)
                VALUES ($1, $2, $3, $4, $5, $6, $7, NULL, $8::vector, $9::jsonb)
                """,
                sid, source_type, section, citation, body, sha,
                base_valid_from, str(emb), "{}",
            )
        # Add one historical row: LDC §6.4(a)(2) old version, valid 2022-2024
        old_body = "No structure shall be erected without a permit issued under §6.4 (pre-2024 wording)."
        old_emb = _deterministic_embedding("ldc.6.4.a.2.historical")
        old_sha = hashlib.sha256(old_body.encode()).hexdigest()
        await conn.execute(
            """
            INSERT INTO corpus_chunks
              (source_id, source_type, section_path, citation, body, sha256,
               valid_from, valid_to, embedding, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::vector, $10::jsonb)
            """,
            "ldc.6.4.a.2", "ldc", "Chapter 6 / §6.4 / (a)(2)",
            "Manatee County LDC §6.4(a)(2) (2022)",
            old_body, old_sha,
            datetime(2022, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            str(old_emb), "{}",
        )
    yield db_pool
    async with db_pool.acquire() as conn:
        await conn.execute("TRUNCATE corpus_chunks RESTART IDENTITY CASCADE;")
```

- [ ] **Step 2: Write the failing retriever test**

`tests/mcp_tools/_lib/corpus/test_retriever.py`:

```python
"""HybridRetriever tests — RRF correctness, BM25 + ANN order, point-in-time.

W3 acceptance criterion from spec §15.
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from mcp_tools._lib.corpus.retriever import HybridRetriever
from mcp_tools._lib.corpus.types import Hit
from tests.fixtures.corpus_seed import _deterministic_embedding, seeded_corpus  # noqa: F401


@pytest.fixture()
def fake_embed_client():
    """Returns a deterministic vector that matches one seeded chunk."""
    c = AsyncMock()
    # Default: target the LDC §6.4 current row
    c.embed = AsyncMock(return_value=_deterministic_embedding("ldc.6.4.a.2"))
    return c


@pytest.mark.asyncio
async def test_bm25_search_returns_lexical_match_first(seeded_corpus, fake_embed_client):
    r = HybridRetriever(seeded_corpus, fake_embed_client)
    hits = await r._bm25_search("variance applications hearing", k=10)
    # Top hit should be LDC §6.5 ("Variance applications must be filed...")
    assert len(hits) >= 1
    assert hits[0].source_id == "ldc.6.5.a"


@pytest.mark.asyncio
async def test_ann_search_returns_semantic_match_first(seeded_corpus, fake_embed_client):
    r = HybridRetriever(seeded_corpus, fake_embed_client)
    # query_vec is the embedding for "ldc.6.4.a.2" seed — should rank that chunk first
    query_vec = _deterministic_embedding("ldc.6.4.a.2")
    hits = await r._ann_search(query_vec, k=10)
    assert hits[0].source_id == "ldc.6.4.a.2"


@pytest.mark.asyncio
async def test_rrf_merge_is_correct():
    """RRF: score(d) = Σ 1 / (k + rank_in_list_i(d))."""
    from mcp_tools._lib.corpus.retriever import HybridRetriever

    # Two ranked lists. Doc A is rank 1 in list1, rank 2 in list2.
    # Doc B is rank 2 in list1, rank 1 in list2. Doc C is rank 3 in list1 only.
    list1 = [
        Hit(id=1, source_id="A", source_type="ldc", citation="A", body="A", score=1.0),
        Hit(id=2, source_id="B", source_type="ldc", citation="B", body="B", score=0.8),
        Hit(id=3, source_id="C", source_type="ldc", citation="C", body="C", score=0.5),
    ]
    list2 = [
        Hit(id=2, source_id="B", source_type="ldc", citation="B", body="B", score=0.95),
        Hit(id=1, source_id="A", source_type="ldc", citation="A", body="A", score=0.85),
    ]
    # k=60 Cormack default. Expected RRF scores:
    # A: 1/(60+1) + 1/(60+2) = 0.01639... + 0.01613... = 0.03252...
    # B: 1/(60+2) + 1/(60+1) = same = 0.03252...
    # C: 1/(60+3) = 0.01587...
    # A and B tie; tiebreak is by id ASC (stable). C is last.
    merged = HybridRetriever._rrf_merge(list1, list2, k=3, rrf_k=60)
    ids = [h.source_id for h in merged]
    # Ties broken deterministically (by id ascending)
    assert ids[:2] == ["A", "B"]
    assert ids[2] == "C"
    # Scores should be normalized to [0, 1]
    assert all(0.0 <= h.score <= 1.0 for h in merged)


@pytest.mark.asyncio
async def test_hybrid_search_returns_top_k(seeded_corpus, fake_embed_client):
    r = HybridRetriever(seeded_corpus, fake_embed_client)
    hits = await r.search("permit setback", k=5)
    assert len(hits) <= 5
    # All hits must be Hit instances with normalized scores
    for h in hits:
        assert isinstance(h, Hit)
        assert 0.0 <= h.score <= 1.0


@pytest.mark.asyncio
async def test_source_filter_excludes_other_types(seeded_corpus, fake_embed_client):
    r = HybridRetriever(seeded_corpus, fake_embed_client)
    hits = await r.search("hearing", k=10, source_filter=["fl_ag_opinion"])
    for h in hits:
        assert h.source_type == "fl_ag_opinion"


@pytest.mark.asyncio
async def test_point_in_time_query_returns_historical_version(seeded_corpus, fake_embed_client):
    r = HybridRetriever(seeded_corpus, fake_embed_client)
    # 2023-06-01: historical LDC §6.4 was valid (2022-01-01 to 2024-01-01)
    valid_at = datetime(2023, 6, 1, tzinfo=timezone.utc)
    hits = await r._bm25_search("permit erected", k=10, valid_at=valid_at)
    # Should find the historical version, not the 2024 version
    matching = [h for h in hits if h.source_id == "ldc.6.4.a.2"]
    assert len(matching) >= 1
    assert "pre-2024" in matching[0].body


@pytest.mark.asyncio
async def test_default_query_excludes_historical_versions(seeded_corpus, fake_embed_client):
    r = HybridRetriever(seeded_corpus, fake_embed_client)
    # No valid_at = current corpus only
    hits = await r._bm25_search("permit erected", k=10)
    for h in hits:
        if h.source_id == "ldc.6.4.a.2":
            assert "pre-2024" not in h.body


@pytest.mark.asyncio
async def test_search_falls_back_to_bm25_when_embed_unavailable(seeded_corpus):
    from mcp_tools._lib.corpus.embed_client import EmbeddingUnavailable
    failing_client = AsyncMock()
    failing_client.embed = AsyncMock(side_effect=EmbeddingUnavailable("test"))
    r = HybridRetriever(seeded_corpus, failing_client)
    hits = await r.search("variance applications", k=5)
    # Should still get BM25 hits, with metadata flag
    assert len(hits) >= 1
    assert any(h.metadata.get("retrieval_mode") == "bm25_only" for h in hits)
```

- [ ] **Step 3: Confirm the test fails for the right reason**

```bash
.venv/bin/python -m pytest tests/mcp_tools/_lib/corpus/test_retriever.py -v
```

Expected: ModuleNotFoundError on `mcp_tools._lib.corpus.retriever`.

- [ ] **Step 4: Implement HybridRetriever**

`mcp_tools/_lib/corpus/retriever.py`:

```python
"""HybridRetriever — BM25 (Postgres ts_rank_cd) + pgvector ANN + RRF merge.

Per spec §6.1 and ADR-001. Library is imported into list_rls_precedents
and get_policy_snippets MCP tools.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

import asyncpg

from mcp_tools._lib.corpus.embed_client import EmbedClient, EmbeddingUnavailable
from mcp_tools._lib.corpus.types import Hit


class HybridRetriever:
    def __init__(
        self,
        db_pool: asyncpg.Pool,
        embed_client: EmbedClient,
        rrf_k: int = 60,
    ):
        self.db_pool = db_pool
        self.embed_client = embed_client
        self.rrf_k = rrf_k

    async def search(
        self,
        query: str,
        k: int = 10,
        source_filter: Optional[list[str]] = None,
        valid_at: Optional[datetime] = None,
    ) -> list[Hit]:
        bm25_task = asyncio.create_task(
            self._bm25_search(query, k=50, source_filter=source_filter, valid_at=valid_at)
        )

        bm25_only_mode = False
        ann_hits: list[Hit] = []
        try:
            query_vec = await self.embed_client.embed(query)
        except EmbeddingUnavailable:
            bm25_only_mode = True
        else:
            ann_hits = await self._ann_search(
                query_vec, k=50, source_filter=source_filter, valid_at=valid_at
            )

        bm25_hits = await bm25_task

        if bm25_only_mode:
            # Mark each hit so callers can surface the degraded mode to the UI.
            for h in bm25_hits:
                h.metadata = {**h.metadata, "retrieval_mode": "bm25_only"}
            return bm25_hits[:k]

        return self._rrf_merge(bm25_hits, ann_hits, k=k, rrf_k=self.rrf_k)

    async def _bm25_search(
        self,
        query: str,
        k: int,
        source_filter: Optional[list[str]] = None,
        valid_at: Optional[datetime] = None,
    ) -> list[Hit]:
        where = []
        args: list = [query]
        if valid_at is None:
            where.append("valid_to IS NULL")
        else:
            where.append("valid_from <= $2 AND (valid_to IS NULL OR valid_to > $2)")
            args.append(valid_at)
        if source_filter:
            ph = f"${len(args) + 1}"
            where.append(f"source_type = ANY({ph})")
            args.append(source_filter)
        args.append(k)
        k_ph = f"${len(args)}"

        sql = f"""
            SELECT id, source_id, source_type, section_path, citation, body,
                   ts_rank_cd(to_tsvector('english', body), plainto_tsquery('english', $1)) AS score,
                   valid_from, valid_to, metadata
            FROM corpus_chunks
            WHERE plainto_tsquery('english', $1) @@ to_tsvector('english', body)
              AND {' AND '.join(where)}
            ORDER BY score DESC
            LIMIT {k_ph}
        """
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(sql, *args)
        if not rows:
            return []
        # Normalize ts_rank_cd scores into [0, 1] by dividing by max in result set.
        max_score = max(r["score"] for r in rows) or 1.0
        hits = []
        for r in rows:
            hits.append(
                Hit(
                    id=r["id"],
                    source_id=r["source_id"],
                    source_type=r["source_type"],
                    section_path=r["section_path"],
                    citation=r["citation"],
                    body=r["body"],
                    score=min(1.0, max(0.0, r["score"] / max_score)),
                    valid_from=r["valid_from"],
                    valid_to=r["valid_to"],
                    metadata=dict(r["metadata"]) if r["metadata"] else {},
                )
            )
        return hits

    async def _ann_search(
        self,
        query_vec: list[float],
        k: int,
        source_filter: Optional[list[str]] = None,
        valid_at: Optional[datetime] = None,
    ) -> list[Hit]:
        where = []
        args: list = [str(query_vec)]  # pgvector accepts text-formatted vector
        if valid_at is None:
            where.append("valid_to IS NULL")
        else:
            where.append("valid_from <= $2 AND (valid_to IS NULL OR valid_to > $2)")
            args.append(valid_at)
        if source_filter:
            ph = f"${len(args) + 1}"
            where.append(f"source_type = ANY({ph})")
            args.append(source_filter)
        args.append(k)
        k_ph = f"${len(args)}"

        sql = f"""
            SELECT id, source_id, source_type, section_path, citation, body,
                   1 - (embedding <=> $1::vector) AS score,
                   valid_from, valid_to, metadata
            FROM corpus_chunks
            WHERE embedding IS NOT NULL
              AND {' AND '.join(where)}
            ORDER BY embedding <=> $1::vector ASC
            LIMIT {k_ph}
        """
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(sql, *args)
        return [
            Hit(
                id=r["id"],
                source_id=r["source_id"],
                source_type=r["source_type"],
                section_path=r["section_path"],
                citation=r["citation"],
                body=r["body"],
                score=min(1.0, max(0.0, float(r["score"]))),
                valid_from=r["valid_from"],
                valid_to=r["valid_to"],
                metadata=dict(r["metadata"]) if r["metadata"] else {},
            )
            for r in rows
        ]

    @staticmethod
    def _rrf_merge(
        bm25_hits: list[Hit],
        ann_hits: list[Hit],
        k: int,
        rrf_k: int = 60,
    ) -> list[Hit]:
        """Reciprocal Rank Fusion (Cormack 2009).

        score(d) = Σ 1 / (rrf_k + rank_in_list_i(d))
        Tie-broken by source_id ascending for stability.
        """
        rrf: dict[str, float] = {}
        first_hit_seen: dict[str, Hit] = {}
        for rank, h in enumerate(bm25_hits, start=1):
            sid = h.source_id
            rrf[sid] = rrf.get(sid, 0.0) + 1.0 / (rrf_k + rank)
            first_hit_seen.setdefault(sid, h)
        for rank, h in enumerate(ann_hits, start=1):
            sid = h.source_id
            rrf[sid] = rrf.get(sid, 0.0) + 1.0 / (rrf_k + rank)
            first_hit_seen.setdefault(sid, h)

        # Sort by RRF score DESC, then source_id ASC for tiebreak
        ordered = sorted(rrf.items(), key=lambda kv: (-kv[1], kv[0]))[:k]

        # Normalize scores into [0, 1] by dividing by max
        if not ordered:
            return []
        max_rrf = ordered[0][1] or 1.0
        result = []
        for sid, score in ordered:
            h = first_hit_seen[sid]
            h.score = min(1.0, max(0.0, score / max_rrf))
            result.append(h)
        return result
```

- [ ] **Step 5: Update package init**

`mcp_tools/_lib/corpus/__init__.py`:

```python
"""Shared retrieval library."""
from mcp_tools._lib.corpus.embed_client import EmbedClient, EmbeddingUnavailable
from mcp_tools._lib.corpus.retriever import HybridRetriever
from mcp_tools._lib.corpus.types import Hit, SourceType

__all__ = [
    "Hit",
    "SourceType",
    "EmbedClient",
    "EmbeddingUnavailable",
    "HybridRetriever",
]
```

- [ ] **Step 6: Run retriever tests**

```bash
.venv/bin/python -m pytest tests/mcp_tools/_lib/corpus/test_retriever.py -v
```

Expected: 8 passed.

Note: this requires the `db_pool` pytest fixture which must already exist from v0.2.0a (`tests/conftest.py` per Plan A's setup). If `db_pool` doesn't exist in the suite at this point, fall through to the conftest section of Plan A Task 3.

- [ ] **Step 7: Run full suite**

```bash
.venv/bin/python -m pytest -q
```

Expected: 139 + 8 = 147 passed.

- [ ] **Step 8: Commit**

```bash
git add mcp_tools/_lib/corpus/retriever.py mcp_tools/_lib/corpus/__init__.py \
        tests/fixtures/corpus_seed.py tests/mcp_tools/_lib/corpus/test_retriever.py
git commit -m "$(cat <<'EOF'
feat(corpus): HybridRetriever — BM25 + pgvector ANN + RRF merge

Per spec §6.1 and ADR-001 (hybrid retrieval). BM25 via Postgres
ts_rank_cd over GIN tsvector index; ANN via pgvector cosine over HNSW
index. Reciprocal Rank Fusion (Cormack 2009, k=60 default) merges both
candidate lists. Tie-broken deterministically by source_id for stable
ordering.

Point-in-time queries (ADR-002) filter on valid_from/valid_to range.
BM25-only fallback path activates when EmbedClient raises
EmbeddingUnavailable (R11 mitigation); falls-back hits are tagged with
metadata.retrieval_mode='bm25_only' so callers can surface the degraded
mode.

W3 acceptance criterion satisfied via test_rrf_merge_is_correct.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: L3 MCP tool — `list_rls_precedents` (port 30103)

**Files:**
- Create: `mcp_tools/list_rls_precedents/__init__.py`
- Create: `mcp_tools/list_rls_precedents/server.py`
- Create: `mcp_tools/list_rls_precedents/requirements.txt`
- Create: `mcp_tools/list_rls_precedents/systemd/list_rls_precedents.service`
- Create: `tests/mcp_tools/list_rls_precedents/__init__.py`
- Create: `tests/mcp_tools/list_rls_precedents/test_server.py`

- [ ] **Step 1: Write the failing server test**

`tests/mcp_tools/list_rls_precedents/test_server.py`:

```python
"""list_rls_precedents L3 MCP tool tests."""
from unittest.mock import AsyncMock, patch

import pytest

from mcp_tools._lib.corpus.types import Hit


@pytest.fixture()
def mock_retriever():
    """Returns a HybridRetriever mock that produces deterministic hits."""
    r = AsyncMock()
    r.search = AsyncMock(return_value=[
        Hit(id=1, source_id="internal_opinion.stub.1", source_type="internal_opinion",
            citation="Internal Opinion 2026-001", body="Vested rights claim...", score=0.9,
            metadata={"matter_type": "permit_or_zoning"}),
        Hit(id=2, source_id="fl-ag.2023-08", source_type="fl_ag_opinion",
            citation="Fla. AGO 2023-08", body="Dual office holding...", score=0.7),
        Hit(id=3, source_id="ldc.6.4.a.2", source_type="ldc",
            citation="LDC §6.4(a)(2)", body="Permit required", score=0.5,
            metadata={"matter_type": "code_enforcement_litigation"}),
    ])
    return r


@pytest.mark.asyncio
async def test_list_rls_precedents_returns_precedent_sources_only(mock_retriever):
    from mcp_tools.list_rls_precedents.server import list_rls_precedents

    with patch("mcp_tools.list_rls_precedents.server._retriever", mock_retriever), \
         patch("mcp_tools.list_rls_precedents.server.require_actor", lambda: type("A", (), {"actor_id": "u1", "dept": "legal", "role_band": "L3"})()), \
         patch("mcp_tools.list_rls_precedents.server._roi_emit", AsyncMock()):
        result = await list_rls_precedents(
            matter_type="permit_or_zoning",
            legal_question="What governs pre-amendment vested rights?",
        )

    mock_retriever.search.assert_called_once()
    # source_filter must restrict to precedent types only
    call_kwargs = mock_retriever.search.call_args.kwargs
    assert set(call_kwargs["source_filter"]) == {"internal_opinion", "fl_ag_opinion"}
    # Only matter_type matches OR fl_ag (matter_type-agnostic) pass through
    hit_ids = [h["source_id"] for h in result["hits"]]
    assert "internal_opinion.stub.1" in hit_ids
    assert "fl-ag.2023-08" in hit_ids
    # ldc.6.4 SHOULD have been excluded by source_filter, never reached the matter_type filter
    assert "ldc.6.4.a.2" not in hit_ids


@pytest.mark.asyncio
async def test_list_rls_precedents_filters_by_matter_type(mock_retriever):
    from mcp_tools.list_rls_precedents.server import list_rls_precedents

    with patch("mcp_tools.list_rls_precedents.server._retriever", mock_retriever), \
         patch("mcp_tools.list_rls_precedents.server.require_actor", lambda: type("A", (), {"actor_id": "u1", "dept": "legal", "role_band": "L3"})()), \
         patch("mcp_tools.list_rls_precedents.server._roi_emit", AsyncMock()):
        result = await list_rls_precedents(
            matter_type="procurement",
            legal_question="contract dispute standing",
        )
    # No matching internal_opinion stub (only stub.1 was permit_or_zoning) — should still pass
    # the fl_ag_opinion through unfiltered (matter_type-agnostic)
    hit_source_types = {h["source_type"] for h in result["hits"]}
    assert "fl_ag_opinion" in hit_source_types or len(result["hits"]) == 0


@pytest.mark.asyncio
async def test_list_rls_precedents_emits_rag_hit(mock_retriever):
    from mcp_tools.list_rls_precedents.server import list_rls_precedents
    captured = []

    async def capture(event_kind, payload):
        captured.append((event_kind, payload))

    with patch("mcp_tools.list_rls_precedents.server._retriever", mock_retriever), \
         patch("mcp_tools.list_rls_precedents.server.require_actor", lambda: type("A", (), {"actor_id": "u42", "dept": "legal", "role_band": "L3"})()), \
         patch("mcp_tools.list_rls_precedents.server._roi_emit", capture):
        await list_rls_precedents(matter_type="permit_or_zoning", legal_question="x")

    assert len(captured) == 1
    kind, payload = captured[0]
    assert kind == "rag_hit"
    assert payload["user_id"] == "u42"
    assert payload["tool"] == "rls_apex"
    assert payload["surface"] == "other"
    assert payload["task_type"] == "search"
    assert payload["success"] is True
    assert "hit_count" in payload["extra"]
    assert payload["extra"]["matter_type"] == "permit_or_zoning"


@pytest.mark.asyncio
async def test_list_rls_precedents_emits_failure_on_raise(mock_retriever):
    from mcp_tools.list_rls_precedents.server import list_rls_precedents
    captured = []

    async def capture(event_kind, payload):
        captured.append((event_kind, payload))

    mock_retriever.search = AsyncMock(side_effect=RuntimeError("retriever exploded"))
    with patch("mcp_tools.list_rls_precedents.server._retriever", mock_retriever), \
         patch("mcp_tools.list_rls_precedents.server.require_actor", lambda: type("A", (), {"actor_id": "u1", "dept": "legal", "role_band": "L3"})()), \
         patch("mcp_tools.list_rls_precedents.server._roi_emit", capture):
        with pytest.raises(RuntimeError):
            await list_rls_precedents(matter_type="permit_or_zoning", legal_question="x")

    # success=False emit must precede the raise (per Lock #7)
    assert len(captured) == 1
    assert captured[0][1]["success"] is False
```

- [ ] **Step 2: Run — confirm failure**

```bash
.venv/bin/python -m pytest tests/mcp_tools/list_rls_precedents/test_server.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement the L3 tool**

`mcp_tools/list_rls_precedents/__init__.py`: empty.

`mcp_tools/list_rls_precedents/server.py`:

```python
"""L3 — list_rls_precedents MCP tool, port 30103.

Per spec §6.3. Source-filtered to precedent types (internal_opinion +
fl_ag_opinion), with optional matter_type filtering against chunk metadata.
Emits ROI rag_hit per ADR-004.
"""
from __future__ import annotations

import asyncpg
import os
from datetime import datetime
from typing import Optional

from apps.gateway.tools import build_tool_app, require_actor
from apps.gateway.sidecar import roi_emit
from mcp_tools._lib.corpus.embed_client import EmbedClient
from mcp_tools._lib.corpus.retriever import HybridRetriever


# Module-level constants per the ROI emit hardening pattern (Option C, ADR-001 of
# roi-emit-contract-hardening-design)
_EMIT_DEFAULTS = {
    "workflow": "rls_apex",
    "tool": "rls_apex",
    "surface": "other",
    "task_type": "search",
}

PRECEDENT_SOURCES = ["internal_opinion", "fl_ag_opinion"]

# Module-level singletons wired up at lifespan startup
_db_pool: Optional[asyncpg.Pool] = None
_retriever: Optional[HybridRetriever] = None


async def _roi_emit(event_kind: str, payload: dict) -> None:
    """Indirection so tests can patch the emit call without monkey-patching the sidecar."""
    await roi_emit(event_kind=event_kind, **payload)


async def list_rls_precedents(
    matter_type: str,
    legal_question: str,
    factual_keywords: Optional[list[str]] = None,
    valid_at: Optional[datetime] = None,
    k: int = 5,
) -> dict:
    actor = require_actor()
    query = legal_question + " " + " ".join(factual_keywords or [])
    try:
        hits = await _retriever.search(
            query=query,
            k=k * 4,  # over-fetch; matter_type filter trims downstream
            source_filter=PRECEDENT_SOURCES,
            valid_at=valid_at,
        )
        # Matter-type filter: keep stubs that match matter_type OR fl_ag opinions
        # (FL AG opinions are matter-type agnostic per spec §6.3 inline code)
        filtered = [
            h for h in hits
            if h.metadata.get("matter_type") == matter_type
            or h.source_type == "fl_ag_opinion"
        ][:k]
        await _roi_emit("rag_hit", {
            **_EMIT_DEFAULTS,
            "user_id": actor.actor_id,
            "dept": getattr(actor, "dept", "unknown"),
            "role_band": getattr(actor, "role_band", "unknown"),
            "success": True,
            "extra": {
                "matter_type": matter_type,
                "hit_count": len(filtered),
                "valid_at": valid_at.isoformat() if valid_at else None,
                "k": k,
            },
        })
        return {"hits": [h.model_dump() for h in filtered]}
    except Exception:
        await _roi_emit("rag_hit", {
            **_EMIT_DEFAULTS,
            "user_id": actor.actor_id,
            "dept": getattr(actor, "dept", "unknown"),
            "role_band": getattr(actor, "role_band", "unknown"),
            "success": False,
            "extra": {"matter_type": matter_type, "hit_count": 0, "k": k},
        })
        raise


async def _lifespan_startup(app):
    global _db_pool, _retriever
    _db_pool = await asyncpg.create_pool(os.environ["DATABASE_URL"])
    embed_client = EmbedClient(
        base_url=os.environ.get("EMBEDDING_SERVICE_URL", "http://127.0.0.1:30201")
    )
    _retriever = HybridRetriever(_db_pool, embed_client)


async def _lifespan_shutdown(app):
    if _db_pool is not None:
        await _db_pool.close()


app = build_tool_app(
    tool_name="list_rls_precedents",
    tool_callable=list_rls_precedents,
    port=30103,
    on_startup=_lifespan_startup,
    on_shutdown=_lifespan_shutdown,
)
```

`mcp_tools/list_rls_precedents/requirements.txt`:

```
# Inherits root requirements + mcp_tools/_lib/corpus deps
fastapi==0.115.0
uvicorn[standard]==0.30.6
asyncpg==0.29.0
httpx==0.27.2
pydantic==2.9.2
```

`mcp_tools/list_rls_precedents/systemd/list_rls_precedents.service`:

```ini
[Unit]
Description=RLS Apex — list_rls_precedents MCP tool (L3)
After=network.target postgresql.service embedding-service.service
Wants=embedding-service.service

[Service]
Type=simple
User=rls_apex
WorkingDirectory=/opt/rls-apex-v1
ExecStart=/opt/rls-apex-v1/.venv/bin/uvicorn mcp_tools.list_rls_precedents.server:app --host 127.0.0.1 --port 30103
Environment="DATABASE_URL=postgresql://rls_apex:CHANGE_ME@localhost/rls_apex"
Environment="EMBEDDING_SERVICE_URL=http://127.0.0.1:30201"
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 4: Run the L3 tests**

```bash
.venv/bin/python -m pytest tests/mcp_tools/list_rls_precedents/test_server.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Run full suite**

```bash
.venv/bin/python -m pytest -q
```

Expected: 147 + 4 = 151 passed.

- [ ] **Step 6: Commit**

```bash
git add mcp_tools/list_rls_precedents/ tests/mcp_tools/list_rls_precedents/
git commit -m "$(cat <<'EOF'
feat(mcp): L3 list_rls_precedents tool — port 30103

Per spec §6.3. source_filter pinned to precedent types
(internal_opinion + fl_ag_opinion). matter_type filter applied
in-process (FL AG opinions pass through agnostic per inline spec code).
Emits rag_hit ROI events with hit_count + matter_type in extra; emits
success=False before raising on retriever failure (Lock #7).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: L4 MCP tool — `get_policy_snippets` (port 30104)

**Files:**
- Create: `mcp_tools/get_policy_snippets/__init__.py`
- Create: `mcp_tools/get_policy_snippets/server.py`
- Create: `mcp_tools/get_policy_snippets/requirements.txt`
- Create: `mcp_tools/get_policy_snippets/systemd/get_policy_snippets.service`
- Create: `tests/mcp_tools/get_policy_snippets/__init__.py`
- Create: `tests/mcp_tools/get_policy_snippets/test_server.py`

- [ ] **Step 1: Write the failing server test**

`tests/mcp_tools/get_policy_snippets/test_server.py`:

```python
"""get_policy_snippets L4 MCP tool tests."""
from unittest.mock import AsyncMock, patch

import pytest

from mcp_tools._lib.corpus.types import Hit


@pytest.fixture()
def mock_retriever_with_procedure():
    r = AsyncMock()
    r.search = AsyncMock(return_value=[
        Hit(id=1, source_id="ldc.6.4.a.2", source_type="ldc",
            citation="LDC §6.4(a)(2)", body="Permit required", score=0.9),
        Hit(id=2, source_id="procedure.26-104.001.2", source_type="procedure",
            citation="Procedure 26-104.001 §2", body="NOV references...", score=0.8),
    ])
    return r


@pytest.fixture()
def mock_retriever_without_procedure():
    r = AsyncMock()
    r.search = AsyncMock(return_value=[
        Hit(id=1, source_id="ldc.6.4.a.2", source_type="ldc",
            citation="LDC §6.4(a)(2)", body="Permit required", score=0.9),
    ])
    return r


@pytest.mark.asyncio
async def test_get_policy_snippets_returns_policy_sources_only(mock_retriever_with_procedure):
    from mcp_tools.get_policy_snippets.server import get_policy_snippets

    with patch("mcp_tools.get_policy_snippets.server._retriever", mock_retriever_with_procedure), \
         patch("mcp_tools.get_policy_snippets.server.require_actor", lambda: type("A", (), {"actor_id": "u1", "dept": "legal", "role_band": "L3"})()), \
         patch("mcp_tools.get_policy_snippets.server._roi_emit", AsyncMock()):
        result = await get_policy_snippets(topic_or_field="permit denial process")

    call_kwargs = mock_retriever_with_procedure.search.call_args.kwargs
    assert set(call_kwargs["source_filter"]) == {"ldc", "ordinance", "procedure"}


@pytest.mark.asyncio
async def test_get_policy_snippets_flags_procedure_pending_when_no_procedure_hit(mock_retriever_without_procedure):
    from mcp_tools.get_policy_snippets.server import get_policy_snippets

    with patch("mcp_tools.get_policy_snippets.server._retriever", mock_retriever_without_procedure), \
         patch("mcp_tools.get_policy_snippets.server.require_actor", lambda: type("A", (), {"actor_id": "u1", "dept": "legal", "role_band": "L3"})()), \
         patch("mcp_tools.get_policy_snippets.server._roi_emit", AsyncMock()):
        result = await get_policy_snippets(topic_or_field="RLS form requirements")

    assert result["procedure_corpus_pending"] is True


@pytest.mark.asyncio
async def test_get_policy_snippets_does_not_flag_pending_when_procedure_hit_present(mock_retriever_with_procedure):
    from mcp_tools.get_policy_snippets.server import get_policy_snippets

    with patch("mcp_tools.get_policy_snippets.server._retriever", mock_retriever_with_procedure), \
         patch("mcp_tools.get_policy_snippets.server.require_actor", lambda: type("A", (), {"actor_id": "u1", "dept": "legal", "role_band": "L3"})()), \
         patch("mcp_tools.get_policy_snippets.server._roi_emit", AsyncMock()):
        result = await get_policy_snippets(topic_or_field="NOV procedure")

    assert result["procedure_corpus_pending"] is False


@pytest.mark.asyncio
async def test_get_policy_snippets_emits_rag_hit_with_procedure_availability(mock_retriever_with_procedure):
    from mcp_tools.get_policy_snippets.server import get_policy_snippets
    captured = []

    async def capture(event_kind, payload):
        captured.append((event_kind, payload))

    with patch("mcp_tools.get_policy_snippets.server._retriever", mock_retriever_with_procedure), \
         patch("mcp_tools.get_policy_snippets.server.require_actor", lambda: type("A", (), {"actor_id": "u9", "dept": "legal", "role_band": "L3"})()), \
         patch("mcp_tools.get_policy_snippets.server._roi_emit", capture):
        await get_policy_snippets(topic_or_field="NOV procedure")

    assert len(captured) == 1
    kind, payload = captured[0]
    assert kind == "rag_hit"
    assert payload["extra"]["procedure_corpus_available"] is True
```

- [ ] **Step 2: Run — confirm failure**

```bash
.venv/bin/python -m pytest tests/mcp_tools/get_policy_snippets/test_server.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement the L4 tool**

`mcp_tools/get_policy_snippets/__init__.py`: empty.

`mcp_tools/get_policy_snippets/server.py`:

```python
"""L4 — get_policy_snippets MCP tool, port 30104.

Per spec §6.4. Filters to policy-and-procedure source types. Surfaces
`procedure_corpus_pending` flag when no procedure-source hits return,
so the frontend can show "internal procedure corpus pending Legal
confirmation" inline (per spec R7 mitigation).
"""
from __future__ import annotations

import asyncpg
import os
from datetime import datetime
from typing import Optional

from apps.gateway.tools import build_tool_app, require_actor
from apps.gateway.sidecar import roi_emit
from mcp_tools._lib.corpus.embed_client import EmbedClient
from mcp_tools._lib.corpus.retriever import HybridRetriever


_EMIT_DEFAULTS = {
    "workflow": "rls_apex",
    "tool": "rls_apex",
    "surface": "other",
    "task_type": "search",
}

POLICY_SOURCES = ["ldc", "ordinance", "procedure"]

_db_pool: Optional[asyncpg.Pool] = None
_retriever: Optional[HybridRetriever] = None


async def _roi_emit(event_kind: str, payload: dict) -> None:
    await roi_emit(event_kind=event_kind, **payload)


async def get_policy_snippets(
    topic_or_field: str,
    rls_id: Optional[str] = None,
    valid_at: Optional[datetime] = None,
    k: int = 3,
) -> dict:
    actor = require_actor()
    try:
        hits = await _retriever.search(
            query=topic_or_field,
            k=k,
            source_filter=POLICY_SOURCES,
            valid_at=valid_at,
        )
        has_procedure = any(h.source_type == "procedure" for h in hits)
        await _roi_emit("rag_hit", {
            **_EMIT_DEFAULTS,
            "user_id": actor.actor_id,
            "dept": getattr(actor, "dept", "unknown"),
            "role_band": getattr(actor, "role_band", "unknown"),
            "success": True,
            "extra": {
                "topic": topic_or_field,
                "hit_count": len(hits),
                "procedure_corpus_available": has_procedure,
                "k": k,
                "rls_id": rls_id,
            },
        })
        return {
            "snippets": [h.model_dump() for h in hits[:k]],
            "procedure_corpus_pending": not has_procedure,
        }
    except Exception:
        await _roi_emit("rag_hit", {
            **_EMIT_DEFAULTS,
            "user_id": actor.actor_id,
            "dept": getattr(actor, "dept", "unknown"),
            "role_band": getattr(actor, "role_band", "unknown"),
            "success": False,
            "extra": {"topic": topic_or_field, "hit_count": 0, "k": k},
        })
        raise


async def _lifespan_startup(app):
    global _db_pool, _retriever
    _db_pool = await asyncpg.create_pool(os.environ["DATABASE_URL"])
    embed_client = EmbedClient(
        base_url=os.environ.get("EMBEDDING_SERVICE_URL", "http://127.0.0.1:30201")
    )
    _retriever = HybridRetriever(_db_pool, embed_client)


async def _lifespan_shutdown(app):
    if _db_pool is not None:
        await _db_pool.close()


app = build_tool_app(
    tool_name="get_policy_snippets",
    tool_callable=get_policy_snippets,
    port=30104,
    on_startup=_lifespan_startup,
    on_shutdown=_lifespan_shutdown,
)
```

`mcp_tools/get_policy_snippets/requirements.txt`:

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
asyncpg==0.29.0
httpx==0.27.2
pydantic==2.9.2
```

`mcp_tools/get_policy_snippets/systemd/get_policy_snippets.service`:

```ini
[Unit]
Description=RLS Apex — get_policy_snippets MCP tool (L4)
After=network.target postgresql.service embedding-service.service
Wants=embedding-service.service

[Service]
Type=simple
User=rls_apex
WorkingDirectory=/opt/rls-apex-v1
ExecStart=/opt/rls-apex-v1/.venv/bin/uvicorn mcp_tools.get_policy_snippets.server:app --host 127.0.0.1 --port 30104
Environment="DATABASE_URL=postgresql://rls_apex:CHANGE_ME@localhost/rls_apex"
Environment="EMBEDDING_SERVICE_URL=http://127.0.0.1:30201"
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 4: Run the L4 tests**

```bash
.venv/bin/python -m pytest tests/mcp_tools/get_policy_snippets/test_server.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Run full suite**

```bash
.venv/bin/python -m pytest -q
```

Expected: 151 + 4 = 155 passed.

- [ ] **Step 6: Commit**

```bash
git add mcp_tools/get_policy_snippets/ tests/mcp_tools/get_policy_snippets/
git commit -m "$(cat <<'EOF'
feat(mcp): L4 get_policy_snippets tool — port 30104

Per spec §6.4. source_filter pinned to {ldc, ordinance, procedure}.
Surfaces procedure_corpus_pending=true when no source_type='procedure'
hit returns, so frontend shows "internal procedure corpus pending Legal
confirmation" inline (spec R7 mitigation).

ROI emits include procedure_corpus_available in extra so Power BI can
track adoption once Procedure 26-104.001 source is verified.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Emit-compliance parametrize for L3 + L4 (E1 acceptance)

**Files:**
- Create: `tests/mcp_tools/list_rls_precedents/test_emit_compliance.py`
- Create: `tests/mcp_tools/get_policy_snippets/test_emit_compliance.py`

The existing v0.2.0a emit-compliance parametrize is in
`tests/test_emit_compliance.py` (per Plan A baseline). E1 in the spec
asks us to extend the parametrized test to cover L3 and L4. Easiest
non-fragile approach: add per-tool emit-compliance tests in each tool's
test dir that import the shared `validate_event_for_persistence` and
invoke the tool with realistic args, asserting the emit payload passes
the schema.

- [ ] **Step 1: L3 emit-compliance test**

`tests/mcp_tools/list_rls_precedents/test_emit_compliance.py`:

```python
"""E1 — list_rls_precedents emit must pass validate_event_for_persistence."""
from unittest.mock import AsyncMock, patch

import pytest

from mcp_tools._lib.corpus.types import Hit
from manatee_ai_roi.validation import validate_event_for_persistence


@pytest.mark.asyncio
async def test_list_rls_precedents_emit_success_passes_schema():
    from mcp_tools.list_rls_precedents.server import list_rls_precedents
    captured = []

    async def capture(event_kind, payload):
        captured.append((event_kind, payload))

    fake_retriever = AsyncMock()
    fake_retriever.search = AsyncMock(return_value=[
        Hit(id=1, source_id="x", source_type="internal_opinion",
            citation="x", body="x", score=0.9, metadata={"matter_type": "permit_or_zoning"})
    ])

    with patch("mcp_tools.list_rls_precedents.server._retriever", fake_retriever), \
         patch("mcp_tools.list_rls_precedents.server.require_actor", lambda: type("A", (), {"actor_id": "u1", "dept": "legal", "role_band": "L3"})()), \
         patch("mcp_tools.list_rls_precedents.server._roi_emit", capture):
        await list_rls_precedents(matter_type="permit_or_zoning", legal_question="x")

    assert len(captured) == 1
    kind, payload = captured[0]
    # Synthesize the wire event: emit_event takes event_kind as separate arg + payload fields
    event = {"event_kind": kind, **payload}
    # Should not raise
    validate_event_for_persistence(event)


@pytest.mark.asyncio
async def test_list_rls_precedents_emit_failure_passes_schema():
    from mcp_tools.list_rls_precedents.server import list_rls_precedents
    captured = []

    async def capture(event_kind, payload):
        captured.append((event_kind, payload))

    fake_retriever = AsyncMock()
    fake_retriever.search = AsyncMock(side_effect=RuntimeError("boom"))

    with patch("mcp_tools.list_rls_precedents.server._retriever", fake_retriever), \
         patch("mcp_tools.list_rls_precedents.server.require_actor", lambda: type("A", (), {"actor_id": "u1", "dept": "legal", "role_band": "L3"})()), \
         patch("mcp_tools.list_rls_precedents.server._roi_emit", capture):
        with pytest.raises(RuntimeError):
            await list_rls_precedents(matter_type="permit_or_zoning", legal_question="x")

    event = {"event_kind": captured[0][0], **captured[0][1]}
    validate_event_for_persistence(event)
```

- [ ] **Step 2: L4 emit-compliance test**

`tests/mcp_tools/get_policy_snippets/test_emit_compliance.py`:

```python
"""E1 — get_policy_snippets emit must pass validate_event_for_persistence."""
from unittest.mock import AsyncMock, patch

import pytest

from mcp_tools._lib.corpus.types import Hit
from manatee_ai_roi.validation import validate_event_for_persistence


@pytest.mark.asyncio
async def test_get_policy_snippets_emit_success_passes_schema():
    from mcp_tools.get_policy_snippets.server import get_policy_snippets
    captured = []

    async def capture(event_kind, payload):
        captured.append((event_kind, payload))

    fake_retriever = AsyncMock()
    fake_retriever.search = AsyncMock(return_value=[
        Hit(id=1, source_id="procedure.x", source_type="procedure",
            citation="x", body="x", score=0.9)
    ])

    with patch("mcp_tools.get_policy_snippets.server._retriever", fake_retriever), \
         patch("mcp_tools.get_policy_snippets.server.require_actor", lambda: type("A", (), {"actor_id": "u1", "dept": "legal", "role_band": "L3"})()), \
         patch("mcp_tools.get_policy_snippets.server._roi_emit", capture):
        await get_policy_snippets(topic_or_field="permit denial")

    event = {"event_kind": captured[0][0], **captured[0][1]}
    validate_event_for_persistence(event)


@pytest.mark.asyncio
async def test_get_policy_snippets_emit_failure_passes_schema():
    from mcp_tools.get_policy_snippets.server import get_policy_snippets
    captured = []

    async def capture(event_kind, payload):
        captured.append((event_kind, payload))

    fake_retriever = AsyncMock()
    fake_retriever.search = AsyncMock(side_effect=RuntimeError("boom"))

    with patch("mcp_tools.get_policy_snippets.server._retriever", fake_retriever), \
         patch("mcp_tools.get_policy_snippets.server.require_actor", lambda: type("A", (), {"actor_id": "u1", "dept": "legal", "role_band": "L3"})()), \
         patch("mcp_tools.get_policy_snippets.server._roi_emit", capture):
        with pytest.raises(RuntimeError):
            await get_policy_snippets(topic_or_field="permit denial")

    event = {"event_kind": captured[0][0], **captured[0][1]}
    validate_event_for_persistence(event)
```

- [ ] **Step 3: Run the compliance tests**

```bash
.venv/bin/python -m pytest tests/mcp_tools/list_rls_precedents/test_emit_compliance.py \
                        tests/mcp_tools/get_policy_snippets/test_emit_compliance.py -v
```

Expected: 4 passed.

If `validate_event_for_persistence` import fails, the rag_hit event-kind may not be in the schema yet — verify `apps/gateway/sidecar/manatee_ai_roi.schema.json` includes a `rag_hit` example under the event-kind enum. If missing, add it (see Task 9's verify step which audits the schema). The schema file is a vendored copy of `manatee-ai-roi`'s authoritative JSON Schema — the source-of-truth is `~/Projects/manatee-ai-roi/src/manatee_ai_roi/schema.py` per Operating Rule #18.

- [ ] **Step 4: Run full suite**

```bash
.venv/bin/python -m pytest -q
```

Expected: 155 + 4 = 159 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/mcp_tools/list_rls_precedents/test_emit_compliance.py \
        tests/mcp_tools/get_policy_snippets/test_emit_compliance.py
git commit -m "$(cat <<'EOF'
test(emit-compliance): E1 — L3 + L4 emit shapes validated against schema

Per spec §15 E1. Both success and failure (success=False on raise) emit
paths must pass validate_event_for_persistence against the Operating
Rule #18 ROI schema. Vendored schema lives at
apps/gateway/sidecar/manatee_ai_roi.schema.json.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Embedding-breaker fallback integration test (E2)

**Files:**
- Create: `tests/integration/test_embedding_breaker_fallback.py`
- Verify (no edit unless missing): `apps/gateway/sidecar/manatee_ai_roi.schema.json` includes `rag_hit` event-kind

This test exercises the real embedding-service `app` against a mocked
Ollama. When Ollama is "down," after 3 failures the breaker opens,
embedding-service returns 503, EmbedClient raises EmbeddingUnavailable,
and HybridRetriever falls back to BM25-only. Each downstream hit must
carry `metadata.retrieval_mode == "bm25_only"`.

- [ ] **Step 1: Audit the schema first**

```bash
.venv/bin/python -c "
import json
with open('apps/gateway/sidecar/manatee_ai_roi.schema.json') as f:
    schema = json.load(f)
print('event_kind enum:')
# Schema structure varies — print the enum/anyOf branches
import re
text = json.dumps(schema)
# Grep for rag_hit
print('rag_hit present:', 'rag_hit' in text)
"
```

Expected: `rag_hit present: True`. If False, the schema needs the
`rag_hit` event-kind added. Add it now:

If not present, open `apps/gateway/sidecar/manatee_ai_roi.schema.json`,
locate the `event_kind` enum (likely under `properties.event_kind.enum`
or a `oneOf` branch), and append `"rag_hit"`. Re-run the audit.

- [ ] **Step 2: Write the failing integration test**

`tests/integration/test_embedding_breaker_fallback.py`:

```python
"""E2 — Embedding breaker → BM25-only retrieval fallback.

Exercises the chain:
  HybridRetriever.search → EmbedClient.embed → embedding-service /embed
  → Ollama call (mocked failing) → breaker opens → 503 → EmbedClient
  raises EmbeddingUnavailable → HybridRetriever drops to BM25-only.

Validates the bm25_only retrieval_mode metadata is set on every hit.
"""
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from mcp_tools._lib.corpus.embed_client import EmbedClient
from mcp_tools._lib.corpus.retriever import HybridRetriever
from tests.fixtures.corpus_seed import seeded_corpus  # noqa: F401


@pytest.mark.asyncio
async def test_breaker_open_falls_back_to_bm25(seeded_corpus, httpx_mock):
    """When embedding-service returns 503, retrieval still returns hits, marked bm25_only."""
    embedding_service_url = "http://127.0.0.1:30201"
    # Mock embedding-service responses: always 503 (breaker-open simulation)
    httpx_mock.add_response(
        url=f"{embedding_service_url}/embed",
        status_code=503,
        json={"detail": "breaker open"},
    )
    embed_client = EmbedClient(base_url=embedding_service_url)
    r = HybridRetriever(seeded_corpus, embed_client)
    hits = await r.search("variance applications", k=5)

    assert len(hits) >= 1, "BM25-only path must still return at least one hit"
    assert all(h.metadata.get("retrieval_mode") == "bm25_only" for h in hits), \
        "Every hit must be tagged bm25_only so the frontend can surface degraded mode"


@pytest.mark.asyncio
async def test_breaker_recovery_returns_to_hybrid(seeded_corpus, httpx_mock):
    """When embedding-service returns 200 again, retrieval is hybrid (no bm25_only tag)."""
    from tests.fixtures.corpus_seed import _deterministic_embedding

    embedding_service_url = "http://127.0.0.1:30201"
    # Provide a real-looking embedding response so ANN search returns a known top hit
    target_seed = "ldc.6.4.a.2"
    vec = _deterministic_embedding(target_seed)
    httpx_mock.add_response(
        url=f"{embedding_service_url}/embed",
        status_code=200,
        json={"embedding": vec},
    )
    embed_client = EmbedClient(base_url=embedding_service_url)
    r = HybridRetriever(seeded_corpus, embed_client)
    hits = await r.search("permit erected", k=5)

    assert len(hits) >= 1
    # bm25_only tag should NOT be present when hybrid path executed
    assert all(h.metadata.get("retrieval_mode") != "bm25_only" for h in hits)
```

- [ ] **Step 3: Confirm failure**

```bash
.venv/bin/python -m pytest tests/integration/test_embedding_breaker_fallback.py -v
```

Expected: passes if HybridRetriever already sets `retrieval_mode` (Task 5 did), but `pytest-httpx` may need to be installed.

If `pytest-httpx` is missing:

```bash
.venv/bin/pip install pytest-httpx
```

Pin in `requirements-dev.txt`:

```
pytest-httpx==0.30.0
```

- [ ] **Step 4: Run — verify pass**

```bash
.venv/bin/python -m pytest tests/integration/test_embedding_breaker_fallback.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Run full suite**

```bash
.venv/bin/python -m pytest -q
```

Expected: 159 + 2 = 161 passed.

- [ ] **Step 6: Commit**

```bash
git add tests/integration/test_embedding_breaker_fallback.py requirements-dev.txt
git commit -m "$(cat <<'EOF'
test(integration): E2 — embedding-breaker fallback drops to BM25-only

Per spec §15 E2. When embedding-service returns 503 (breaker-open
simulation), HybridRetriever drops to BM25-only and tags every Hit
with metadata.retrieval_mode='bm25_only' so the frontend can surface
the degraded mode via the smart-surface contract.

When embedding-service is healthy again, hybrid path resumes and the
bm25_only tag is absent.

Adds pytest-httpx dev dependency.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Retrieval integration smoke through the gateway

**Files:**
- Create: `tests/integration/test_retrieval_smoke.py`

End-to-end happy path: gateway routes a `list_rls_precedents` call to
the L3 MCP tool, hits land, ROI emits flow through. The L3/L4 tools
expose themselves via `build_tool_app`'s MCP transport — gateway
already wires this in v0.2.0a (`apps/gateway/mcp_router.py` or
equivalent). This smoke test verifies the new tools are reachable.

- [ ] **Step 1: Write the smoke test**

`tests/integration/test_retrieval_smoke.py`:

```python
"""End-to-end retrieval smoke: gateway → L3 → corpus_chunks → ROI emit."""
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from apps.gateway.main import app as gateway_app
from tests.fixtures.corpus_seed import seeded_corpus  # noqa: F401


@pytest.mark.asyncio
async def test_intake_then_list_precedents_through_gateway(seeded_corpus):
    """POST a payload that classifies into permit_or_zoning, then verify L3 retrieves stub.1."""
    captured_emits: list[dict] = []

    async def capture_emit(event_kind, **payload):
        captured_emits.append({"event_kind": event_kind, **payload})

    # Patch the embedding service URL so the in-test EmbedClient won't try a real socket
    with patch("apps.gateway.sidecar.roi_emit", capture_emit):
        async with AsyncClient(transport=ASGITransport(app=gateway_app), base_url="http://test") as ac:
            # Direct MCP tool call through the gateway's tool router
            # (Exact path depends on existing gateway routes — v0.2.0a uses /api/mcp/{tool})
            r = await ac.post(
                "/api/mcp/list_rls_precedents",
                json={
                    "matter_type": "permit_or_zoning",
                    "legal_question": "vested rights before LDC amendment",
                },
                headers={"X-Actor-Id": "u1", "X-Actor-Dept": "legal", "X-Actor-Role": "L3"},
            )

    assert r.status_code == 200
    body = r.json()
    assert "hits" in body
    # At least one hit (the stub.1 has matter_type=permit_or_zoning in seed metadata)
    assert len(body["hits"]) >= 1
    # At least one ROI rag_hit emit
    rag_emits = [e for e in captured_emits if e["event_kind"] == "rag_hit"]
    assert len(rag_emits) >= 1
    assert rag_emits[0]["success"] is True
```

**Note for executor:** The seed fixture in Task 5 set
`metadata={}` on insert. To make this smoke test pass against L3's
matter_type filter, update `tests/fixtures/corpus_seed.py` to set
`metadata={"matter_type": "permit_or_zoning"}` for `internal_opinion.stub.1`,
`metadata={"matter_type": "code_enforcement_litigation"}` for stub.2,
`metadata={"matter_type": "procurement"}` for stub.3,
`metadata={"matter_type": "general_advisory"}` for stub.4,
`metadata={"matter_type": "public_records"}` for stub.5.

If you've already committed the seed without metadata, fix it now and
re-run Task 5's retriever tests to confirm no regression before
proceeding.

- [ ] **Step 2: Apply the seed metadata fix**

Patch `tests/fixtures/corpus_seed.py` SEED_BODIES — change the
internal_opinion rows from 5-tuples to 6-tuples and add a metadata
column. If your implementation already accepts metadata as a 6th tuple
element, update the loop in the fixture accordingly:

```python
# In tests/fixtures/corpus_seed.py — adjust loop to read metadata from tuples
INTERNAL_METADATA = {
    "internal_opinion.stub.1": {"matter_type": "permit_or_zoning"},
    "internal_opinion.stub.2": {"matter_type": "code_enforcement_litigation"},
    "internal_opinion.stub.3": {"matter_type": "procurement"},
    "internal_opinion.stub.4": {"matter_type": "general_advisory"},
    "internal_opinion.stub.5": {"matter_type": "public_records"},
}

# In the insert loop:
for source_type, sid, section, citation, body in SEED_BODIES:
    meta = INTERNAL_METADATA.get(sid, {})
    # ... pass json.dumps(meta) where "{}" used to go
```

This is a fixture-only change; existing retriever tests don't depend on
metadata so they keep passing.

- [ ] **Step 3: Run smoke test**

```bash
.venv/bin/python -m pytest tests/integration/test_retrieval_smoke.py -v
```

Expected: 1 passed.

If the gateway path `/api/mcp/list_rls_precedents` doesn't exist (v0.2.0a
may use a different convention), grep the existing gateway main module
for the MCP dispatch endpoint and adjust the test URL. Example:

```bash
grep -n "mcp" apps/gateway/main.py apps/gateway/routes/*.py 2>/dev/null | head -10
```

- [ ] **Step 4: Run full suite**

```bash
.venv/bin/python -m pytest -q
```

Expected: 161 + 1 = 162 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_retrieval_smoke.py tests/fixtures/corpus_seed.py
git commit -m "$(cat <<'EOF'
test(integration): retrieval smoke — gateway → L3 → corpus → ROI

End-to-end happy path: gateway routes list_rls_precedents call, L3
queries corpus_chunks via HybridRetriever, hits land, rag_hit emit
flows through the sidecar. Stub.1 metadata.matter_type now matches the
permit_or_zoning query so the matter_type filter retains the hit.

Fixture seed updated: 5 internal_opinion stubs each carry a
matter_type label matching spec §5.2.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: systemd units + deployment notes

**Files:**
- Already created in Tasks 3, 6, 7:
  - `services/embedding/systemd/embedding.service`
  - `mcp_tools/list_rls_precedents/systemd/list_rls_precedents.service`
  - `mcp_tools/get_policy_snippets/systemd/get_policy_snippets.service`
- Create: `docs/runbooks/2026-05-12-v0_2_1a-stream-c-deploy-notes.md`

The systemd unit files were committed alongside their respective
services. This task closes Plan C with a runbook section so the
operator knows how to wire the new units on `bcc-ap-llm01`.

- [ ] **Step 1: Write the deploy notes**

`docs/runbooks/2026-05-12-v0_2_1a-stream-c-deploy-notes.md`:

```markdown
# RLS Apex v0.2.1a Stream C — Deploy Notes

## What ships with Stream C

3 new systemd units on `bcc-ap-llm01`:

| Unit | Port | Source |
|---|---|---|
| `embedding-service.service` | 30201 | `services/embedding/systemd/embedding.service` |
| `list_rls_precedents.service` | 30103 | `mcp_tools/list_rls_precedents/systemd/list_rls_precedents.service` |
| `get_policy_snippets.service` | 30104 | `mcp_tools/get_policy_snippets/systemd/get_policy_snippets.service` |

Plus 1 alembic migration: `embedding` column → `vector(1024)` + HNSW index.

## Preconditions

- Plan A merged (`scraper-service` running; `corpus_chunks` table seeded with
  scraped LDC + Ch. 2-26 + mymanatee + FL AG content)
- Plan B merged (18 stub opinions onboarded as `source_type='internal_opinion'`)
- Postgres has `pgvector` extension installed (verify: `SELECT * FROM pg_extension WHERE extname = 'vector';`)
- Ollama on `bcc-ap-infer01` has `mxbai-embed-large` pulled (verify: `curl http://bcc-ap-infer01:11434/api/tags | grep mxbai-embed-large`)

If pgvector is not installed, install via Homebrew (`brew install pgvector`) and
restart Postgres before the migration. The alembic migration will fail with
`ERROR: extension "vector" is not available` until pgvector is present.

## Deploy steps

1. SSH to `bcc-ap-llm01`:

   ```bash
   ssh rls_apex@bcc-ap-llm01
   ```

2. Pull and migrate:

   ```bash
   cd /opt/rls-apex-v1
   git fetch origin
   git checkout feat/v0.2.0a-backend  # or feat/v0.2.1a if rebased
   git pull
   .venv/bin/alembic upgrade head
   ```

3. Install units:

   ```bash
   sudo cp services/embedding/systemd/embedding.service /etc/systemd/system/
   sudo cp mcp_tools/list_rls_precedents/systemd/list_rls_precedents.service /etc/systemd/system/
   sudo cp mcp_tools/get_policy_snippets/systemd/get_policy_snippets.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable embedding-service list_rls_precedents get_policy_snippets
   sudo systemctl start embedding-service
   sleep 2  # let embedding-service warm Ollama keep_alive
   sudo systemctl start list_rls_precedents get_policy_snippets
   ```

4. Verify each unit:

   ```bash
   curl -s http://127.0.0.1:30201/health | jq .
   # Expected: {"status": "healthy", "ollama_reachable": true, "breaker_state": "closed", ...}

   curl -s http://127.0.0.1:30103/health | jq .  # L3 tool /health from build_tool_app
   curl -s http://127.0.0.1:30104/health | jq .  # L4 tool /health from build_tool_app
   ```

5. Backfill embeddings for existing scraped chunks (Plan A's scraper didn't
   embed; embeddings populate on-demand for v0.2.1a — or run a one-shot
   backfill if retrieval recall is poor):

   ```bash
   .venv/bin/python -m services.embedding.backfill --batch-size 50
   # (Plan A may have included this script; if not, defer to v0.2.1b.)
   ```

## Smoke test

End-to-end retrieval from outside:

```bash
curl -sS -X POST http://bcc-ap-llm01:8443/api/mcp/list_rls_precedents \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $RLS_APEX_TOKEN" \
  -d '{"matter_type": "permit_or_zoning", "legal_question": "vested rights LDC amendment"}' \
  | jq .
```

Expected: at least one `hits[]` entry, including one of the 18 stubs.

Then check Power BI inflow:

```bash
curl -s http://bcc-ap-llm01:8000/health/sidecar | jq .
# breaker_state must be "closed" — events draining cleanly to manatee-ai-roi FastAPI
```

## Rollback

If retrieval is broken (no hits, 5xx loop, breaker stuck open):

1. Stop the new units:
   ```bash
   sudo systemctl stop list_rls_precedents get_policy_snippets embedding-service
   ```
2. Revert the migration:
   ```bash
   .venv/bin/alembic downgrade -1
   ```
3. Revert to last green commit:
   ```bash
   git checkout <last-green-tag>
   ```

The v0.2.0b feature surface continues to function without Plan C.
```

- [ ] **Step 2: Commit**

```bash
git add docs/runbooks/2026-05-12-v0_2_1a-stream-c-deploy-notes.md
git commit -m "$(cat <<'EOF'
docs(runbook): Stream C deploy notes for bcc-ap-llm01

Three new systemd units (embedding-service, list_rls_precedents,
get_policy_snippets) + one alembic migration. Preconditions, deploy
sequence, smoke-test commands, and rollback procedure for the operator.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 3: Run final full suite as the close-the-loop check**

```bash
.venv/bin/python -m pytest -q
```

Expected: 162 passed.

- [ ] **Step 4: Push to origin**

```bash
git push origin feat/v0.2.0a-backend
```

- [ ] **Step 5: Tag a release marker**

```bash
git tag -a v0.2.1a-stream-c-rc1 -m "Stream C retrieval engine — release candidate 1"
git push origin v0.2.1a-stream-c-rc1
```

---

## Self-Review

**Spec coverage check:**

| Spec section | Task |
|---|---|
| §3.3 `embedding vector(1024)` + HNSW | Task 1 |
| §6.0 BM25 naming note (`ts_rank_cd`) | Task 5 SQL |
| §6.1 HybridRetriever (BM25 + ANN + RRF k=60) | Task 5 |
| §6.2 Point-in-time queries (valid_at) | Task 5 (SQL + tests) |
| §6.3 L3 `list_rls_precedents` | Task 6 |
| §6.4 L4 `get_policy_snippets` + `procedure_corpus_pending` | Task 7 |
| §6.5 ROI emit on every retrieval | Tasks 6, 7 (per-tool emits) |
| §8 backend wiring — `_lib/corpus/`, L3, L4, embedding-service | Tasks 2-7 |
| §9.1 W8 unit roster (30103, 30104, 30201) | Tasks 6, 7, 3 (systemd units expose `/health`) |
| §10 testing — retriever unit, RRF, point-in-time | Task 5 |
| §10 testing — MCP tools | Tasks 6, 7 |
| §10 testing — embedding-service unit + breaker | Task 3 |
| §10 testing — integration breaker fallback | Task 9 |
| §10 testing — retrieval through gateway integration | Task 10 |
| §13 NFRs — ≤200ms p95 retrieval | Implicit (BM25 ≤50ms + ANN ≤100ms + RRF ≤50ms; no test gate, smoke-checked at deploy) |
| §15 W3 RRF correctness test | Task 5 (`test_rrf_merge_is_correct`) |
| §15 E1 emit compliance for L3/L4 | Task 8 |
| §15 E2 embedding-breaker fallback | Task 9 |
| ADR-001 hybrid retrieval | Task 5 |
| ADR-002 versioned corpus + valid_at | Task 5 |
| ADR-005 mxbai-embed-large 1024-dim via Ollama | Tasks 1 + 3 |
| ADR-006 library-in-each-tool | Architecture (Tasks 2, 4, 5 share library; Tasks 6, 7 import) |

No gaps identified.

**Placeholder scan:** Searched plan for "TBD", "TODO", "fill in", "implement later", "similar to" — none present.

**Type consistency:** Verified `Hit` model used identically across tests in Tasks 2, 5, 6, 7, 8, 9, 10. `EmbeddingUnavailable` referenced consistently in Tasks 4, 5, 9. `HybridRetriever.search` signature `(query, k, source_filter, valid_at)` matches across all callers. `_EMIT_DEFAULTS` constant pattern matches the ROI emit hardening doc (Tasks 6, 7).

**Risk callouts identified during self-review:**

- **Task 1 pgvector precondition:** the spec assumes pgvector is installed before any alembic migration runs. Plan A's migration tries `CREATE EXTENSION IF NOT EXISTS vector;` but if pgvector isn't installed at the OS level the CREATE EXTENSION fails. Plan A's migration silently no-ops on the column type (it uses `ARRAY(Float)`), so Plan A passes even without pgvector. Plan C's migration is where pgvector failure surfaces. Task 1 step 3 calls this out explicitly.

- **Task 10 gateway dispatch path:** assumes the gateway uses `/api/mcp/{tool}` for MCP dispatch. If the v0.2.0a gateway uses a different route convention, the smoke test URL must change. Step 3 includes the grep command to discover it.

- **Task 9 schema audit (`rag_hit` event-kind):** Plan A's documentation didn't explicitly state whether the v0.2.0a schema already had `rag_hit` in its event-kind enum. Step 1 audits; step 1 instruction adds it if missing.

- **Task 10 fixture metadata fix:** the seed fixture in Task 5 didn't include matter_type metadata on the internal_opinion stubs because Task 5's retriever tests don't need it. Task 10 retroactively patches the fixture. Acceptable — the metadata change doesn't regress retriever tests because they don't filter on matter_type.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-11-v0_2_1a-stream-c-retrieval.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Per the rls-apex pattern used for Plans A and B, this works well for Stream C's 11 tasks because each task is self-contained with clear acceptance.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
