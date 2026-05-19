"""RLS persistence bounded context — the only module that touches _mock or
raw SQL. Spec 2026-05-18-rls-persistence-genesis-design.md §4/§6/§8.
"""
from __future__ import annotations

import datetime as _dt
import json as _json
from typing import Any, Protocol

import asyncpg

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
            async with self._pool.acquire() as c:
                existing = await c.fetchval(
                    "SELECT rls_id FROM audit_event WHERE idempotency_key=$1",
                    idempotency_key)
            return await self.get_rls(existing)
        return await self.get_rls(rls_id)

    async def get_rls(self, rls_id: str) -> RlsRecord | None:
        async with self._pool.acquire() as c:
            row = await c.fetchrow(
                "SELECT rls_id, matter_id, classification, status, type, subject, "
                "department, contact_name, contact_extension, created_at, updated_at, "
                "lineage_head FROM rls WHERE rls_id=$1", rls_id)
        if row is None:
            return None
        return RlsRecord(
            rls_id=row["rls_id"],
            matter_id=row["matter_id"],
            classification=row["classification"],
            status=RlsStatus(row["status"]),
            type=RlsType(row["type"]),
            subject=row["subject"],
            department=row["department"],
            contact_name=row["contact_name"],
            contact_extension=row["contact_extension"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            lineage_head=row["lineage_head"],
        )

    async def get_lineage(self, rls_id: str) -> list[LineageEvent]:
        async with self._pool.acquire() as c:
            rows = await c.fetch(
                "SELECT rls_id, sequence, prev_hash, this_hash, payload "
                "FROM lineage_event WHERE rls_id=$1 ORDER BY sequence",
                rls_id)
        return [
            LineageEvent(
                rls_id=r["rls_id"],
                sequence=r["sequence"],
                prev_hash=r["prev_hash"],
                this_hash=r["this_hash"],
                payload=_json.loads(r["payload"]) if isinstance(r["payload"], str) else dict(r["payload"]),
            )
            for r in rows
        ]

