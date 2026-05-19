# P1 — RLS Persistence + Lineage Genesis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give RLS a real persistence subsystem: an explicit Submit creates a durable `rls` row + genesis `lineage_event` + `audit_event` in one Postgres transaction, behind one repository interface, with a tamper-evident hash chain (DECISION_LOG Lock #20).

**Architecture:** One shared pure module (`lineage.py`) computes the canonical hash chain and the content-digest idempotency key. One repository interface (`repository.py`) with a per-request env-gated backend: `_MockRepo` (in-memory, normalizing adapter — DEV) and `PgRepo` (real Postgres — prod), both calling the same `lineage.py`. The genesis transaction allocates a contiguous per-year `rls_id` via an atomic `id_counter` upsert, fails loud through the existing circuit breaker, and emits ROI post-commit fire-and-forget.

**Tech Stack:** Python 3.12, FastAPI, asyncpg, Alembic, Pydantic v2, pytest + pytest-postgresql (`db_pool` fixture), Lit 3.2.1 + Vitest/jsdom (frontend), `apps/gateway/circuit` breaker.

**Spec:** `docs/superpowers/specs/2026-05-18-rls-persistence-genesis-design.md` (HEAD `ae91085`). Zero open decisions. Lock #20 (canonicalization anchor) accepted; §7 = (b) content-digest key.

**Branch:** `feat/v0.2.0a-backend`. **Test commands:** backend `python -m pytest -q`; frontend `cd apps/web && npx vitest run`.

---

## File Structure

| File | Create/Modify | Responsibility |
|---|---|---|
| `apps/gateway/db/lineage.py` | Create | Pure: `canonical_bytes`, `compute_link`, `verify_chain`, `content_idempotency_key`. No I/O. Lock #20 algorithm. |
| `alembic/versions/<rev>_p1_id_counter.py` | Create | `id_counter(year PK, next_seq)` table. |
| `apps/gateway/db/repository.py` | Create | `Repo` Protocol; `_MockRepo`; `PgRepo`; `get_repo` per-request dependency. |
| `apps/gateway/main.py` | Modify | `/api/rls/submit` genesis endpoint; repoint `/api/cao/brief` + DEV list/get off direct `_mock` via `get_repo`; post-commit ROI. |
| `apps/web/static/components/submit-panel.js` | Modify | Enable Submit; compute content-digest key; POST `/api/rls/submit`. |
| `apps/web/static/core/api.js` | Modify | Add `postSubmit(body)`. |
| `DECISION_LOG.md` | Modify | Locks #21 (genesis-at-submit), #22 (DEV_AUTH_BYPASS-backend), #23 (per-year-counter). |
| `tests/test_lineage.py` | Create | Pure-fn suite (both-backends-irrelevant; lineage is shared). |
| `tests/test_repository_contract.py` | Create | Shape/contract suite parametrized over `_MockRepo` + `PgRepo`. |
| `tests/integration/test_genesis_pg.py` | Create | **PgRepo-only** (real Postgres `db_pool`): atomicity, idempotency, concurrency, breaker. |
| `apps/web/tests/unit/submit-panel.test.js` | Create | Vitest jsdom — enabled button, content-digest key, POST. |

**Test boundary (spec §10, non-negotiable):** shape/contract → both backends (`tests/test_repository_contract.py`). Transaction-isolation/concurrency → **PgRepo real-Postgres only** (`tests/integration/test_genesis_pg.py`); `_MockRepo` cannot reproduce `ON CONFLICT DO UPDATE` row-lock serialization, abort-on-unique-violation, or separate-tx replay — do not assert those on the mock.

**pytest discovery:** never add `tests/integration/__init__.py` or `tests/__init__.py` (shadows real packages — `reference_rls_apex_pytest_discovery`).

---

## Task 1: `id_counter` Alembic migration

**Files:**
- Create: `alembic/versions/p1a1b2c3d4e5_p1_id_counter.py`
- Test: `tests/test_migration_p1_id_counter.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_migration_p1_id_counter.py
import pytest


@pytest.mark.asyncio
async def test_id_counter_table_exists_and_constrained(db_pool):
    async with db_pool.acquire() as c:
        cols = await c.fetch(
            "SELECT column_name, data_type, is_nullable "
            "FROM information_schema.columns WHERE table_name='id_counter' "
            "ORDER BY ordinal_position"
        )
    by = {r["column_name"]: r for r in cols}
    assert set(by) == {"year", "next_seq"}
    assert by["year"]["data_type"] == "integer"
    assert by["next_seq"]["is_nullable"] == "NO"
    async with db_pool.acquire() as c:
        # PK on year → duplicate year rejected
        await c.execute("INSERT INTO id_counter (year, next_seq) VALUES (2026, 1)")
        with pytest.raises(Exception):
            await c.execute("INSERT INTO id_counter (year, next_seq) VALUES (2026, 9)")
        # CHECK next_seq >= 1
        with pytest.raises(Exception):
            await c.execute("INSERT INTO id_counter (year, next_seq) VALUES (2027, 0)")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_migration_p1_id_counter.py -q`
Expected: FAIL — relation `id_counter` does not exist.

- [ ] **Step 3: Write the migration**

```python
# alembic/versions/p1a1b2c3d4e5_p1_id_counter.py
"""p1 id_counter table — per-year contiguous RLS number allocation

Revision ID: p1a1b2c3d4e5
Revises: c5f2154f8fb3
Create Date: 2026-05-19

Per DECISION_LOG Lock #23: a per-year counter row, mutated via atomic
INSERT ... ON CONFLICT (year) DO UPDATE ... RETURNING inside the genesis
tx, gives contiguous gap-free official RLS numbers (rollback consumes no
number). Single-row-lock scaling limit documented in the P1 spec §13.
"""
from alembic import op
import sqlalchemy as sa

revision = "p1a1b2c3d4e5"
down_revision = "c5f2154f8fb3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "id_counter",
        sa.Column("year", sa.Integer, primary_key=True),
        sa.Column("next_seq", sa.Integer, nullable=False),
        sa.CheckConstraint("next_seq >= 1", name="id_counter_next_seq_ge_1"),
    )


def downgrade() -> None:
    op.drop_table("id_counter")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_migration_p1_id_counter.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add alembic/versions/p1a1b2c3d4e5_p1_id_counter.py tests/test_migration_p1_id_counter.py
git commit -m "feat(db): P1 id_counter migration (Lock #23 per-year contiguous allocation)"
```

---

## Task 2: `lineage.canonical_bytes` (Lock #20 §5.1)

