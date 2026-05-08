"""POST /api/intake takes free-text and returns an assembled rlsPayload (spec §5.1)."""
import pytest


@pytest.mark.asyncio
async def test_intake_returns_classified_rls_payload(client):
    response = await client.post("/api/intake", json={
        "text": "Need legal review on a permit denial for parcel 12345"
    })
    assert response.status_code == 200
    body = response.json()
    assert body["classification"]["type"] == "permit_or_zoning"
    assert "rlsPayload" in body
    assert "subject" in body["rlsPayload"]
    assert len(body["rlsPayload"]["subject"]) <= 50


@pytest.mark.asyncio
async def test_intake_validates_input(client):
    response = await client.post("/api/intake", json={"text": ""})
    assert response.status_code == 422  # pydantic rejects empty text


@pytest.mark.asyncio
async def test_intake_returns_general_advisory_on_unknown(client):
    response = await client.post("/api/intake", json={
        "text": "Just a random short note that doesn't match patterns"
    })
    assert response.status_code == 200
    body = response.json()
    assert body["classification"]["type"] == "general_advisory"
