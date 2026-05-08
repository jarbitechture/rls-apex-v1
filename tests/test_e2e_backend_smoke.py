"""End-to-end backend: paste text → intake → validate → check status."""
import pytest


@pytest.mark.asyncio
async def test_full_flow_text_to_validation(client):
    # 1. Intake
    intake = await client.post("/api/intake", json={
        "text": "Need legal review on a permit denial for parcel 12345"
    })
    assert intake.status_code == 200
    payload = intake.json()["rlsPayload"]

    # 2. Validate the assembled payload
    validate = await client.post("/api/validate", json={"rlsPayload": payload})
    assert validate.status_code == 200
    result = validate.json()
    # Mock extractor returns mostly-empty payload → validation has blocking issues
    assert result["blocking"]  # not empty
    assert any(i["code"] == "MISSING_ACCOUNT_KEY" for i in result["blocking"])

    # 3. Health surface present
    health = await client.get("/api/health/breakers")
    assert health.status_code == 200
    assert "breakers" in health.json()