**Files:**
- Create: `apps/gateway/db/lineage.py`
- Test: `tests/test_lineage.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_lineage.py
import pytest
from apps.gateway.db.lineage import canonical_bytes, CanonicalProfileError


def test_canonical_bytes_is_sorted_compact_utf8():
    out = canonical_bytes({"b": "2", "a": "1", "chain_version": "1"})
    assert out == b'{"a":"1","b":"2","chain_version":"1"}'
    assert isinstance(out, bytes)


def test_canonical_bytes_nfc_normalizes_string_values():
    # "e" + combining acute (NFD)  vs precomposed "é" (NFC) → identical bytes
    nfd = {"k": "é", "chain_version": "1"}
    nfc = {"k": "é", "chain_version": "1"}
    assert canonical_bytes(nfd) == canonical_bytes(nfc)


def test_canonical_bytes_rejects_non_string_and_nested():
    for bad in ({"a": 1}, {"a": 1.0}, {"a": True}, {"a": None}, {"a": {"x": "1"}}, {"a": ["1"]}):
        with pytest.raises(CanonicalProfileError):
            canonical_bytes({**bad, "chain_version": "1"})


def test_canonical_bytes_requires_chain_version():
    with pytest.raises(CanonicalProfileError):
        canonical_bytes({"a": "1"})


def test_canonical_bytes_escapes_control_chars_no_raw_0x1f():
    out = canonical_bytes({"a": "x\x1fy", "chain_version": "1"})
    assert b"\x1f" not in out
    assert b"\\u001f" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_lineage.py -q`
Expected: FAIL — `apps.gateway.db.lineage` does not exist.

- [ ] **Step 3: Write the implementation**

```python
# apps/gateway/db/lineage.py
"""Lineage tamper-evidence — the legal anchor (DECISION_LOG Lock #20).

Pure functions, no I/O. Spec 2026-05-18-rls-persistence-genesis-design.md
§5.1 (canonical profile, rules 1-6), §5.2 (link), §5.3 (verify), §7 (the
content-digest idempotency key). This algorithm is normative and
self-specified; it is NOT RFC 8785/JCS. Changing it is a chain-breaking,
chain_version-gated event — never edit in place (Lock #20 reversal cost).
"""
from __future__ import annotations

import hashlib
import json
import unicodedata
from typing import Any

CHAIN_VERSION = "1"


class CanonicalProfileError(ValueError):
    """Payload violates the §5.1 strict string-only canonical profile."""


def _assert_profile(payload: dict[str, Any]) -> None:
    if payload.get("chain_version") != CHAIN_VERSION:
        raise CanonicalProfileError(
            f"payload must include chain_version={CHAIN_VERSION!r}"
        )
    for k, v in payload.items():
        if not isinstance(k, str):
            raise CanonicalProfileError(f"non-string key: {k!r}")
        if not isinstance(v, str):
            raise CanonicalProfileError(
                f"value for {k!r} is {type(v).__name__}; profile is string-only "
                "(no int/float/bool/None/nested) — flatten or stringify, omit if absent"
            )


def canonical_bytes(payload: dict[str, Any]) -> bytes:
    """§5.1: strict string-only, NFC-normalized, sorted keys, compact, UTF-8.

    Normative algorithm — an auditor reproduces it from Lock #20 + this code.
    """
    _assert_profile(payload)
    norm = {k: unicodedata.normalize("NFC", v) for k, v in payload.items()}
    return json.dumps(
        norm, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_lineage.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/gateway/db/lineage.py tests/test_lineage.py
git commit -m "feat(lineage): canonical_bytes — Lock #20 §5.1 string-only profile"
```

---

## Task 3: `lineage.compute_link` (Lock #20 §5.2)

**Files:**
- Modify: `apps/gateway/db/lineage.py`
- Test: `tests/test_lineage.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_lineage.py
from apps.gateway.db.lineage import compute_link
import hashlib


def test_compute_link_genesis_known_answer():
    payload = {"chain_version": "1", "rls_id": "RLS-26-0001"}
    expected = hashlib.sha256(
        b"GENESIS" + b"\x1f" + b"1" + b"\x1f"
        + b'{"chain_version":"1","rls_id":"RLS-26-0001"}'
    ).hexdigest()
    got = compute_link(None, 1, payload)
    assert got == expected
    assert len(got) == 64 and got == got.lower()


def test_compute_link_non_genesis_uses_prev_hash():
    prev = "a" * 64
    payload = {"chain_version": "1", "x": "y"}
    expected = hashlib.sha256(
        prev.encode("ascii") + b"\x1f" + b"2" + b"\x1f"
        + b'{"chain_version":"1","x":"y"}'
    ).hexdigest()
    assert compute_link(prev, 2, payload) == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_lineage.py -k compute_link -q`
Expected: FAIL — `compute_link` not defined.

- [ ] **Step 3: Write the implementation**

```python
# append to apps/gateway/db/lineage.py
def compute_link(prev_hash: str | None, sequence: int, payload: dict[str, Any]) -> str:
    """§5.2 link. Genesis = prev_hash None → literal b"GENESIS" sentinel.

    sha256( (prev_hash or "GENESIS").ascii + 0x1F + str(seq).ascii + 0x1F
            + canonical_bytes(payload) ).hexdigest()  — lowercase 64-hex.
    """
    head = (prev_hash or "GENESIS").encode("ascii")
    return hashlib.sha256(
        head
        + b"\x1f"
        + str(sequence).encode("ascii")
        + b"\x1f"
        + canonical_bytes(payload)
    ).hexdigest()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_lineage.py -k compute_link -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/gateway/db/lineage.py tests/test_lineage.py
git commit -m "feat(lineage): compute_link — Lock #20 §5.2 exact byte construction"
```

---

## Task 4: `lineage.verify_chain` (§5.3)

**Files:**
- Modify: `apps/gateway/db/lineage.py`
- Test: `tests/test_lineage.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_lineage.py
from apps.gateway.db.lineage import verify_chain
from dataclasses import dataclass


@dataclass
class _Ev:
    sequence: int
    prev_hash: str | None
    this_hash: str
    payload: dict


def _mk(seq, prev):
    p = {"chain_version": "1", "n": str(seq)}
    return _Ev(seq, prev, compute_link(prev, seq, p), p)


def test_verify_chain_accepts_valid_chain():
    g = _mk(1, None)
    e2 = _mk(2, g.this_hash)
    assert verify_chain([g, e2]) is True


def test_verify_chain_rejects_tamper_reorder_and_missing_genesis():
    g = _mk(1, None)
    e2 = _mk(2, g.this_hash)
    tampered = _Ev(2, g.this_hash, e2.this_hash, {"chain_version": "1", "n": "X"})
    assert verify_chain([g, tampered]) is False           # payload tampered
    assert verify_chain([e2, g]) is False                  # reordered
    assert verify_chain([_mk(2, g.this_hash)]) is False    # no genesis (seq!=1)
    broken = _Ev(2, "f" * 64, e2.this_hash, e2.payload)
    assert verify_chain([g, broken]) is False              # broken prev link
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_lineage.py -k verify_chain -q`
Expected: FAIL — `verify_chain` not defined.

