"""P1 Task 11 — /api/rls/submit genesis endpoint.

Uses the conftest `client` fixture, which overrides `current_user` so the
authenticated endpoint works without a real Entra token. (The module-level
`DEV_MODE` in main.py is frozen at import, so a `monkeypatch.setenv` on
DEV_AUTH_BYPASS cannot flip the auth path — the dependency override is the
codebase's established pattern for this.) No lifespan runs under
ASGITransport, so `app.state.db_pool` is unset and `get_repo` selects
`MockRepo`.
"""
import pytest


@pytest.mark.asyncio
async def test_submit_creates_rls_returns_receipt(client):
    body = {"rlsPayload": {"subject": "Lease", "department": "Legal",
            "type": "general_advisory"}, "idempotency_key": "abc"}
    r = await client.post("/api/rls/submit", json=body)
    assert r.status_code == 200
    j = r.json()
    assert j["rls_id"].startswith("RLS-")
    assert len(j["lineage_receipt"]["this_hash"]) == 64
    assert j["lineage_receipt"]["sequence"] == 1


@pytest.mark.asyncio
async def test_submit_idempotent_same_key(client):
    body = {"rlsPayload": {"subject": "X", "department": "Legal",
            "type": "general_advisory"}, "idempotency_key": "dup9"}
    a = (await client.post("/api/rls/submit", json=body)).json()
    b = (await client.post("/api/rls/submit", json=body)).json()
    assert a["rls_id"] == b["rls_id"]


@pytest.mark.asyncio
async def test_submit_missing_idempotency_key_400(client):
    r = await client.post("/api/rls/submit", json={"rlsPayload": {"subject": "Y"}})
    assert r.status_code == 400
