"""P1 Task 12 — read-path migration: /api/cao/brief served via get_repo.

Uses the conftest `client` fixture (overrides current_user; no lifespan →
no app.state.db_pool → get_repo selects MockRepo). The same MockRepo
singleton backs both the submit POST and the brief GET via get_repo's
pool-keyed memo, so a just-submitted record is visible to the brief read.
"""
import pytest


@pytest.mark.asyncio
async def test_cao_brief_served_from_repo_after_submit(client):
    sub = (await client.post("/api/rls/submit", json={
        "rlsPayload": {"subject": "Brief me", "department": "Legal",
                       "type": "general_advisory"},
        "idempotency_key": "rp1"})).json()
    br = await client.get(f"/api/cao/brief?rlsId={sub['rls_id']}")
    assert br.status_code == 200
    assert br.json()["rlsId"] == sub["rls_id"]
    assert "Brief me" in br.json()["summary"][0]


@pytest.mark.asyncio
async def test_cao_brief_unknown_id_falls_back_to_mock_fixture(client):
    """An id the repo doesn't know still returns the legacy v0.2.0b canned
    brief — DEV fixture behaviour is preserved, not broken by the migration."""
    br = await client.get("/api/cao/brief?rlsId=RLS-99-9999")
    assert br.status_code == 200
    assert br.json()["rlsId"] == "RLS-99-9999"
    assert len(br.json()["summary"]) >= 1