- [ ] **Step 3: Write the implementation**

```python
# append to apps/gateway/db/lineage.py
def verify_chain(events: list) -> bool:
    """§5.3: ordered events for one rls_id. Returns False on any failure.

    Each event needs attributes: sequence:int, prev_hash:str|None,
    this_hash:str, payload:dict.
    """
    if not events:
        return False
    for i, ev in enumerate(events):
        expected_seq = i + 1
        if ev.sequence != expected_seq:
            return False
        prev = None if i == 0 else events[i - 1].this_hash
        if ev.prev_hash != prev:
            return False
        if compute_link(ev.prev_hash, ev.sequence, ev.payload) != ev.this_hash:
            return False
    return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_lineage.py -k verify_chain -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/gateway/db/lineage.py tests/test_lineage.py
git commit -m "feat(lineage): verify_chain — Lock #20 §5.3 tamper-evidence contract"
```

---

## Task 5: `lineage.content_idempotency_key` (spec §7 = (b))

**Files:**
- Modify: `apps/gateway/db/lineage.py`
- Test: `tests/test_lineage.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_lineage.py
from apps.gateway.db.lineage import content_idempotency_key


def test_idem_key_is_stable_for_same_content_order_independent():
    a = {"subject": "Lease X", "department": "Legal", "legal_question": "Q?"}
    b = {"legal_question": "Q?", "department": "Legal", "subject": "Lease X"}
    assert content_idempotency_key(a) == content_idempotency_key(b)
    assert len(content_idempotency_key(a)) == 64


def test_idem_key_changes_on_material_edit():
    a = {"subject": "Lease X", "department": "Legal"}
    b = {"subject": "Lease Y", "department": "Legal"}
    assert content_idempotency_key(a) != content_idempotency_key(b)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_lineage.py -k idem -q`
Expected: FAIL — `content_idempotency_key` not defined.

- [ ] **Step 3: Write the implementation**

```python
# append to apps/gateway/db/lineage.py
def content_idempotency_key(rls_payload: dict[str, Any]) -> str:
    """§7(b): deterministic digest of the submitted draft content.

    Stringifies every value (the §5.1 profile is string-only), then hashes
    the canonical bytes. Content-stable by construction — same draft yields
    the same key across refresh / new session / lost-response retry, with
    no server state. The server treats this as OPAQUE (it never recomputes
    or trusts it; UNIQUE(idempotency_key) is the sole enforcement).
    """
    flat = {
        k: ("" if v is None else v if isinstance(v, str) else json.dumps(
            v, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
        for k, v in rls_payload.items()
    }
    flat["chain_version"] = CHAIN_VERSION
    return hashlib.sha256(canonical_bytes(flat)).hexdigest()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_lineage.py -q`
Expected: PASS (all lineage tests).

- [ ] **Step 5: Commit**

```bash
git add apps/gateway/db/lineage.py tests/test_lineage.py
git commit -m "feat(lineage): content_idempotency_key — spec §7(b) content-digest"
```

---

## Task 6: Repository interface + `_MockRepo`

**Files:**
- Create: `apps/gateway/db/repository.py`
- Test: `tests/test_repository_contract.py`

- [ ] **Step 1: Write the failing test (shape/contract — `_MockRepo` only here; PgRepo added Task 12)**

```python
# tests/test_repository_contract.py
import pytest
from apps.gateway.db.repository import MockRepo
from apps.gateway.db.models import RlsRecord, RlsStatus

PAYLOAD = {
    "subject": "Lease dispute", "department": "Legal",
    "contact_name": "A. Cohen", "contact_extension": "x4821",
    "type": "general_advisory", "legal_question": "May we terminate?",
}
ACTOR = {"actor_id": "pilot@manatee", "actor_role": "requester"}


@pytest.mark.asyncio
async def test_mockrepo_create_then_get_roundtrip():
    repo = MockRepo()
    rec = await repo.create_rls(PAYLOAD, actor=ACTOR, idempotency_key="k1")
    assert isinstance(rec, RlsRecord)
    assert rec.status == RlsStatus.READY_FOR_CAO
    assert rec.rls_id.startswith("RLS-")
    assert len(rec.lineage_head) == 64
    again = await repo.get_rls(rec.rls_id)
    assert again is not None and again.rls_id == rec.rls_id


@pytest.mark.asyncio
async def test_mockrepo_idempotent_replay_same_key():
    repo = MockRepo()
    a = await repo.create_rls(PAYLOAD, actor=ACTOR, idempotency_key="dup")
    b = await repo.create_rls(PAYLOAD, actor=ACTOR, idempotency_key="dup")
    assert a.rls_id == b.rls_id
    assert len(await repo.list_for_cao()) == 1


@pytest.mark.asyncio
async def test_mockrepo_get_lineage_genesis_verifies():
    from apps.gateway.db.lineage import verify_chain
    repo = MockRepo()
    rec = await repo.create_rls(PAYLOAD, actor=ACTOR, idempotency_key="k2")
    chain = await repo.get_lineage(rec.rls_id)
    assert len(chain) == 1 and chain[0].sequence == 1 and chain[0].prev_hash is None
    assert chain[0].this_hash == rec.lineage_head
    assert verify_chain(chain) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_repository_contract.py -q`
Expected: FAIL — `apps.gateway.db.repository` does not exist.

- [ ] **Step 3: Write the implementation**

