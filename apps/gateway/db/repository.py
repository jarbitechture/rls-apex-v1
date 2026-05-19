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
