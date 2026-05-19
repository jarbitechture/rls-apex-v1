from __future__ import annotations

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