```python
# apps/gateway/db/repository.py
"""RLS persistence bounded context — the only module that touches _mock or
raw SQL. Spec 2026-05-18-rls-persistence-genesis-design.md §4/§6/§8.
"""
from __future__ import annotations

import datetime as _dt
from typing import Any, Protocol

from apps.gateway.db.lineage import CHAIN_VERSION, compute_link, verify_chain  # noqa: F401
from apps.gateway.db.models import LineageEvent, RlsRecord, RlsStatus, RlsType


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _genesis_payload(rls_id: str, p: dict[str, Any], actor_id: str, ts: str) -> dict:
    """§6 step 3: string-only canonical snapshot, authn provenance in-hash."""
    return {
        "chain_version": CHAIN_VERSION,
        "rls_id": rls_id,
        "type": str(p.get("type") or ""),
        "subject": str(p.get("subject") or ""),
        "department": str(p.get("department") or ""),
        "contact_name": str(p.get("contact_name") or ""),
        "contact_extension": str(p.get("contact_extension") or ""),
        "classification": str(p.get("classification") or "confidential"),
        "actor_id": actor_id,
        "authn": "pilot_bypass",
        "ts": ts,
    }


class Repo(Protocol):
    async def create_rls(self, payload: dict, *, actor: dict, idempotency_key: str) -> RlsRecord: ...
    async def get_rls(self, rls_id: str) -> RlsRecord | None: ...
    async def list_for_cao(self, *, status: RlsStatus = RlsStatus.READY_FOR_CAO) -> list[RlsRecord]: ...
    async def get_brief(self, rls_id: str) -> dict | None: ...
    async def get_lineage(self, rls_id: str) -> list[LineageEvent]: ...


class MockRepo:
    """In-memory normalizing adapter (DEV). Uses the SAME lineage.py as
    PgRepo, an in-memory per-year counter, and an idempotency map. NOT a
    passthrough — returns strict RlsRecord/LineageEvent."""

    def __init__(self) -> None:
        self._rows: dict[str, RlsRecord] = {}
        self._chains: dict[str, list[LineageEvent]] = {}
        self._counter: dict[int, int] = {}
        self._idem: dict[str, str] = {}

    async def create_rls(self, payload: dict, *, actor: dict, idempotency_key: str) -> RlsRecord:
        if idempotency_key in self._idem:                       # replay
            return self._rows[self._idem[idempotency_key]]
        yr = _dt.datetime.now(_dt.timezone.utc).year
        seq = self._counter.get(yr, 0) + 1
        self._counter[yr] = seq
        rls_id = f"RLS-{yr % 100:02d}-{seq:04d}"
        ts = _now_iso()
        actor_id = str(actor.get("actor_id") or "pilot_principal")
        gp = _genesis_payload(rls_id, payload, actor_id, ts)
        this_hash = compute_link(None, 1, gp)
        rec = RlsRecord(
            rls_id=rls_id, matter_id=None,
            classification=gp["classification"],
            status=RlsStatus.READY_FOR_CAO,
            type=RlsType(gp["type"]) if gp["type"] else RlsType.GENERAL_ADVISORY,
            subject=gp["subject"][:240], department=gp["department"],
            contact_name=gp["contact_name"] or "—",
            contact_extension=gp["contact_extension"] or "—",
            created_at=_dt.datetime.now(_dt.timezone.utc),
            updated_at=_dt.datetime.now(_dt.timezone.utc),
            lineage_head=this_hash,
        )
        self._rows[rls_id] = rec
        self._chains[rls_id] = [LineageEvent(
            rls_id=rls_id, sequence=1, prev_hash=None,
            this_hash=this_hash, payload=gp)]
        self._idem[idempotency_key] = rls_id
        return rec

    async def get_rls(self, rls_id: str) -> RlsRecord | None:
        return self._rows.get(rls_id)

    async def list_for_cao(self, *, status: RlsStatus = RlsStatus.READY_FOR_CAO) -> list[RlsRecord]:
        return [r for r in self._rows.values() if r.status == status]

    async def get_brief(self, rls_id: str) -> dict | None:
        r = self._rows.get(rls_id)
        if r is None:
            return None
        return {"rlsId": r.rls_id, "summary": [r.subject], "keyFacts": [],
                "risk": "", "suggestedNextSteps": []}

    async def get_lineage(self, rls_id: str) -> list[LineageEvent]:
        return list(self._chains.get(rls_id, []))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_repository_contract.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/gateway/db/repository.py tests/test_repository_contract.py
git commit -m "feat(db): repository interface + MockRepo normalizing adapter (§4/§8)"
```

---

## Task 7: `PgRepo.create_rls` genesis transaction (PgRepo-only, real Postgres)

**Files:**
- Modify: `apps/gateway/db/repository.py`
- Test: `tests/integration/test_genesis_pg.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_genesis_pg.py   (NO tests/integration/__init__.py)
import pytest
from apps.gateway.db.repository import PgRepo
from apps.gateway.db.lineage import verify_chain
from apps.gateway.db.models import RlsStatus

PAYLOAD = {"subject": "Lease", "department": "Legal", "contact_name": "A",
           "contact_extension": "x1", "type": "general_advisory"}
ACTOR = {"actor_id": "pilot@manatee", "actor_role": "requester"}


@pytest.mark.asyncio
async def test_pg_genesis_creates_row_chain_and_contiguous_ids(db_pool):
    repo = PgRepo(db_pool)
    r1 = await repo.create_rls(PAYLOAD, actor=ACTOR, idempotency_key="a")
    r2 = await repo.create_rls(PAYLOAD, actor=ACTOR, idempotency_key="b")
    assert r1.status == RlsStatus.READY_FOR_CAO
    n1 = int(r1.rls_id.rsplit("-", 1)[1])
    n2 = int(r2.rls_id.rsplit("-", 1)[1])
    assert n2 == n1 + 1                                  # contiguous
    chain = await repo.get_lineage(r1.rls_id)
    assert len(chain) == 1 and chain[0].prev_hash is None
    assert chain[0].this_hash == r1.lineage_head
    assert verify_chain(chain) is True
    async with db_pool.acquire() as c:
        row = await c.fetchrow("SELECT status, lineage_head FROM rls WHERE rls_id=$1", r1.rls_id)
        assert row["status"] == "ReadyForCAO"
        assert row["lineage_head"] == r1.lineage_head
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_genesis_pg.py -q`
Expected: FAIL — `PgRepo` not defined.

- [ ] **Step 3: Write the implementation**

