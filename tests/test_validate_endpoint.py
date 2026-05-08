"""POST /api/validate runs validate_rls_structure on rlsPayload (spec §5.4)."""
import pytest


@pytest.mark.asyncio
async def test_validate_returns_blocking_for_incomplete_payload(client):
    response = await client.post("/api/validate", json={
        "rlsPayload": {
            "subject": "Q",
            # missing department, contact_name, contact_extension, account_key
        }
    })
    assert response.status_code == 200
    body = response.json()
    blocking_codes = {issue["code"] for issue in body["blocking"]}
    assert "MISSING_DEPARTMENT" in blocking_codes
    assert "MISSING_ACCOUNT_KEY" in blocking_codes


@pytest.mark.asyncio
async def test_validate_clean_payload_returns_no_blocking(client):
    response = await client.post("/api/validate", json={
        "rlsPayload": {
            "subject": "Vested rights review",
            "department": "Development Services",
            "contact_name": "Jane Planner",
            "contact_extension": "1234",
            "account_key": "010-1234-560",
            "type": "permit_or_zoning",
            "legal_question": "Whether the County must honor prior approval.",
            "factual_background": "In 2018, the County approved a site plan.",
            "services_requested": ["written_response"],
        }
    })
    assert response.status_code == 200
    body = response.json()
    assert body["blocking"] == []
