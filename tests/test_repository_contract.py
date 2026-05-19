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