```python
# append to apps/gateway/db/repository.py
import json as _json

import asyncpg


_ID_UPSERT = (
    "INSERT INTO id_counter (year, next_seq) VALUES ($1, 2) "
    "ON CONFLICT (year) DO UPDATE SET next_seq = id_counter.next_seq + 1 "
    "RETURNING next_seq - 1 AS seq"
)


class PgRepo:
    """Real Postgres. Genesis = one tx: atomic id mint → audit_event →
    rls + lineage_event. §6."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create_rls(self, payload: dict, *, actor: dict, idempotency_key: str) -> RlsRecord:
        yr = _dt.datetime.now(_dt.timezone.utc).year
        ts = _now_iso()
        actor_id = str(actor.get("actor_id") or "pilot_principal")
        actor_role = str(actor.get("actor_role") or "requester")
        envelope = _json.dumps(
            {"rlsPayload": payload, "actor_id": actor_id, "ts": ts,
             "idempotency_key": idempotency_key})
        try:
            async with self._pool.acquire() as c, c.transaction():
                seq = await c.fetchval(_ID_UPSERT, yr)
                rls_id = f"RLS-{yr % 100:02d}-{seq:04d}"
                await c.execute(
                    "INSERT INTO audit_event "
                    "(rls_id, actor_id, actor_role, action, payload, idempotency_key) "
                    "VALUES ($1,$2,$3,'rls.create',$4::jsonb,$5)",
                    rls_id, actor_id, actor_role, envelope, idempotency_key)
                gp = _genesis_payload(rls_id, payload, actor_id, ts)
                this_hash = compute_link(None, 1, gp)
                now = _dt.datetime.now(_dt.timezone.utc)
                await c.execute(
                    "INSERT INTO rls (rls_id, matter_id, classification, status, "
                    "type, subject, department, contact_name, contact_extension, "
                    "payload, created_at, updated_at, lineage_head) "
                    "VALUES ($1,NULL,$2,'ReadyForCAO',$3,$4,$5,$6,$7,$8::jsonb,$9,$9,$10)",
                    rls_id, gp["classification"],
                    gp["type"] or "general_advisory",
                    gp["subject"][:240], gp["department"],
                    gp["contact_name"] or "—", gp["contact_extension"] or "—",
                    _json.dumps(payload), now, this_hash)
                await c.execute(
                    "INSERT INTO lineage_event "
                    "(rls_id, sequence, prev_hash, this_hash, payload) "
                    "VALUES ($1,1,NULL,$2,$3::jsonb)",
                    rls_id, this_hash, _json.dumps(gp))
        except asyncpg.UniqueViolationError:
            # idempotency replay — separate tx (the aborted one rolled back,
            # incl. its id_counter bump; no number consumed)
            async with self._pool.acquire() as c:
                existing = await c.fetchval(
                    "SELECT rls_id FROM audit_event WHERE idempotency_key=$1",
                    idempotency_key)
            return await self.get_rls(existing)
        return await self.get_rls(rls_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/integration/test_genesis_pg.py -q`
Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add apps/gateway/db/repository.py tests/integration/test_genesis_pg.py
git commit -m "feat(db): PgRepo.create_rls genesis tx (§6 atomic id+audit+rls+lineage)"
```

---

## Task 8: `PgRepo` reads + idempotency replay (real Postgres)

**Files:**
- Modify: `apps/gateway/db/repository.py`
- Test: `tests/integration/test_genesis_pg.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/integration/test_genesis_pg.py
@pytest.mark.asyncio
async def test_pg_idempotent_replay_returns_same_row_no_extra(db_pool):
    repo = PgRepo(db_pool)
    a = await repo.create_rls(PAYLOAD, actor=ACTOR, idempotency_key="same")
    b = await repo.create_rls(PAYLOAD, actor=ACTOR, idempotency_key="same")
    assert a.rls_id == b.rls_id
    async with db_pool.acquire() as c:
        n = await c.fetchval("SELECT count(*) FROM rls")
        gaps = await c.fetch("SELECT rls_id FROM rls ORDER BY rls_id")
    assert n == 1
    assert len(gaps) == 1


@pytest.mark.asyncio
async def test_pg_get_and_list_and_brief(db_pool):
    repo = PgRepo(db_pool)
    r = await repo.create_rls(PAYLOAD, actor=ACTOR, idempotency_key="g1")
    assert (await repo.get_rls(r.rls_id)).rls_id == r.rls_id
    assert await repo.get_rls("RLS-99-9999") is None
    lst = await repo.list_for_cao()
    assert [x.rls_id for x in lst] == [r.rls_id]
    brief = await repo.get_brief(r.rls_id)
    assert brief["rlsId"] == r.rls_id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_genesis_pg.py -k "replay or get_and_list" -q`
Expected: FAIL — `get_rls`/`list_for_cao`/`get_brief` not defined on `PgRepo`.

- [ ] **Step 3: Write the implementation**

```python
# append to apps/gateway/db/repository.py  (methods on PgRepo)
    async def _row_to_record(self, row) -> RlsRecord:
        return RlsRecord(
            rls_id=row["rls_id"], matter_id=row["matter_id"],
            classification=row["classification"], status=row["status"],
            type=row["type"], subject=row["subject"],
            department=row["department"], contact_name=row["contact_name"],
            contact_extension=row["contact_extension"],
            created_at=row["created_at"], updated_at=row["updated_at"],
            lineage_head=row["lineage_head"])

    async def get_rls(self, rls_id: str) -> RlsRecord | None:
        async with self._pool.acquire() as c:
            row = await c.fetchrow("SELECT * FROM rls WHERE rls_id=$1", rls_id)
        return await self._row_to_record(row) if row else None

    async def list_for_cao(self, *, status: RlsStatus = RlsStatus.READY_FOR_CAO) -> list[RlsRecord]:
        async with self._pool.acquire() as c:
            rows = await c.fetch(
                "SELECT * FROM rls WHERE status=$1 ORDER BY rls_id",
                status.value if hasattr(status, "value") else status)
        return [await self._row_to_record(r) for r in rows]

    async def get_brief(self, rls_id: str) -> dict | None:
        r = await self.get_rls(rls_id)
        if r is None:
            return None
        return {"rlsId": r.rls_id, "summary": [r.subject], "keyFacts": [],
                "risk": "", "suggestedNextSteps": []}

    async def get_lineage(self, rls_id: str) -> list[LineageEvent]:
        async with self._pool.acquire() as c:
            rows = await c.fetch(
                "SELECT rls_id, sequence, prev_hash, this_hash, payload "
                "FROM lineage_event WHERE rls_id=$1 ORDER BY sequence", rls_id)
        return [LineageEvent(rls_id=r["rls_id"], sequence=r["sequence"],
                             prev_hash=r["prev_hash"], this_hash=r["this_hash"],
                             payload=_json.loads(r["payload"])) for r in rows]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/integration/test_genesis_pg.py -q`
Expected: PASS (all genesis-pg tests).

- [ ] **Step 5: Commit**

```bash
git add apps/gateway/db/repository.py tests/integration/test_genesis_pg.py
git commit -m "feat(db): PgRepo reads + idempotency replay (separate-tx, no gap)"
```

---

## Task 9: Fail-loud breaker wrap on the genesis write

**Files:**
- Modify: `apps/gateway/db/repository.py`
- Test: `tests/integration/test_genesis_pg.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/integration/test_genesis_pg.py
from apps.gateway.circuit import BreakerOpenError


@pytest.mark.asyncio
async def test_pg_breaker_open_fails_loud_no_partial_write(db_pool):
    repo = PgRepo(db_pool)
    repo._breaker.force_open()  # test hook (Step 3)
    with pytest.raises(BreakerOpenError):
        await repo.create_rls(PAYLOAD, actor=ACTOR, idempotency_key="x")
    async with db_pool.acquire() as c:
        assert await c.fetchval("SELECT count(*) FROM rls") == 0
        assert await c.fetchval("SELECT count(*) FROM lineage_event") == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_genesis_pg.py -k breaker -q`
Expected: FAIL — `_breaker` not defined / no `force_open`.

- [ ] **Step 3: Write the implementation**

Wrap the genesis tx body in the existing breaker. In `PgRepo.__init__` add:

```python
        from apps.gateway.circuit import CircuitBreaker
        self._breaker = CircuitBreaker(name="rls_pg_write", fail_max=5, reset_timeout=30.0)
```

Refactor `create_rls`: move the `async with self._pool.acquire() as c, c.transaction(): …` block into a local coroutine `async def _genesis(): … return rls_id` and call it through the breaker — the breaker is **fail-loud**: `BreakerOpenError` propagates (no fallback), the gateway maps it to 503 (Task 11).

```python
        async def _genesis() -> str:
            async with self._pool.acquire() as c, c.transaction():
                # ... existing steps (id upsert → audit_event → rls → lineage_event) ...
                return rls_id
        try:
            rls_id = await self._breaker.call(_genesis)
        except asyncpg.UniqueViolationError:
            async with self._pool.acquire() as c:
                existing = await c.fetchval(
                    "SELECT rls_id FROM audit_event WHERE idempotency_key=$1",
                    idempotency_key)
            return await self.get_rls(existing)
        return await self.get_rls(rls_id)
```

If `apps/gateway/circuit.CircuitBreaker` has no `force_open`, add a minimal test-only method to `apps/gateway/circuit/breaker.py`:

```python
    def force_open(self) -> None:
        """Test hook: trip the breaker open immediately."""
        self._state = BreakerState.OPEN
        self._opened_at = self._clock()
```
(Match the existing private attribute names in `breaker.py`; read them first.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/integration/test_genesis_pg.py -q`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add apps/gateway/db/repository.py apps/gateway/circuit/breaker.py tests/integration/test_genesis_pg.py
git commit -m "feat(db): fail-loud breaker on genesis write (Lock #18); no partial write"
```

---

## Task 10: `get_repo` per-request dependency + parametrized contract suite

**Files:**
- Modify: `apps/gateway/db/repository.py`
- Test: `tests/test_repository_contract.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_repository_contract.py
import pytest
from apps.gateway.db.repository import MockRepo, PgRepo, get_repo


@pytest.fixture(params=["mock", "pg"])
async def repo(request, db_pool):
    if request.param == "mock":
        yield MockRepo()
    else:
        yield PgRepo(db_pool)


@pytest.mark.asyncio
async def test_contract_create_get_list_lineage(repo):
    rec = await repo.create_rls(PAYLOAD, actor=ACTOR, idempotency_key="cx")
    assert (await repo.get_rls(rec.rls_id)).rls_id == rec.rls_id
    assert rec in await repo.list_for_cao()
    assert (await repo.get_lineage(rec.rls_id))[0].sequence == 1


def test_get_repo_resolves_per_request_not_module_load(monkeypatch):
    """DEV_AUTH_BYPASS or no pool → MockRepo; resolved at call time."""
    class _Req:
        class app:
            class state:
                db_pool = None
    monkeypatch.setenv("DEV_AUTH_BYPASS", "1")
    assert isinstance(get_repo(_Req()), MockRepo)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_repository_contract.py -k "contract or per_request" -q`
Expected: FAIL — `get_repo` not defined.

- [ ] **Step 3: Write the implementation**

```python
# append to apps/gateway/db/repository.py
import os

_memo: dict[str, object] = {}


def get_repo(request) -> Repo:
    """Per-request backend selection (NEVER at import — the DB pool is
    created in the lifespan, after module load). DEV_AUTH_BYPASS or no
    pool → MockRepo; else PgRepo. Memoized after first real resolution."""
    pool = getattr(getattr(request.app, "state", None), "db_pool", None)
    if os.environ.get("DEV_AUTH_BYPASS") == "1" or pool is None:
        return _memo.setdefault("mock", MockRepo())
    key = "pg"
    if key not in _memo or getattr(_memo[key], "_pool", None) is not pool:
        _memo[key] = PgRepo(pool)
    return _memo[key]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_repository_contract.py -q`
Expected: PASS (contract parametrized over mock+pg; per-request resolution).

- [ ] **Step 5: Commit**

```bash
git add apps/gateway/db/repository.py tests/test_repository_contract.py
git commit -m "feat(db): get_repo per-request env-gated backend + parametrized contract suite"
```

---

## Task 11: `/api/rls/submit` genesis endpoint + post-commit ROI

**Files:**
- Modify: `apps/gateway/main.py` (add endpoint near `/api/intake` ~line 355; helper `emit_roi` is at line 1565; `current_user` at 263)
- Test: `tests/test_submit_endpoint.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_submit_endpoint.py
import pytest
from httpx import AsyncClient, ASGITransport
from apps.gateway.main import app


@pytest.mark.asyncio
async def test_submit_creates_rls_returns_receipt(monkeypatch):
    monkeypatch.setenv("DEV_AUTH_BYPASS", "1")  # MockRepo path
    body = {"rlsPayload": {"subject": "Lease", "department": "Legal",
            "type": "general_advisory"}, "idempotency_key": "abc"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        r = await ac.post("/api/rls/submit", json=body)
    assert r.status_code == 200
    j = r.json()
    assert j["rls_id"].startswith("RLS-")
    assert len(j["lineage_receipt"]["this_hash"]) == 64
    assert j["lineage_receipt"]["sequence"] == 1


@pytest.mark.asyncio
async def test_submit_idempotent_same_key(monkeypatch):
    monkeypatch.setenv("DEV_AUTH_BYPASS", "1")
    body = {"rlsPayload": {"subject": "X", "department": "Legal",
            "type": "general_advisory"}, "idempotency_key": "dup9"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        a = (await ac.post("/api/rls/submit", json=body)).json()
        b = (await ac.post("/api/rls/submit", json=body)).json()
    assert a["rls_id"] == b["rls_id"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_submit_endpoint.py -q`
Expected: FAIL — 404, `/api/rls/submit` not registered.

- [ ] **Step 3: Write the implementation**

```python
# apps/gateway/main.py — add after /api/validate (~line 420), NOT inside the DEV_MODE block
from fastapi import Depends, HTTPException, Request
from apps.gateway.db.repository import get_repo
from apps.gateway.circuit import BreakerOpenError


@app.post("/api/rls/submit", tags=["rls"])
async def api_rls_submit(req: Request, user: dict = Depends(current_user)):
    body = await req.json()
    payload = body.get("rlsPayload") or {}
    idem = body.get("idempotency_key")
    if not idem:
        raise HTTPException(status_code=400, detail="idempotency_key required")
    # Pilot bypass: actor_id is the single configured pilot principal,
    # NOT request free-text (spec §6 step 3 / Lock #19).
    actor = {"actor_id": user.get("upn") or "pilot_principal",
             "actor_role": user.get("role_band", "requester")}
    repo = get_repo(req)
    try:
        rec = await repo.create_rls(payload, actor=actor, idempotency_key=idem)
    except BreakerOpenError:
        raise HTTPException(status_code=503, detail="persistence unavailable")
    chain = await repo.get_lineage(rec.rls_id)
    # Post-commit, fire-and-forget ROI (W1 ordering; never blocks).
    try:
        emit_roi({
            "event_kind": "tool_invocation", "workflow": "rls_apex.submit",
            "tool": "rls_apex", "surface": "other",
            "user_id": user.get("upn", "unknown"),
            "dept": user.get("dept", "DEV"),
            "role_band": user.get("role_band", "professional"),
            "task_type": "data_analysis", "success": True,
        })
    except Exception:
        pass  # ROI never blocks the user action (Rule #18)
    head = chain[-1]
    return {"rls_id": rec.rls_id, "status": rec.status.value,
            "lineage_receipt": {"sequence": head.sequence,
                                "this_hash": head.this_hash}}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_submit_endpoint.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/gateway/main.py tests/test_submit_endpoint.py
git commit -m "feat(gateway): /api/rls/submit genesis endpoint + post-commit ROI (§6.7)"
```

---

## Task 12: Read-path migration — repoint `/api/cao/brief` + DEV list/get off direct `_mock`

**Files:**
- Modify: `apps/gateway/main.py` (`/api/cao/brief` ~line 425; DEV `/api/rls` list ~991, `/api/rls/{rls_id}` ~1006)
- Test: `tests/test_readpath_repo.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_readpath_repo.py
import pytest
from httpx import AsyncClient, ASGITransport
from apps.gateway.main import app


@pytest.mark.asyncio
async def test_cao_brief_served_from_repo_after_submit(monkeypatch):
    monkeypatch.setenv("DEV_AUTH_BYPASS", "1")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        sub = (await ac.post("/api/rls/submit", json={
            "rlsPayload": {"subject": "Brief me", "department": "Legal",
                           "type": "general_advisory"},
            "idempotency_key": "rp1"})).json()
        br = await ac.get(f"/api/cao/brief?rlsId={sub['rls_id']}")
    assert br.status_code == 200
    assert br.json()["rlsId"] == sub["rls_id"]
    assert "Brief me" in br.json()["summary"][0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_readpath_repo.py -q`
Expected: FAIL — brief endpoint still reads `_mock`, doesn't know the just-submitted id.

- [ ] **Step 3: Write the implementation**

In `apps/gateway/main.py`, change `/api/cao/brief` (~line 425) to resolve via `get_repo(req)` and fall back to the existing `_mock` brief only when the repo returns `None` (preserves legacy DEV fixtures):

```python
@app.get("/api/cao/brief", tags=["cao"])
async def api_cao_brief(rlsId: str, req: Request, user: dict = Depends(current_user)):
    repo = get_repo(req)
    brief = await repo.get_brief(rlsId)
    if brief is not None:
        return brief
    # legacy DEV fixture fallback (unchanged behaviour for seeded mock ids)
    ...existing _mock brief body...
```

For the DEV `/api/rls` list (~991) and `/api/rls/{rls_id}` (~1006): keep the legacy `_mock` fixtures but **append** repo-backed rows so a just-submitted record appears:

```python
    @app.get("/api/rls", tags=["mock"])
    async def list_rls(status: str | None = None, req: Request = None):
        repo = get_repo(req)
        live = [r.model_dump() for r in await repo.list_for_cao()]
        ...existing _mock filtered list...
        return {"items": live + items}
```

(Keep `/api/rls/{rls_id}/decision` at ~1041 untouched — that's P2.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_readpath_repo.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/gateway/main.py tests/test_readpath_repo.py
git commit -m "feat(gateway): read-path migration — cao/brief + rls list via get_repo (§8)"
```

---

## Task 13: Frontend — enable submit-panel, content-digest key, POST

**Files:**
- Modify: `apps/web/static/core/api.js`, `apps/web/static/components/submit-panel.js`
- Test: `apps/web/tests/unit/submit-panel.test.js`

- [ ] **Step 1: Write the failing test (Vitest jsdom — NOT happy-dom)**

```javascript
// apps/web/tests/unit/submit-panel.test.js
import { test, expect, vi } from 'vitest';
import '../../static/components/submit-panel.js';
import { createStore } from '../../static/core/store.js';

test('submit button is enabled and POSTs a content-digest key', async () => {
  const calls = [];
  vi.stubGlobal('fetch', vi.fn(async (url, opts) => {
    calls.push({ url, body: JSON.parse(opts.body) });
    return { ok: true, json: async () => ({ rls_id: 'RLS-26-0001',
      lineage_receipt: { sequence: 1, this_hash: 'a'.repeat(64) } }) };
  }));
  const store = createStore();
  store.update('draft', d => { d.rlsPayload = { subject: 'Lease', department: 'Legal' }; });
  const el = document.createElement('submit-panel');
  el.store = store;
  document.body.appendChild(el);
  await el.updateComplete;
  const btn = el.shadowRoot.querySelector('button.submit');
  expect(btn.disabled).toBe(false);
  btn.click();
  await new Promise(r => setTimeout(r, 0));
  expect(calls[0].url).toBe('/api/rls/submit');
  expect(calls[0].body.idempotency_key).toMatch(/^[0-9a-f]{64}$/);
  // stable: same draft → same key
  const k1 = calls[0].body.idempotency_key;
  btn.click(); await new Promise(r => setTimeout(r, 0));
  expect(calls[1].body.idempotency_key).toBe(k1);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/web && npx vitest run tests/unit/submit-panel.test.js`
Expected: FAIL — button still `disabled`, no fetch.

- [ ] **Step 3: Write the implementation**

Add to `apps/web/static/core/api.js`:

```javascript
export async function postSubmit(body) {
  return jsonOrThrow(await fetch('/api/rls/submit', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }));
}
```

Replace `submit-panel.js` render's disabled button + add a content-digest key (Web Crypto SHA-256 over the canonical-sorted payload — mirrors spec §7(b)):

```javascript
import { postSubmit } from '../core/api.js';

// ... inside class:
async _digest(obj) {
  const sorted = {};
  for (const k of Object.keys(obj).sort()) sorted[k] = String(obj[k] ?? '');
  sorted.chain_version = '1';
  const json = JSON.stringify(sorted);
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(json));
  return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, '0')).join('');
}

async _submit() {
  const payload = this.store?.draft.rlsPayload ?? {};
  const idempotency_key = await this._digest(payload);
  const res = await postSubmit({ rlsPayload: payload, idempotency_key });
  this.store.update('draft', d => { d.rlsId = res.rls_id; });
  this._submitted = res;
  this.requestUpdate();
}
```

In `render()`, replace the disabled button with:

```javascript
      <button class="submit" @click=${() => this._submit()}>Submit</button>
```

and remove the `opacity:0.5;cursor:not-allowed` from `button.submit` css. Keep the JSON `<pre>` escape-hatch.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/web && npx vitest run tests/unit/submit-panel.test.js`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/web/static/core/api.js apps/web/static/components/submit-panel.js apps/web/tests/unit/submit-panel.test.js
git commit -m "feat(frontend): enable submit-panel — content-digest key + POST /api/rls/submit"
```

---

## Task 14: Author the 3 plan-task ADR Locks

**Files:**
- Modify: `DECISION_LOG.md` (append-only; current head Lock #20; format `## Lock #N` + Decision/Rationale/Reversal cost)

- [ ] **Step 1: Append Lock #21, #22, #23**

Append to `DECISION_LOG.md` (match the existing terse Lock voice; `---` separator before each):

```markdown

---

## Lock #21 — RLS genesis at explicit Submit (not at intake)

**Decision:** A durable `rls` row + genesis `lineage_event` is created ONLY at explicit Submit (after validate, `blocking==0`), never at `/api/intake`. Drafts stay client-side until Submit.

**Rationale:** Lock #19 privileged-matter hygiene — every half-typed exploratory legal question persisted as a durable privileged row is an ACL/records-retention liability. Intake/validate stay stateless (spec §1/§3).

**Reversal cost:** Low — adding draft autosave later is additive; no chain rewrite.

---

## Lock #22 — `DEV_AUTH_BYPASS` selects the persistence backend

**Decision:** `get_repo` resolves per-request: `DEV_AUTH_BYPASS=="1"` OR no `app.state.db_pool` → `MockRepo`; else `PgRepo`. Auth-bypass and store-choice are deliberately fused on one pilot flag.

**Rationale:** Keeps the no-DB DEV click-through working (standing pilot pattern) without a second flag. Accepted limitation: no real-auth+mock-DB or bypass-auth+real-DB combination (spec §4).

**Reversal cost:** Low — splitting into two env flags later is mechanical.

---

## Lock #23 — Per-year `id_counter` row over a sequence

**Decision:** `rls_id` (`RLS-YY-NNNN`) is allocated from a per-year `id_counter` row via atomic `INSERT … ON CONFLICT (year) DO UPDATE … RETURNING` inside the genesis tx. Calendar year (UTC).

**Rationale:** Contiguous, gap-free official legal numbering (a rolled-back genesis consumes no number); a Postgres SEQUENCE leaks numbers on rollback. Single-row-lock scaling limit (~≤1 submit/s) documented in spec §13 — acceptable at county intake volume.

**Reversal cost:** Medium — moving to hi-lo/sequence allocation later changes the numbering guarantee; needs a documented transition.
```

- [ ] **Step 2: Verify format consistency**

Run: `grep -nE '^## Lock #2[0-3]' DECISION_LOG.md`
Expected: Lock #20, #21, #22, #23 present, in order.

- [ ] **Step 3: Commit**

```bash
git add DECISION_LOG.md
git commit -m "docs(decision): Lock #21/#22/#23 — genesis-at-submit, bypass-backend, per-year-counter"
```

---

## Task 15: Full regression + push

- [ ] **Step 1: Backend suite**

Run: `python -m pytest -q`
Expected: all green (≥ 261 prior + the new P1 tests; 0 failures).

- [ ] **Step 2: Frontend suite**

Run: `cd apps/web && npx vitest run`
Expected: all green (≥ 65 prior + the new submit-panel test).

- [ ] **Step 3: Push**

```bash
git push origin feat/v0.2.0a-backend
```

- [ ] **Step 4: Verify clean + pushed**

Run: `git status -sb | head -1 && git rev-parse --short HEAD`
Expected: in sync with origin, 0 uncommitted.

---

## Self-Review

**1. Spec coverage:** §4 repository+per-request (T6,T10) · §5.1 canonical (T2) · §5.2 link (T3) · §5.3 verify (T4) · §6 genesis tx incl. ts/actor_id/breaker (T7,T9,T11) · §6.2 idempotency replay (T8) · §7(b) content key (T5,T13) · §8 DEV parity + read migration (T6,T12) · §9 id_counter migration (T1) · §10 test boundary (mock/contract = T6,T10; PgRepo-only = T7-T9) · §14 plan-task ADRs (T14). Lock #20 was the accepted precondition (not re-done). No gaps.

**2. Placeholders:** Task 12 step 3 uses `...existing _mock brief body...` / `...existing _mock filtered list...` — these are deliberate "preserve the existing block, wrap it" markers, not unwritten code; the surrounding new code is complete. Task 9 step 3 instructs reading `breaker.py` private attr names before adding `force_open` (the only safe way without inventing names). Acceptable — flagged, not silent.

**3. Type consistency:** `Repo` protocol methods (`create_rls/get_rls/list_for_cao/get_brief/get_lineage`) identical across `MockRepo`/`PgRepo`/`get_repo`/tests. `RlsRecord`/`LineageEvent` fields match `apps/gateway/db/models.py` (verified). `compute_link(prev_hash, sequence, payload)` signature stable T3→T4→T6→T7.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-19-p1-rls-persistence-genesis.md`. Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task, code review between tasks, fast iteration with quality gates. Recommended here: 15 tasks, legal-liability subsystem, several PgRepo-only integration tasks where an independent eye between tasks catches drift.

**2. Inline Execution** — execute tasks in this session via `superpowers:executing-plans`, batch with checkpoints.

Which approach?
